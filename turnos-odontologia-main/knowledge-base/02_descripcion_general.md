# Descripción General

## Stack tecnológico

| Capa | Tecnologías | Versión mínima |
|------|--------------|----------------|
| Backend | Python + FastAPI + SQLAlchemy ORM | Python 3.12, FastAPI 0.115+ |
| Auth | JWT (Bearer) | — |
| Base de datos | PostgreSQL | 16+ |
| Async / colas | Redis (cola + scheduler recordatorios) | 7+ |
| Infra local/dev | Docker + Docker Compose | Compose v2 |
| Frontend | React + TypeScript + Vite | React 18+, TS 5+ |
| UI | Mobile-first (mayoría reserva desde teléfono) | — |
| Pagos | Mercado Pago SDK + webhooks | API v1 vigente |
| Notificaciones | Twilio WhatsApp (Cloud API) | — |
| Respaldo | Google Calendar API + email (SMTP) | — |

## Arquitectura general

```
Mobile/Desktop → SPA React (Vite) → API REST FastAPI → PostgreSQL
                                        │  ├→ Redis (jobs: WA 24hs, expiración señas)
                                        │  ├→ Mercado Pago (seña % + webhook)
                                        │  ├→ Twilio WhatsApp (recordatorio 24hs)
                                        │  └→ Google Calendar + email (respaldo)
```

- Backend monolito modular (routers por dominio: turnos, pagos, notificaciones, admin) — prioridad CALIDAD/escalabilidad sobre velocidad (ronda 1, respuesta 4): separación por dominios desde día 1 para partir a servicios si crece, sin microservicios prematuros.
- Frontend SPA mobile-first, rutas públicas de reserva sin auth; panel interno con JWT por rol.
- 1 clínica en v1 (`clinic_id` presente desde día 1 solo como preparación multi-sede futura — ver DD-06).
- Jobs asíncronos en Redis: programar recordatorio WA T-24hs al confirmar turno con seña; expirar reservas sin seña pagada.

## Integraciones externas

| Servicio | Propósito | Tipo |
|----------|-----------|------|
| Mercado Pago | Cobro de seña en % + webhook de confirmación | SDK + REST/webhook |
| Twilio WhatsApp | Confirmación + recordatorio 24hs (un envío), número transparente | REST API |
| Google Calendar | Respaldo de agenda por sillón/odontólogo | REST API (OAuth clínica) |
| Email (SMTP) | Respaldo de confirmación/recordatorio | SMTP |
| OS / ARCA | Fuera de v1 (v2 consciente) | — |

Detalle pagos: ver `11_pagos_mercadopago.md`. Detalle WhatsApp: ver `12_whatsapp_twilio.md`.

## API REST (resumen por recurso)

- `POST /api/public/slots?clinica=1&fecha=&practica=` — huecos libres (público).
- `POST /api/public/reservas` — crear reserva (pública, sin auth; devuelve `payment_url` MP).
- `POST /api/public/reservas/{id}/cancelar` / `/reprogramar` — con reglas RN-RES-*.
- `GET /api/agenda?vista=dia|semana&sillon=&odontologo=` — agenda multi-sillón (recepción/odontólogo/admin).
- `GET /api/panel/dia?fecha=` — panel del día (recepción).
- `POST /api/webhooks/mercadopago` — webhook MP (idempotente).
- `POST /api/webhooks/twilio` — estado de entrega WA (opcional v1.0).
- `GET /api/admin/aranceles` — lectura (v1.0); ABM completo en v1.1.
- (v1.1) `/api/auth/*`, `/api/odontograma/*`, `/api/admin/aranceles` (CRUD).
