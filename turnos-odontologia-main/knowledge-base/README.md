# SaaS Odontología — Base de Conocimiento

Base de conocimiento generada en Mode B interactivo (ronda 1 respondida, sin re-preguntas) a partir de `discovery/discovery.md` + `state.discovery` (discovery-research) + respuestas de usuario. Fuente: `interactive`.

## Índice de Archivos

| Archivo | Contenido |
|---------|-----------|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito, objetivos por actor, alcance v1.0 (3b) + v1.1 fast-follow, fuera de alcance, métricas |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack FastAPI+React+Postgres+Redis, arquitectura, integraciones, API REST |
| [03_actores_y_roles.md](03_actores_y_roles.md) | 5 actores, RBAC, rutas públicas |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | 10 entidades, ERD textual, constraints anti-solape, seed |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | RN-RES/CANCEL/AUS/PAGO/NOTIF/ADMIN (bloqueo 30d, seña %, 12hs, 1 repro) |
| [06_funcionalidades.md](06_funcionalidades.md) | US-001..009 (MVP) + US-010..012 (v1.1) |
| [07_flujos_principales.md](07_flujos_principales.md) | Reserva+seña, cancel/reprog, panel día, conciliación |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Patrones, directorios backend/frontend, seguridad, env vars |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | DD-01..07 + SU-01..04 |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | IN-01 (Discovery vs 3b) + 8 preguntas priorizadas |
| [11_pagos_mercadopago.md](11_pagos_mercadopago.md) | Extra: seña % real, webhook idempotente, reembolsos |
| [12_whatsapp_twilio.md](12_whatsapp_twilio.md) | Extra: Twilio, 1 envío 24hs, fallback |

## Quick Start para Desarrolladores

1. Entender el dominio → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. Entender los datos → [04](04_modelo_de_datos.md)
3. Entender las reglas → [05](05_reglas_de_negocio.md)
4. Entender la arquitectura → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md)
5. Implementar → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. Antes de codificar → [10](10_preguntas_abiertas.md)

## Resumen Ejecutivo

SaaS mobile-first para 1 clínica: reserva 24/7 sin login + agenda multi-sillón sin solapes + seña % MP real + recordatorio WA Twilio 24hs (un envío). Login paciente, odontograma y ABM aranceles van a v1.1 fast-follow (IN-01). Bloqueo 2 faltas = 30 días; seña % por práctica configurable por Admin; stack FastAPI + React + Postgres + Redis en Docker.
