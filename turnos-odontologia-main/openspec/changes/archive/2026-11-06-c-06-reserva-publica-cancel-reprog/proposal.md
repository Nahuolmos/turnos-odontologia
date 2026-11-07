# Proposal — C-06 reserva pública, cancelación y reprogramación

## Why

C-05 dejó cerrado el núcleo del motor de reservas: `Turno` con `manage_token`, disponibilidad por práctica, alta pública en `pendiente_sena`, anti-solape, expiración por TTL y cancelación con ventana de 12 h. Pero el paciente todavía no puede autogestionar su turno: `GET /api/public/reservas/{id}?token=` exige conocer el `id`, no existe reprogramación y `/gestionar/:token` es un formulario placeholder que no llama a la API.

Este change cierra US-003 (ver/cancelar/reprogramar con token) y completa la reserva pública E2E sobre lo ya entregado por C-05, sin tocar pagos reales ni notificaciones.

## What Changes

### Backend — consulta y contrato público

- Nuevo `GET /api/public/reservas/gestion/{token}` que resuelve un turno por `manage_token` (UNIQUE) sin exigir `id`; 404 si no existe. La ruta literal se declara antes de `/reservas/{turno_id}` para evitar que `gestion` se interprete como UUID.
- `TurnoPublicoOut` incorpora `reprogramaciones_count`.
- Nuevo `TurnoGestionOut` con flags derivados, no persistidos: `puede_reprogramar`, `puede_reprogramar_sin_sena` y `cancelacion_retiene_sena`.

### Backend — cancelación

- Se mantiene `POST /api/public/reservas/{turno_id}/cancelar?token=` y su equivalente interno `POST /api/internal/turnos/{turno_id}/cancelar`.
- Semántica explícita: cancelar siempre se permite; `sena_retenida = (inicio - now) < 12 h`; `estado = "cancelado"`; 409 si ya estaba cancelado; 404 si el token no corresponde. El slot se libera al salir de `ESTADOS_VIGENTES`.

### Backend — reprogramación

- Nuevo `POST /api/public/reservas/{turno_id}/reprogramar?token=` y su equivalente interno `POST /api/internal/turnos/{turno_id}/reprogramar` sin token.
- Body: `{"inicio": datetime, "sillon_id"?: UUID, "odontologo_id"?: UUID}`; los recursos ausentes se heredan del turno actual.
- Reglas: nuevo horario con `nuevo_inicio - now >= 12 h`; anti-solape por sillón y odontólogo excluyendo el turno actual; práctica activa y recursos de la misma clínica; 409 si el turno está `cancelado`, `completado` o `ausente`.
- 1.ª reprogramación en fecha (sin segunda previa y con ≥ 12 h): se actualiza la misma fila, la seña viaja y `reprogramaciones_count` pasa a 1.
- 2.ª reprogramación o reprogramación tardía (< 12 h): el turno viejo queda `cancelado` con seña retenida y se crea un turno nuevo `pendiente_sena` con nuevo `manage_token`, seña recalculada y `reprogramaciones_count` incrementado. El slot viejo se libera y el nuevo queda ocupado.
- Sin migración Alembic: no hay columnas ni tablas nuevas.

### Frontend

- `ManageAppointmentPage` real sobre `/gestionar/:token`: resuelve el turno por token, muestra estado, fecha, práctica, sillón, seña y reprogramaciones, permite cancelar con confirmación explícita (advirtiendo retención si < 12 h) y reprogramar reutilizando `getSlots`.
- La lógica se extrae a `frontend/src/features/booking/` (API, hook y componentes) siguiendo el patrón de `useBooking`; tipos nuevos en `types.ts`, sin `any`, mobile-first y reutilizando tokens/CSS existentes.
- Cuando la reprogramación exige nueva seña, la UI muestra el nuevo `manage_token`, el monto y el estado `pendiente_sena`.

### Tests (TDD obligatorio)

- Dominio: ventana de 12 h, 1.ª reprogramación migra seña, 2.ª/tardía crea turno nuevo y libera el anterior, anti-solape con exclusión del turno actual, estados no reprogramables, token inválido.
- API: consulta por token, cancelación anticipada/tardía, reprogramación pública e interna, 404/409 y slot re-reservable.
- Frontend: API tipada, hook de gestión y flujo de página con mocks de `apiClient`/feature API.

## Capabilities

### New Capabilities

- `reserva-publica`: autogestión del paciente por `manage_token` (consulta sin `id`, cancelación con política de seña y reprogramación con migración o pérdida de seña). Se separa de `motor-reservas` porque esta capability gobierna el plano de autoservicio y sus reglas RN-CANCEL, mientras `motor-reservas` conserva admisión, disponibilidad y ciclo de expiración.

### Modified Capabilities

- Ninguna. No se reescriben requisitos existentes de `motor-reservas`; el nuevo endpoint de consulta y los flujos de gestión se agregan como capability nueva.

## Impact

- **Código backend nuevo/modificado**: `backend/app/domain/turnos/service.py` (`reprogramar`, `get_por_token_solo`, resultado y errores), `repository.py` (`get_by_manage_token_solo` si no alcanza el método actual), `schemas.py` (`TurnoGestionOut`, `ReprogramacionPublicaOut`, `ReprogramarPayload`), `api/public/turnos.py` y `api/internal/turnos.py`.
- **Código frontend nuevo/modificado**: `frontend/src/features/booking/{api.ts,types.ts,hooks/useManageAppointment.ts,components/*}`, `frontend/src/pages/ManageAppointmentPage.tsx` y su CSS.
- **APIs**: 1 endpoint público nuevo de consulta y 2 de reprogramación (público + interno); se extienden respuestas existentes con campos aditivos. No hay cambios breaking.
- **Datos**: ninguno. `manage_token`, `reprogramaciones_count` y `monto_sena` ya existen desde C-04/C-05.
- **Dependencias**: C-05 archivado y `openspec/specs/motor-reservas/spec.md` vigente; C-08/C-09 (pagos reales) y C-10 (notificaciones/recordatorios) quedan fuera.
- **Governance**: MEDIO. No se toca autenticación, RBAC base, pagos ni infraestructura.
- **Fuera de alcance**: checkout/webhook Mercado Pago, reembolsos, envío/cancelación real de jobs de recordatorio (solo se documenta el hook para C-10), migración Alembic, login de paciente (C-11), multi-clínica y endurecimiento `EXCLUDE USING gist`.
- **Riesgo de UI**: la política de design system/mockups no está registrada en `.active-orchestrator-state.json`; debe resolverse antes de aplicar cambios visuales.
