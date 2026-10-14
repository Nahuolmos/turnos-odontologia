# Funcionalidades

Organizadas por **épica** e **historia de usuario** (`US-NNN`). MVP = épicas 1-4. Épica 5 = v1.1 fast-follow.

## Épica 1: Reserva online 24/7 (MVP)

### US-001 — Ver horarios libres
**Como** paciente **Quiero** ver huecos libres por fecha/práctica **Para** elegir sin escribir por WhatsApp.
**Criterios de aceptación**:
- [ ] Lista slots por `duracion_min` de la práctica, sin mostrar datos de otros pacientes.
- [ ] Respeta timezone AR y horarios de atención.
- [ ] Mobile-first, carga < 2s en 4G.
**Reglas relacionadas**: RN-RES-01, RN-RES-02.

### US-002 — Reservar sin login y pagar seña MP
**Como** paciente **Quiero** reservar con nombre+teléfono y pagar la seña % **Para** asegurar mi turno.
**Criterios de aceptación**:
- [ ] Crea `Turno(pendiente_sena)` + `manage_token` + `preference MP` con `monto_sena` (foto según RN-PAGO-02).
- [ ] Webhook aprueba → `confirmado` + WA confirmación + job recordatorio T-24hs.
- [ ] Sin pago en TTL → libera slot.
**Reglas relacionadas**: RN-RES-03, RN-RES-04, RN-RES-05, RN-PAGO-01, RN-PAGO-02, RN-PAGO-03, RN-NOTIF-02.

### US-003 — Cancelar / reprogramar con token
**Como** paciente **Quiero** cancelar o reprogramar (1 vez sin perder seña) **Para** gestionar imprevistos.
**Criterios de aceptación**:
- [ ] Con `manage_token` y ventana ≥ 12hs.
- [ ] 1.ª reprogramación migra seña; 2.ª/tardía pierde seña y libera slot.
**Reglas relacionadas**: RN-CANCEL-01, RN-CANCEL-02, RN-CANCEL-03, RN-CANCEL-04, RN-NOTIF-03.

## Épica 2: Agenda multi-sillón + panel del día (MVP)

### US-004 — Agenda día/semana sin solape
**Como** recepcionista **Quiero** ver agenda multi-sillón día/semana **Para** ubicar turnos sin solapar.
**Criterios de aceptación**:
- [ ] Filtros por sillón/odontólogo/estado; solape rechazado 409 con mensaje claro.
- [ ] Crear turno interno (presencial/teléfono) con mismo motor de reglas.
**Reglas relacionadas**: RN-RES-01, RN-RES-02.

### US-005 — Panel del día
**Como** recepcionista **Quiero** un panel del día (llegadas, señas, faltas) **Para** operar la jornada.
**Criterios de aceptación**:
- [ ] Lista ordenada por hora con estado de seña y contacto WA.
- [ ] Marcar `completado`/`ausente` (alimenta RN-AUS-*).
**Reglas relacionadas**: RN-AUS-03.

### US-006 — Ver mi día (odontólogo)
**Como** odontólogo **Quiero** ver solo mi día/pacientes **Para** atender sin ruido.
**Criterios de aceptación**:
- [ ] Vista filtrada por `odontologo_id` = yo; sin ABM.
**Reglas relacionadas**: RN-RES-02.

## Épica 3: Seña Mercado Pago REAL (MVP)

### US-007 — Checkout seña %
**Como** paciente **Quiero** pagar la seña % por MP **Para** confirmar mi turno.
**Criterios de aceptación**:
- [ ] Preference con monto exacto RN-PAGO-02, moneda ARS.
- [ ] Estados pendiente/aprobado/rechazado visibles; reintento de pago.
**Reglas relacionadas**: RN-PAGO-01, RN-PAGO-02, RN-PAGO-04.

### US-008 — Webhook idempotente + conciliación
**Como** admin **Quiero** conciliación confiable MP→turno **Para** no confirmar dos veces ni perder pagos.
**Criterios de aceptación**:
- [ ] `mp_payment_id`/`idempotency_key` UNIQUE; reprocesos seguros.
- [ ] Reporte día: turnos vs señas aprobadas.
**Reglas relacionadas**: RN-PAGO-03. Detalle: `11_pagos_mercadopago.md`.

## Épica 4: WhatsApp Twilio REAL (MVP)

### US-009 — Confirmación + recordatorio 24hs (un envío)
**Como** paciente **Quiero** confirmación inmediata y 1 recordatorio 24hs antes **Para** no perder el turno.
**Criterios de aceptación**:
- [ ] WA vía Twilio número transparente; exactamente 1 recordatorio por turno.
- [ ] Cancelación/reprogramación previa cancela el job.
- [ ] Respaldo email + evento Google Calendar.
**Reglas relacionadas**: RN-NOTIF-01, RN-NOTIF-02, RN-NOTIF-03, RN-NOTIF-04. Detalle: `12_whatsapp_twilio.md`.

## Épica 5: v1.1 fast-follow (NO MVP)

### US-010 — Login paciente opcional + historial
**Como** paciente **Quiero** login opcional para ver mi historial **Para** seguir mis tratamientos.
**Criterios de aceptación**:
- [ ] Reserva sigue sin login; login solo añade historial.
- [ ] JWT rol `paciente`, RBAC según `03_actores_y_roles.md`.

### US-011 — Odontograma + historia clínica básica
**Como** odontólogo **Quiero** cargar odontograma/historia del paciente **Para** atender con contexto.
**Criterios de aceptación**:
- [ ] Lectura + carga básica por turno/paciente; auditoría de cambios.

### US-012 — ABM aranceles por Admin
**Como** admin **Quiero** ABM de aranceles/nomenclador **Para** mantener precios y % seña.
**Criterios de aceptación**:
- [ ] CRUD con vigencia y auditoría; no altera turnos existentes (RN-PAGO-02).
**Reglas relacionadas**: RN-ADMIN-01, RN-ADMIN-02.
