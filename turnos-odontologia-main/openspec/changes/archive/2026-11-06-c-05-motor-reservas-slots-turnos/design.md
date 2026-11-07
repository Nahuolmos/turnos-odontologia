# Design - C-05 motor-reservas-slots-turnos

## Context

C-04 entregó el modelo `Turno`, el catálogo `TipoPractica`, el `TurnoService`, los endpoints públicos/internos y la migración `004`. La suite actual cubre anti-solape, snapshot de seña, disponibilidad y `manage_token`. C-05 no reescribe ese núcleo: agrega las reglas que faltaban para cumplir RN-AUS-02 y RN-RES-04, más el alias de contrato `practica`.

Restricciones reales del repo:

- La suite de backend corre sobre SQLite (`backend/tests/conftest.py`), por lo que las soluciones deben funcionar sin PostgreSQL.
- No existe todavía un consumidor de colas Redis: `app/infrastructure/queue/worker.py` es un heartbeat. C-08/C-10 agregarán los jobs de pago y notificaciones.
- La migración `004` ya está aplicada y no debe editarse; los cambios de esquema van en una migración nueva.
- `Settings.mp_ttl_min` ya existe con default 30.

## Goals / Non-Goals

### Goals

- Rechazar reservas públicas e internas de pacientes con bloqueo vigente, con 403 y `bloqueado_hasta`.
- Liberar automáticamente turnos `pendiente_sena` vencidos y devolver el slot a disponibilidad.
- Ejecutar el barrido desde el worker con una sesión propia, de forma idempotente y tolerante a errores.
- Aceptar `practica` como alias de `tipo_practica_id` en `GET /api/public/slots`.
- Agregar índices de soporte en una migración `005`.

### Non-Goals

- Checkout, preferencia y webhook de Mercado Pago (C-08/C-09).
- Confirmación automática del turno al aprobarse el pago (C-09).
- Excepción auditada de recepción para pacientes bloqueados (C-07).
- Reprogramación completa y cancelación pública avanzada (C-06).
- Notificaciones WhatsApp/Twilio y cancelación de jobs de recordatorio (C-10).
- Caché Redis de disponibilidad y `EXCLUDE USING gist` en PostgreSQL (endurecimiento futuro).
- Cambios de frontend: el bloqueo se reflejará en la UI cuando C-07 exponga el flujo de excepción.

## Decisions

### D1 - Barrido periódico contra la base, no job Redis diferido

**Decisión**: la expiración se implementa como un barrido idempotente sobre `turnos` (`estado = 'pendiente_sena'` y `created_at <= cutoff`) ejecutado por el worker cada `WORKER_POLL_SECONDS`. No se depende de Redis para la corrección del TTL.

**Alternativas**:
- Job Redis con `ZADD` y timestamp de expiración: es el diseño del roadmap, pero hoy no hay consumidor de colas; agregarlo sin C-08/C-10 dejaría una dependencia muerta y un camino de falla extra.
- Expiración perezosa al consultar slots: libera el slot solo si alguien consulta, no cumple "libera el slot" de forma observable y complica la agenda interna.

**Rationale**: la base ya es la fuente de verdad; un barrido cada 60 s acota el error a un minuto y sobrevive reinicios. Redis se incorporará cuando exista la infraestructura de jobs de C-08/C-10, sin cambiar el contrato de `expirar_pendientes`.

### D2 - TTL uniforme para todo turno `pendiente_sena`

**Decisión**: se expiran todos los turnos `pendiente_sena`, tanto los creados por el portal como los del mostrador. `MP_TTL_MIN` se lee de `Settings.mp_ttl_min`.

**Rationale**: RN-RES-04 dice "todo turno nace en `pendiente_sena` con expiración". Si recepción necesita reservar sin seña, el flujo correcto es confirmar el turno o usar el mecanismo de excepción de C-07, no dejar pendientes indefinidos que bloquean sillones.

### D3 - El bloqueo se valida en `TurnoService.crear_turno`

**Decisión**: la consulta de bloqueo vigente vive en `TurnoService.crear_turno`, el único punto por el que pasan el alta pública y la interna. `crear_reserva_publica` reutiliza ese método. Un `PacienteBloqueado` de dominio se traduce a 403 en ambos routers.

