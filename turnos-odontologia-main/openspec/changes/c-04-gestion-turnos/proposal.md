# Proposal — C-04 gestion-turnos

## Why

C-02 y C-03 dejaron listos los modelos base (`Clinic`, `Paciente`, `Sillon`, `User`) y la autenticación JWT con RBAC. Falta el núcleo de dominio que los conecta: no existe `Turno`, no hay catálogo de prácticas y las páginas `AgendaPage` y `BookingPage` de C-01 son maquetas con datos hardcodeados.

Este change entrega la gestión de turnos de punta a punta: catálogo mínimo de `TipoPractica`, modelo `Turno` con estados y token de gestión, motor de reservas con anti-solape, agenda interna con filtros, flujo público de reserva sin login y cancelación con ventana de 12 horas. Sin esto no se puede operar una jornada real ni reservar desde el celular.

> **Nota de alcance frente al roadmap.** `CHANGES.md` etiqueta C-04 como `catalogo-sillones-practicas` y C-05 como `motor-reservas-slots-turnos`. Por instrucción explícita del usuario, `C-04-gestion-turnos` consolida el scope de Turnos/Agenda: el núcleo del C-05 del roadmap (modelo `Turno`, anti-solape, slots, cancelación) más el catálogo mínimo de `TipoPractica` que ese motor necesita para derivar duración y seña, más el cableado funcional de las páginas de Agenda y Reserva ya existentes en C-01. Quedan fuera el CRUD de aranceles del C-04 del roadmap (C-13) y la maquinaria completa de pagos MP, webhook, TTL Redis y notificaciones WhatsApp/Twilio (C-05/C-08/C-09 del roadmap).

## What Changes

### Backend — dominio `turnos`
- `TipoPractica`: `id` UUID, `clinic_id` FK, `nombre`, `duracion_min > 0`, `precio_base`, `sena_pct` 0..100, `activa`, `AuditMixin`.
- `Turno`: `id` UUID, `clinic_id`, `paciente_id`, `sillon_id`, `odontologo_id`, `tipo_practica_id`, `inicio`/`fin` timestamptz, `estado` (`pendiente_sena|confirmado|cancelado|reprogramado|completado|ausente`), `manage_token` UNIQUE, `reprogramaciones_count` default 0, `monto_sena`, `AuditMixin`.
- Constraints `CHECK (fin > inicio)` y `CHECK (sena_pct BETWEEN 0 AND 100)`; índices `(clinic_id,inicio)`, `(sillon_id,inicio)`, `(odontologo_id,inicio)`, `(paciente_id,inicio)`, `(estado)`.
- Schemas Pydantic v2, repositorios y `TurnoService` con: `fin` derivado de `duracion_min`, anti-solape por sillón y por odontólogo (409), snapshot `monto_sena = round(precio_base * sena_pct / 100)`, `manage_token` con `secrets.token_urlsafe(32)`, cancelación con ventana de 12 h y consultas de agenda.

### Backend — API
- Interno (JWT + `require_role`): `GET /api/internal/tipos-practica`, `GET /api/internal/sillones`, `GET /api/internal/turnos` (filtros `fecha|desde|hasta|sillon_id|odontologo_id|estado`), `POST /api/internal/turnos`, `POST /api/internal/turnos/{id}/cancelar`.
- Público (sin JWT): `GET /api/public/slots?fecha=&tipo_practica_id=`, `POST /api/public/reservas`, `GET /api/public/reservas/{id}?token=`, `POST /api/public/reservas/{id}/cancelar`.
- Routers registrados en `backend/app/main.py`.

### Backend — migración 004
- Tablas `tipos_practica` y `turnos` con constraints e índices.
- Seed idempotente de 5 prácticas (limpieza, arreglo, endodoncia, extracción, ortodoncia control) con `duracion_min`, `precio_base` y `sena_pct` **provisorios**, documentados como tales.

### Frontend — cableado funcional
- `AgendaPage`: agenda real por fecha, filtros sillón/odontólogo/estado, alta de turno interno, cancelación y leyenda de estados.
- `BookingPage`: selección de práctica, fecha, slots reales, formulario nombre + teléfono, confirmación con `manage_token` y enlace a `/gestionar/:token`.
- Features `frontend/src/features/agenda/` y `frontend/src/features/booking/` con API + hooks tipados sobre `shared/api-client`.

### Tests (TDD obligatorio)
- Unitarios de modelos y `TurnoService`: solape, duración, snapshot de seña, ventana de cancelación, unicidad de token.
- Integración de endpoints con `TestClient` y JWT firmado igual que `backend/tests/test_auth_me.py`.

## Capabilities

### New Capabilities

- `turnos-agenda`: catálogo mínimo de prácticas, modelo `Turno`, motor de reservas con anti-solape y snapshot de seña, disponibilidad pública, reserva sin login, consulta/cancelación con `manage_token`, agenda interna filtrada y RBAC.

### Modified Capabilities

- None — C-04 agrega una capability nueva y consume `clinica-personas`/`auth` sin modificarlas.

## Impact

- **Código nuevo**: `backend/app/domain/turnos/` (models, schemas, repository, service), `backend/app/api/internal/turnos.py`, `backend/app/api/public/turnos.py`, migración `004_turnos.py`, features y páginas de frontend.
- **Código modificado**: `backend/app/main.py` (registro de routers y modelos), `frontend/src/pages/AgendaPage.tsx`, `frontend/src/pages/BookingPage.tsx`, `frontend/src/router.tsx` solo si hace falta ajustar el alta pública.
- **APIs**: 9 endpoints nuevos entre internos y públicos; no rompe contratos existentes.
- **Datos**: dos tablas nuevas y seed de catálogo; no migra datos previos.
- **Dependencias**: SQLAlchemy 2.0, Alembic, Pydantic v2, FastAPI, `secrets`/`zoneinfo` de stdlib; frontend React 19 + Vite + Vitest ya presentes.
- **Fuera de alcance**: checkout/webhook Mercado Pago, TTL Redis del `pendiente_sena`, notificaciones WhatsApp/Twilio, worker de expiración, flujo completo de reprogramación (solo queda el campo `reprogramaciones_count`), CRUD de aranceles (C-13), multi-sede y login/historial de paciente (C-11).
- **Riesgo de calendario**: la ventana de horarios de atención y el mapeo sillón↔odontólogo no están definidos en la KB; se resuelven con supuestos provisorios documentados en `design.md`.
