# Decisiones y Supuestos

## Decisiones documentadas

### DD-01 — Stack dado (Python/FastAPI + React/TS/Vite + Postgres + Redis + Docker)
**Decisión**: stack obligatorio según Discovery punto 9.
**Contexto**: restricción "dada de arriba" (P4).
**Alternativas consideradas**: Node/Nest, Next.js fullstack, MySQL.
**Justificación**: decisión del usuario; además FastAPI + Postgres + Redis cubre turnos concurrentes, webhooks idempotentes y jobs T-24hs.
**Trade-offs aceptados**: equipo debe cubrir dos codebases (backend + SPA).

### DD-02 — Prioridad CALIDAD: escalabilidad sobre velocidad/costo
**Decisión**: monolito modular con fronteras por dominio desde día 1 (ronda 1, respuesta 4).
**Contexto**: P5 — había que elegir una prioridad.
**Alternativas consideradas**: monolito plano rápido; microservicios día 1.
**Justificación**: multi-sillón + pagos + jobs exigen fronteras claras; partir después es barato si los dominios ya están separados.
**Trade-offs aceptados**: más andamiaje inicial, entrega un poco más lenta.

### DD-03 — MVP lanzable 3b (reserva + agenda + seña MP REAL + WA REAL; login/odontograma/ABM → v1.1)
**Decisión**: el corte lanzable incluye solo reserva 24/7 + agenda multi-sillón + cancel/reprog + panel día + seña % MP real + WA 24hs real (ronda 1, respuesta 3b).
**Contexto**: P2 — definir qué es "lanzable" para evitar scope creep.
**Alternativas consideradas**: Discovery punto 5 pedía login + odontograma + ABM en v1.
**Justificación**: lo que reduce ausentismo y libera recepción es reservar+pagar+recordar; login/odontograma/ABM no bloquean ese valor.
**Trade-offs aceptados**: discrepancia con Discovery (ver IN-01 en `10_preguntas_abiertas.md`); aranceles v1.0 solo lectura+seed.

### DD-04 — Bloqueo por 2 faltas = 30 días
**Decisión**: 2 ausencias → bloqueo de reserva 30 días (ronda 1, respuesta 4; cierra pregunta abierta de Discovery).
**Contexto**: Discovery punto 7/11 dejaba duración a definir.
**Alternativas consideradas**: 7/15/60 días; bloqueo solo con seña perdida.
**Justificación**: 30 días es disuasivo sin expulsar pacientes de clínica chica/mediana; recepción puede exceptuar auditado.
**Trade-offs aceptados**: puede parecer duro; requiere comunicar política al reservar.

### DD-05 — Seña en % por tipo de práctica, configurable por Admin
**Decisión**: `TipoPractica.sena_pct` editable por Admin; el turno fotografía el monto (ronda 1, respuesta 4; RN-PAGO-01/02).
**Contexto**: Discovery 11 ya había resuelto "% vs fija" → %.
**Alternativas consideradas**: seña fija global; % global único.
**Justificación**: una limpieza no arriesga lo mismo que una endodoncia; el % por práctica calibra fricción vs protección.
**Trade-offs aceptados**: seed inicial de % exige criterio clínico-comercial (ver pregunta P-Alta-02 en `10_preguntas_abiertas.md`).

### DD-06 — `clinic_id` desde día 1 aunque v1 sea 1 clínica
**Decisión**: todas las tablas de negocio llevan `clinic_id` (ronda 1: supuesto a fijar).
**Contexto**: v1 = 1 clínica, multi-sede explícitamente fuera.
**Alternativas consideradas**: modelar sin `clinic_id` y migrar en v2.
**Justificación**: el costo hoy es una columna+índice; re-modelar multi-sede después es migración dolorosa.
**Trade-offs aceptados**: filtros `clinic_id` omnipresentes; sin feature multi-sede real.

### DD-07 — WhatsApp vía Twilio, número transparente
**Decisión**: proveedor Twilio para confirmación + recordatorio 24hs (ronda 1, respuesta 4; cierra Meta-vs-Twilio de Discovery).
**Contexto**: Discovery punto 8/11 dejaba proveedor a definir.
**Alternativas consideradas**: Meta Cloud API directa.
**Justificación**: Twilio acelera plantillas/aprobación/soporte en AR con presupuesto acotado; número transparente de la clínica.
**Trade-offs aceptados**: costo por mensaje + riesgo de bloqueo si hay spam (ver `12_whatsapp_twilio.md`).

## Supuestos inferidos

### SU-01 — Adopción online con seña
**Suposición:** los pacientes preferirán reservar online y pagar seña % sin abandonar por fricción ni refugiarse en WhatsApp directo.
**Origen**: riesgo declarado en Discovery punto 10, no validado con usuarios.
**Riesgo si es falso**: checkout con abandono alto, doble canal (online + WA manual) y dobles reservas.
**Cómo validar**: piloto 2-4 semanas midiendo abandono MP + % reservas fuera de horario + encuesta post-turno.

### SU-02 — `clinic_id` día 1 no se percibe como multi-sede
**Suposición:** filtrar todo por `clinic_id` no tienta a exponer UI multi-sede en v1.
**Origen**: DD-06 (decisión de modelado).
**Riesgo si es falso**: scope creep multi-sede en sprint 2.
**Cómo validar**: contrato de API v1.0 sin endpoints multi-clínica; test de alcance en roadmap.

### SU-03 — % seña por práctica calibrable con seed
**Suposición:** Admin puede fijar un seed inicial de `sena_pct` por práctica sin dato histórico, y ajustarlo con reportes.
**Origen**: DD-05 + Discovery 11.
**Riesgo si es falso**: % demasiado alto frena conversión o demasiado bajo no frena ausentismo.
**Cómo validar**: reporte quincenal ausentismo vs % por práctica; ajustar en v1.1 con ABM.

### SU-04 — Twilio entrega T-24hs con un envío suficiente
**Suposición:** WA Cloud API vía Twilio con número transparente entrega a tiempo en AR y un solo recordatorio 24hs alcanza (sin refuerzo 2hs).
**Origen**: DD-07 + Discovery (24hs, un envío).
**Riesgo si es falso**: costos/bloqueos o pacientes que igual olvidan (ventana 24hs larga).
**Cómo validar**: medir `entregado` Twilio + correlación recordatorio→asistencia; evaluar refuerzo 2hs solo si datos lo piden (v1.1).
