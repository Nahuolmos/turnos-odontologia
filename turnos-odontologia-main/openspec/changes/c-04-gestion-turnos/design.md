# Design — C-04 gestion-turnos

## Context

C-02 entregó `Clinic`, `Paciente`, `Sillon`, `User` y el patrón `BaseRepository[T]` + `UnitOfWork`; C-03 entregó JWT, `require_role` y `require_odonto_confinement`. C-04 agrega el dominio que los usa. Las fuentes de verdad son `knowledge-base/04_modelo_de_datos.md` (§Turno, §TipoPractica, §Seed), `05_reglas_de_negocio.md` (RN-RES-01..05, RN-CANCEL-01..04), `06_funcionalidades.md` (US-001..005) y `07_flujos_principales.md` (Flujo 1 y 2).

Restricciones reales del repo: los tests de backend corren sobre SQLite (`backend/tests/conftest.py` usa `sqlite+aiosqlite`), las migraciones se validan contra PostgreSQL solo cuando está disponible, y el frontend ya tiene las páginas `AgendaPage`/`BookingPage` como maquetas dentro del router de C-01.

## Goals / Non-Goals

### Goals

- Persistir `TipoPractica` y `Turno` con constraints, índices y multi-tenancy por `clinic_id`.
- Cerrar el cálculo de duración, seña y token dentro de un único `TurnoService` reutilizado por la API interna y la pública.
- Garantizar anti-solape por sillón y por odontólogo con respuesta 409.
- Exponer disponibilidad y reserva públicas sin login, con `manage_token` para gestión posterior.
- Implementar cancelación con la ventana de 12 h y liberación inmediata del slot.
- Cablear funcionalmente la agenda interna y el flujo de reserva en el frontend existente.

### Non-Goals

- Checkout, preferencia y webhook de Mercado Pago; expiración por TTL con Redis; job de liberación.
- Envío de WhatsApp/Twilio, email o eventos de Google Calendar.
- Reprogramación completa: solo se deja `reprogramaciones_count` y el estado `reprogramado` para C-06.
- CRUD de aranceles, multi-sede, login/historial de paciente y marcado de `completado`/`ausente` (C-07).
- Rediseño visual: las pantallas mantienen la identidad y los componentes de C-01.

## Decisions

### D1 — Anti-solape validado en el servicio dentro de una transacción, no con `EXCLUDE` en la migración

**Decisión**: `TurnoService` consulta los turnos vigentes que intersectan el rango para el `sillon_id` y para el `odontologo_id` antes de insertar, dentro de la misma transacción, y lanza un conflicto de dominio que la API traduce a 409. La migración crea los índices de soporte y los `CHECK` portables, pero no un `EXCLUDE USING gist`.

**Alternativas**:
- `EXCLUDE USING gist (sillon_id WITH =, tstzrange(inicio, fin) WITH &&)` — mejor garantía ante concurrencia real, pero exclusivo de PostgreSQL, imposible de crear con `Base.metadata.create_all` en SQLite (que es donde corre la suite) y complica el downgrade.
- `UNIQUE (sillon_id, inicio, fin)` — solo detecta rangos idénticos; deja pasar solapes parciales, que es el caso normal.

**Rationale**: la suite del proyecto es SQLite-first; el motor debe ser testeable sin Postgres. El `EXCLUDE` queda documentado como endurecimiento futuro para producción (ver Risks).

### D2 — `manage_token` opaco generado por el servidor

**Decisión**: `secrets.token_urlsafe(32)` por turno, columna UNIQUE, generado en el servicio para toda alta (interna y pública). La API interna nunca lo devuelve; la pública lo devuelve solo en la creación y lo exige en `GET`/cancelar.

**Alternativas**:
- JWT firmado con `turno_id` — permite expiración y rotación, pero suma complejidad de firma/validación y no aporta en v1.
- `uuid4` — 122 bits y formato adivinable por estructura; menor entropía y peor higiene para un secreto portador.

**Rationale**: token portador simple, sin estado adicional, con entropía suficiente (256 bits) y sin dependencia de la clave JWT. Que el alta interna no lo exponga evita filtrar capacidad de gestión a un turno de mostrador.

### D3 — Snapshot de seña al crear, nunca recalculado

**Decisión**: `monto_sena` se calcula con `round(precio_base * sena_pct / 100)` y se persiste. Las lecturas y cancelaciones usan ese valor.

**Alternativas**:
- Calcular al leer desde `TipoPractica` — rompe RN-PAGO-02: un cambio de arancel alteraría turnos ya tomados.
- Guardar precio y porcentaje y recalcular — mismo problema, más columnas.

**Rationale**: es literalmente la regla de negocio y prepara C-08 (pago) sin migración.

### D4 — Ventana de 12 h: cancelación tardía permitida con seña retenida

**Decisión**: la cancelación siempre se acepta si el turno está en estado cancelable; `inicio - now() >= 12h` distingue cancelación a tiempo de tardía. Ambas liberan el slot (`estado = cancelado`); la respuesta agrega `sena_retenida: bool` calculado, sin columna nueva. Se evalúa en `America/Argentina/Buenos_Aires`.

**Alternativas**:
- Rechazar la cancelación tardía — contradice RN-CANCEL-03, que exige liberar el slot igual.
- Persistir un flag de reembolso — pertenece a C-08, que maneja `Pago` y reembolsos.

**Rationale**: cumple RN-CANCEL-01..04 con el modelo actual y deja la política de dinero explícita en la respuesta.

### D5 — Routers público e interno separados

**Decisión**: `app/api/internal/turnos.py` con `Depends(require_role([...]))`; `app/api/public/turnos.py` sin dependencia de auth. Ambos consumen el mismo `TurnoService`. Los schemas públicos excluyen `manage_token` salvo en la respuesta de creación y no exponen datos de otros pacientes.

