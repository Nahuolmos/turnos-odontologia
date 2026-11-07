# Pagos con Mercado Pago (extra v1.0)

Complementa `05_reglas_de_negocio.md` (RN-PAGO-*) y `07_flujos_principales.md` (Flujos 1 y 4). Alcance: seña en % REAL en el MVP.

## Configuración

- Cuenta MP de la clínica; `MP_ACCESS_TOKEN` + `MP_WEBHOOK_SECRET` en env (ver `08_arquitectura_propuesta.md`).
- Moneda ARS; `monto_sena = round(precio_base * sena_pct / 100)` fotografiado en `Turno.monto_sena` (RN-PAGO-02).
- Preference por reserva: `external_reference = turno_id`, `metadata = {clinic_id, turno_id, idempotency_key}`.

## Webhook

- `POST /api/webhooks/mercadopago`: valida firma, busca `mp_payment_id`; si existe → 200 sin efectos (RN-PAGO-03).
- Solo `estado=aprobado` confirma el turno (`pendiente_sena → confirmado`) y dispara WA + job T-24hs.
- Guarda `raw_webhook` (jsonb) para auditoría/conciliación.
- Reintentos MP: endpoint idempotente + worker de reproceso (US-008).

## Reembolsos (según RN-CANCEL-*)

- 1.ª reprogramación: la seña migra (sin movimiento MP).
- Cancelación en ventana o 2.ª reprogramación / tardía: seña no reembolsable (política visible antes de pagar).
- Reembolso manual solo por Admin con motivo auditado (excepción, no flujo normal).

## Riesgos

- Fricción/abandono checkout (SU-01): medir tasa de abandono; considerar alias/CVU y montos redondeados.
- Contracargos y conciliación diaria (US-008, pregunta Media en `10_preguntas_abiertas.md`).