**Alternativas**:
- Validar solo en el router público: deja pasar el alta interna, violando RN-AUS-02.
- Validar en `crear_reserva_publica`: no cubre el alta interna.

**Rationale**: un único choke point evita divergencias. La excepción auditada de C-07 podrá agregar un parámetro explícito (`permitir_bloqueo` + `motivo`) sin duplicar la consulta.

### D4 - Respuesta 403 con `bloqueado_hasta`

**Decisión**: el error se traduce a `HTTPException(status_code=403, detail={"message": ..., "bloqueado_hasta": "<ISO>"})`. El campo va en el cuerpo para que el frontend pueda mostrar la fecha sin parsear texto libre.

**Rationale**: el contrato de CHANGES.md pide "403 con `bloqueado_hasta`". Un objeto en `detail` mantiene el envelope de FastAPI y permite crecer a otros metadatos. Cuando C-07 agregue la UI de bloqueo, el cliente leerá `detail.bloqueado_hasta`.

### D5 - Alias `practica` compatible con `tipo_practica_id`

**Decisión**: `GET /api/public/slots` acepta ambos nombres. Si llegan los dos y difieren, responde 422; si no llega ninguno, responde 422. Si llega uno, ese se usa.

**Rationale**: el roadmap documenta `practica`; el frontend de C-04 ya usa `tipo_practica_id`. Aceptar ambos evita romper el cliente existente y cumple el contrato nuevo. La validación explícita evita elegir silenciosamente un valor arbitrario.

### D6 - Migración `005` en lugar de editar `004`

**Decisión**: se crea `005_turnos_expiracion_bloqueos.py` con `down_revision = "004"`, que agrega:

- `ix_turnos_estado_created_at` sobre `(estado, created_at)` para el barrido;
- `ix_bloqueos_paciente_id_hasta` sobre `(paciente_id, hasta)` para la consulta de bloqueo vigente.

Los modelos declaran los mismos índices en `__table_args__`.

**Rationale**: `004` ya está aplicada en entornos existentes; editarla rompería el historial de Alembic. Los índices son aditivos y reversibles.

### D7 - Normalización de fechas para SQLite

**Decisión**: las comparaciones de `created_at` con el cutoff se hacen con un cutoff naive en UTC cuando el dialecto es SQLite, y aware en PostgreSQL. El servicio conserva `_as_aware` para los objetos leídos.

**Rationale**: SQLite almacena `DateTime(timezone=True)` sin offset; comparar un parámetro aware contra una columna naive produce resultados inconsistentes. PostgreSQL conserva `timestamptz` y debe recibir el valor aware.

## Risks / Trade-offs

- **Precisión del TTL**: el barrido cada 60 s puede liberar el slot hasta un minuto después del TTL. Es aceptable para v1 y evita la complejidad de un scheduler exacto.
- **Concurrencia de reserva**: el anti-solape sigue siendo check-then-insert dentro de la transacción. En PostgreSQL, dos requests simultáneos podrían pasar la validación antes del commit. El endurecimiento con `EXCLUDE USING gist` o `SELECT ... FOR UPDATE` sobre el sillón queda como deuda documentada (C-05 no lo introduce para no romper SQLite).
- **Bloqueo interno sin excepción**: hasta C-07, recepción no puede crear turnos para un paciente bloqueado. Es el comportamiento correcto de RN-AUS-02; la excepción auditada es explícitamente C-07.
- **Worker único**: si se ejecutan varias instancias del worker, el barrido es idempotente pero puede haber trabajo duplicado. No hay efectos secundarios porque la transición `pendiente_sena -> cancelado` es idempotente.

## Migration / Rollout

1. `alembic upgrade head` aplica `005` (índices aditivos).
2. El worker puede desplegarse antes o después de la migración; si la columna/índice no existe, el ciclo falla y se reintenta.
3. Rollback: `alembic downgrade 004` elimina los índices; no hay pérdida de datos.

## Open Questions

- ¿El TTL debe pausarse para turnos creados por recepción mientras el paciente paga en el mostrador? La KB dice "todo turno", así que v1 aplica el TTL uniforme. Si el negocio pide una excepción, se resuelve en C-07/C-08 con un estado o un parámetro explícito.
- ¿La disponibilidad debe cachearse en Redis? Se difiere hasta medir la carga real; la KB pide < 2 s y el cálculo actual es acotado (grilla de 10 h por práctica).