**Alternativas**:
- Un solo router con dependencias opcionales — mezcla superficies de seguridad y facilita filtraciones accidentales.
- Reusar `/api/internal/turnos` para la reserva pública — obligaría a abrir endpoints autenticados al público.

**Rationale**: separa el contrato y el perímetro de seguridad, y mantiene una sola lógica de negocio.

### D6 — Migración 004 portable, seed idempotente con UUID fijos

**Decisión**: la migración usa el mismo estilo que `002`/`003` (`postgresql.UUID(as_uuid=True)` en Postgres, tipos SQLAlchemy estándar en el resto), `CHECK` e índices portables, y `downgrade` que borra `turnos` y luego `tipos_practica`. El seed usa `id` UUID fijos y `ON CONFLICT DO NOTHING` (o chequeo por nombre + clinic) para ser idempotente; los valores de `duracion_min`, `precio_base` y `sena_pct` se marcan como provisorios en el docstring.

**Alternativas**:
- `EXCLUDE` y `tstzrange` — ver D1.
- Seed por nombre sin UUID fijo — funciona, pero duplica si cambia el nombre; el UUID fijo hace el seed determinista.

**Rationale**: consistencia con las migraciones existentes y tests que corren sin Postgres.

### D7 — Disponibilidad: grilla por duración y asignación de odontólogo en la lectura

**Decisión**: la disponibilidad se calcula sobre una ventana de atención provisoria `09:00–19:00` en la zona de la clínica, avanzando de a `duracion_min`. Para cada inicio se busca el primer par `(sillon activo, odontólogo activo)` libre, y se devuelve ese par en el slot. La reserva pública confirma el par recibido y el servicio revalida el solape.

**Alternativas**:
- Exigir que el paciente elija odontólogo — la KB no lo pide en US-001 y agrega fricción.
- Tabla de horarios/agenda por profesional — correcto a futuro, pero no existe en el modelo y excede C-04.

**Rationale**: permite reservar sin login con la información disponible. La asignación real de horarios y sillón↔odontólogo queda como pregunta abierta (P-Alta de la KB).

### D8 — Fechas y límites de día en la zona de la clínica

**Decisión**: `fecha` se interpreta como día calendario en `America/Argentina/Buenos_Aires` y se convierte a `[00:00, 24:00)` local antes de comparar contra `inicio` (timestamptz). `desde`/`hasta` se aceptan como ISO-8601 con offset y se normalizan a UTC.

**Rationale**: evita el clásico corrimiento de un día por UTC y cumple la excepción global de RN.

### D9 — Token inválido responde 404, no 403

**Decisión**: `GET`/cancelar público devuelven 404 tanto si el turno no existe como si el token no coincide, y 409 si el turno ya está cancelado.

**Rationale**: 404 evita enumeración de reservas ajenas; 409 hace visible el estado inválido sin reescribirlo.

## Risks / Trade-offs

- **Concurrencia real**: la validación en servicio puede perder una carrera entre dos requests simultáneos si no hay lock. Mitigación: `SELECT ... FOR UPDATE` sobre los turnos candidatos en Postgres y reintento/409; el `EXCLUDE` queda como endurecimiento posterior. Riesgo aceptado para v1 (volumen de una clínica).
- **Horario de atención provisorio**: `09:00–19:00` es un supuesto, no un dato de la KB. Puede rechazar reservas válidas o mostrar slots fuera de horario real. Se documenta y se centraliza en una constante para cambiarla sin tocar la lógica.
- **Mapeo sillón↔odontólogo inexistente**: la asignación "primer par libre" puede generar agendas raras (un odontólogo saltando de sillón). C-07 deberá introducir la asignación real.
- **Sin TTL**: un turno `pendiente_sena` reserva el slot indefinidamente hasta que C-08/C-09 implementen la expiración. En este change no hay job ni Redis.
- **Seed con precios provisorios**: los `precio_base` y `sena_pct` no son datos del negocio. Están marcados como provisorios; C-13 los reemplaza con ABM.
- **Frontend sin rediseño**: la agenda y el booking reutilizan estilos de C-01; puede quedar ajuste visual menor para C-07.

## Migration Plan

1. Crear `backend/app/infrastructure/db/migrations/versions/004_turnos.py` con `revision = "004"`, `down_revision = "003"`.
2. `upgrade()`: crear `tipos_practica`, crear `turnos` con FKs a `clinic`, `pacientes`, `sillones`, `users` y `tipos_practica`, agregar `CHECK` e índices, e insertar el seed de 5 prácticas (idempotente).
3. `downgrade()`: borrar `turnos`, luego `tipos_practica`.
4. Verificar `alembic upgrade head` y `alembic downgrade 003` contra PostgreSQL, y `Base.metadata.create_all` en SQLite para la suite.
5. Sin backfill: no hay datos previos de turnos.

## UI Mockups

- **Decision**: no (functional wiring of existing C-01 pages; no new visual identity)
- **Design system revision**: n/a
- **Preview**: n/a
- **Visual verify**: manual (functional review)

## Open Questions

- ¿Horarios de atención reales por día y por sillón? (hoy `09:00–19:00` provisorio)
- ¿Un odontólogo queda fijado a un sillón o rota? Impacta la asignación de D7.
- ¿La cancelación tardía debe exponer el monto retenido o solo el booleano `sena_retenida`?
- ¿La recepción puede crear turnos en estado `confirmado` sin seña? (C-04 asume `pendiente_sena` siempre)
- ¿El alta interna debe generar `manage_token` aunque no se exponga? (se decide que sí, para permitir gestión posterior sin migración)
