# Proposal - C-05 motor-reservas-slots-turnos

## Why

C-04 consolidó el núcleo de turnos (modelo `Turno`, `TipoPractica`, anti-solape, disponibilidad, reserva pública y alta interna) para poder operar la agenda. Sin embargo, el motor todavía no cumple tres reglas duras del dominio que el roadmap asigna a C-05:

1. Un paciente con bloqueo por ausentismo puede reservar; la regla RN-AUS-02 exige rechazarlo.
2. Un turno `pendiente_sena` no se libera nunca si el pago no llega; la regla RN-RES-04 exige expirarlo con `MP_TTL_MIN=30`.
3. El contrato público del roadmap usa `GET /api/public/slots?fecha=&practica=`, pero la API solo acepta `tipo_practica_id`.

Este change cierra esos huecos con tests TDD, un worker de expiración y la migración de índices que soporta ambas consultas. No reimplementa lo que C-04 ya entregó: lo verifica y lo extiende.

> **Relación con el roadmap.** `CHANGES.md` asigna a C-05 el núcleo completo del motor. C-04 ya lo implementó por instrucción explícita del usuario (ver `openspec/changes/c-04-gestion-turnos/proposal.md`). C-05 completa los deltas pendientes y deja evidencia de que el resto sigue vigente. La integración real con Mercado Pago (checkout/webhook y confirmación de pago) sigue fuera de alcance: pertenece a C-08/C-09. La excepción manual de recepción para pacientes bloqueados (RN-AUS-02) pertenece a C-07.

## What Changes

### Backend - bloqueo de 30 días

- `TurnoService.crear_turno` SHALL consultar `Bloqueo` vigente (`desde <= now < hasta`) por `(clinic_id, paciente_id)` antes de insertar y lanzar un error de dominio si existe.
- `POST /api/public/reservas` y `POST /api/internal/turnos` SHALL responder **403** con `bloqueado_hasta` en el cuerpo.
- La excepción auditada de recepción queda explícitamente fuera de C-05 (se implementa en C-07).

### Backend - expiración de `pendiente_sena`

- `TurnoService.expirar_pendientes(clinic_id=None, now=None, ttl_min=None)` SHALL cancelar los turnos en estado `pendiente_sena` cuyo `created_at <= now - MP_TTL_MIN` y devolver los turnos liberados.
- El worker (`app/infrastructure/queue/worker.py`) SHALL ejecutar un ciclo de expiración cada `WORKER_POLL_SECONDS` usando una sesión propia y commit al finalizar. El barrido SHALL ser idempotente y tolerante a reinicios.
- El slot liberado SHALL volver a aparecer en `GET /api/public/slots` y en la agenda interna.
- `MP_TTL_MIN` se toma de `Settings.mp_ttl_min` (default 30).

### Backend - contrato de disponibilidad

- `GET /api/public/slots` SHALL aceptar `practica` como alias de `tipo_practica_id`.
- Si llegan ambos y difieren, o no llega ninguno, SHALL responder **422**.

### Backend - migración e índices

- Nueva migración `005_turnos_expiracion_bloqueos.py` (no se edita la `004`, ya aplicada en C-04):
  - índice `ix_turnos_estado_created_at` para el barrido de expiraciones;
  - índice `ix_bloqueos_paciente_id_hasta` para la consulta de bloqueo vigente.
- Los modelos `Turno` y `Bloqueo` SHALL declarar los mismos índices para que `Base.metadata` y Alembic coincidan.

### Tests

- Unitarios de servicio: bloqueo vigente/vencido/otra clínica, expiración dentro/fuera de TTL, estados no expirables, liberación del slot.
- Integración de API: 403 con `bloqueado_hasta` en público e interno, alias `practica`, 422 por parámetros ambiguos.
- Worker: ciclo de expiración con commit y persistencia del estado `cancelado`.
- Migración: cadena `005 -> 004` e índices declarados en metadata.

## Capabilities

### New Capabilities

- `motor-reservas`: reglas de admisión y ciclo de vida del turno que C-04 dejó pendientes: bloqueo por ausentismo, expiración de reservas no abonadas y contrato de disponibilidad.

### Modified Capabilities

- None - `turnos-agenda` (C-04) no cambia sus requisitos; `motor-reservas` agrega los deltas de C-05. Cuando C-04 se archive, ambos conjuntos pueden convivir como capacidades complementarias.

## Impact

- **Código modificado**: `backend/app/domain/turnos/service.py`, `backend/app/domain/turnos/repository.py`, `backend/app/domain/clinica/repository.py`, `backend/app/domain/clinica/models.py`, `backend/app/domain/turnos/models.py`, `backend/app/api/public/turnos.py`, `backend/app/api/internal/turnos.py`, `backend/app/infrastructure/queue/worker.py`.
- **Código nuevo**: `backend/app/infrastructure/queue/expirations.py`, `backend/app/infrastructure/db/migrations/versions/005_turnos_expiracion_bloqueos.py`, tests asociados.
- **APIs**: cambio compatible en `GET /api/public/slots` (se agrega alias); nuevo comportamiento 403 en reservas públicas/internas cuando hay bloqueo.
- **Datos**: dos índices nuevos; no hay cambios destructivos ni migración de datos.
- **Dependencias**: ninguna nueva. No se requiere Redis para la corrección del TTL: el barrido usa la base como fuente de verdad.
- **Fuera de alcance**: checkout/preferencia/webhook de Mercado Pago, notificaciones WhatsApp/Twilio, excepción de recepción con auditoría (C-07), reprogramación completa (C-06), caché Redis de slots y `EXCLUDE USING gist` (endurecimiento futuro documentado en `design.md`).
