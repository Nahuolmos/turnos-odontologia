# Reglas de Negocio

Cada regla tiene código único `RN-{DOMINIO}-{NN}` para trazabilidad (usado en `06_funcionalidades.md` y `07_flujos_principales.md`).

## Dominio: Reservas (RN-RES)

- **RN-RES-01**: Un sillón no puede tener dos turnos superpuestos (mismo `sillon_id`, rangos `[inicio, fin)` intersectados → rechazo 409).
- **RN-RES-02**: Un odontólogo no puede tener dos turnos superpuestos (misma condición sobre `odontologo_id`).
- **RN-RES-03**: La reserva pública no exige login; emite `manage_token` para gestión posterior.
- **RN-RES-04**: Todo turno nace en `pendiente_sena` con expiración (TTL a definir, propuesto 30 min); sin seña aprobada en ventana → se libera el slot.
- **RN-RES-05**: Solo pasa a `confirmado` con `Pago.estado=aprobado` (webhook MP).

## Dominio: Cancelación / reprogramación (RN-CANCEL)

- **RN-CANCEL-01**: Cancelación mínima 12hs de anticipación (`inicio - now() >= 12h`).
- **RN-CANCEL-02**: 1 reprogramación sin perder seña por turno (`reprogramaciones_count < 1`, nuevo horario con misma anticipación 12hs); la seña viaja al nuevo turno.
- **RN-CANCEL-03**: 2.ª reprogramación o cancelación tardía (< 12hs) → seña no reembolsable; el slot se libera igual.
- **RN-CANCEL-04**: Cancelar/reprogramar libera el horario inmediatamente para re-reserva.

## Dominio: Ausentismo / bloqueo (RN-AUS)

- **RN-AUS-01**: 2 faltas (`estado=ausente` marcado por recepción) → bloqueo de reserva por 30 días (`bloqueado_hasta = now() + 30d`). Decisión ronda 1 (respuesta 4).
- **RN-AUS-02**: Paciente bloqueado no puede crear reservas (público e interno lo rechazan); recepción puede exceptuar con auditoría (motivo obligatorio).
- **RN-AUS-03**: La falta la marca recepción/odontólogo desde panel del día (no automática).

## Dominio: Pagos / seña (RN-PAGO)

- **RN-PAGO-01**: Seña en % del precio de la práctica, según `TipoPractica.sena_pct`, configurable por Admin.
- **RN-PAGO-02**: `monto_sena = round(precio_base * sena_pct / 100)` al crear la reserva (foto del monto en `Turno.monto_sena`; cambios posteriores de arancel no alteran turnos existentes).
- **RN-PAGO-03**: Webhook MP idempotente (`mp_payment_id` / `idempotency_key` UNIQUE; reprocesos no duplican confirmación).
- **RN-PAGO-04**: Un solo pago aprobado vigente por turno.

## Dominio: Notificaciones (RN-NOTIF)

- **RN-NOTIF-01**: Recordatorio WhatsApp 24hs antes, UN solo envío por turno confirmado (`scheduled_for = inicio - 24h`).
- **RN-NOTIF-02**: Confirmación inmediata por WA + respaldo email al aprobarse la seña.
- **RN-NOTIF-03**: Si el turno se cancela/reprograma antes de T-24hs, el job programado se cancela (no enviar recordatorio de turno muerto).
- **RN-NOTIF-04**: Proveedor Twilio con número transparente de la clínica (decisión ronda 1).

## Dominio: Administración (RN-ADMIN)

- **RN-ADMIN-01**: Solo `admin` modifica `% seña` y (v1.1) aranceles; todo cambio audita `quien/cuando/antes/después`.
- **RN-ADMIN-02**: En v1.0 aranceles son lectura + seed inicial; el CRUD llega en v1.1 (ver IN-01).

## Dominio: Excepciones globales

- Toda validación de solape, ventana 12hs y bloqueo se evalúa en `America/Argentina/Buenos_Aires`.
- Errores de MP/Twilio nunca dejan el turno en estado ambiguo: `pendiente_sena` + reintento con backoff; auditoría en `Pago.raw_webhook` / `Notificacion.estado=fallido`.
- Recepción puede operar por teléfono/presencial creando el turno como interno (mismo motor de reglas, sin `manage_token` público).
