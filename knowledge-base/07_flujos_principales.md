# Flujos Principales

## Flujo 1: Reserva pública con seña MP (MVP)
**Disparador**: paciente elige slot. **Actor**: paciente sin login.
**Pasos**:
1. Frontend pide `GET /api/public/slots?fecha=&practica=` → API devuelve huecos (RN-RES-01/02 ya aplicados).
2. Paciente envía nombre+teléfono → `POST /api/public/reservas` crea `Turno(pendiente_sena)` + `manage_token` + preference MP (RN-RES-03, RN-RES-04, RN-PAGO-02).
3. Paciente paga en MP → `POST /api/webhooks/mercadopago` (idempotente) → `Pago.aprobado` → `Turno.confirmado` (RN-RES-05, RN-PAGO-03).
4. API encola WA confirmación inmediata y programa job Redis `recordatorio T-24hs` (RN-NOTIF-01/02); crea evento Calendar + email respaldo.
5. T-24hs: worker envía 1 WA; marca `Notificacion.enviado/entregado`.
**Diagrama**:
```
Paciente → SPA → API → Postgres (turno pendiente)
SPA → MP (checkout) → webhook API → Postgres (confirmado)
API → Redis (job T-24hs) → Twilio → Paciente
```
**Casos de error**:
- Slot tomado en concurrente → 409 + ofrecer alternativos (RN-RES-01/02).
- Pago no llega en TTL → expira reserva, libera slot, avisa por email si existe.
- Webhook duplicado → 200 sin efectos (RN-PAGO-03).
- Twilio falla → `fallido` + reintento backoff; no cambia estado del turno.

## Flujo 2: Cancelar / reprogramar (paciente o recepción)
**Disparador**: paciente (token) o recepción. **Actor**: ambos.
**Pasos**:
1. Validar ventana ≥ 12hs (RN-CANCEL-01); si tardía → avisar pérdida de seña (RN-CANCEL-03).
2. Cancelar: `estado=cancelado`, liberar slot, cancelar job WA (RN-CANCEL-04, RN-NOTIF-03).
3. Reprogramar (1.ª): validar nuevo slot + misma ventana, migrar seña, `reprogramaciones_count=1`, reprogramar job WA (RN-CANCEL-02).
**Casos de error**:
- 2.ª reprogramación → exigir nueva seña.
- Paciente bloqueado (RN-AUS-01) intentando re-reservar → 403 con `bloqueado_hasta`.

## Flujo 3: Jornada de recepción (panel del día)
**Disparador**: inicio de jornada. **Actor**: recepcionista.
**Pasos**:
1. `GET /api/panel/dia?fecha=hoy` → lista por hora con seña y contacto.
2. Confirmar llegadas; marcar `completado`/`ausente` (2.ª falta → bloqueo 30d automático, RN-AUS-01).
3. Crear turnos presenciales/teléfono con mismo motor de reglas.
**Casos de error**:
- Paciente bloqueado pide turno mostrador → excepción con motivo auditado (RN-AUS-02).

## Flujo 4: Conciliación MP (admin)
**Disparador**: cierre del día. **Actor**: admin.
**Pasos**:
1. Reporte turnos confirmados vs pagos aprobados.
2. Reprocesar webhooks pendientes (idempotentes).
3. Reembolsos solo según RN-CANCEL-02/03 (1.ª repro migra; tardía no reembolsa).
