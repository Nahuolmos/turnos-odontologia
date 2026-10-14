# WhatsApp vía Twilio (extra v1.0)

Complementa `05_reglas_de_negocio.md` (RN-NOTIF-*) y `07_flujos_principales.md` (Flujo 1). Alcance: WA REAL con Twilio en el MVP.

## Configuración

- Proveedor Twilio, número transparente de la clínica (`TWILIO_WA_FROM=whatsapp:+54911...`).
- Plantillas aprobadas: `confirmacion_reserva` (inmediata) y `recordatorio_24h` (un envío).
- Variables: nombre, fecha/hora AR, práctica, link `FRONTEND_URL/gestionar/:token`.

## Programación y cancelación

- Al confirmar: envío inmediato + `job Redis scheduled_for = inicio - 24h`.
- Al cancelar/reprogramar antes de T-24hs: cancelar el job (RN-NOTIF-03); reprogramar crea job nuevo.
- Unicidad: índice parcial — un `recordatorio_24h` whatsapp por turno (ver `04_modelo_de_datos.md`).

## Entrega y fallback

- Estados Twilio (`enviado/entregado/fallido`) en `Notificacion`; webhook `POST /api/webhooks/twilio` opcional v1.0.
- Fallo → backoff + respaldo email; el turno no cambia de estado por fallo de WA.
- Respaldo: evento Google Calendar + email (US-009).

## Riesgos

- Costo por mensaje y plantilla aprobada (presupuesto clínica chica/mediana).
- Bloqueo por spam si se abusa (solo 2 mensajes/turno en v1.0: confirmación + 1 recordatorio).
- Medir `entregado` vs asistencia para decidir refuerzo 2hs en v1.1 (SU-04).
