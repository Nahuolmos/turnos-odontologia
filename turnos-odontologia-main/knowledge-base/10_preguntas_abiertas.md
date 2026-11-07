# Preguntas Abiertas

## Inconsistencias detectadas

### IN-01 — Discovery punto 5 (login + odontograma + ABM "necesarias" en v1) vs ronda 1 respuesta 3b (van a v1.1 fast-follow)
**Documento A dice** (`discovery/discovery.md` punto 5 + `state.discovery.funcionalidades_necesarias`): login paciente opcional, odontograma + historia clínica y ABM aranceles son funcionalidades necesarias en v1.
**Documento B dice** (ronda 1, respuesta 3b — decisión posterior y de mayor autoridad): el MVP lanzable es reserva 24/7 + agenda multi-sillón + cancel/reprog + panel día + seña % MP real + WA 24hs real; login + odontograma + ABM quedan como v1.1 fast-follow.
**Impacto**: si roadmap-generator toma Discovery literal, planifica 3 épicas de más en el corte lanzable (auth pacientes, odontograma, ABM) y retrasa el go-live que la 3b quiso acelerar.
**Resolución propuesta**: vale la 3b (decisión explícita posterior). Esta KB ya lo refleja: épicas 1-4 = MVP, épica 5 (US-010/011/012) = v1.1; `05` marca RN-ADMIN-02; `04` marca aranceles lectura/seed en v1.0. Roadmap debe planificar v1.0 (US-001..009) y v1.1 (US-010..012) como oleadas separadas.

## Preguntas abiertas (priorizadas)

| Prioridad | Pregunta | Bloquea | Decisor |
|-----------|----------|---------|---------|
| Alta | % seña inicial por tipo de práctica (seed v1.0 sin ABM): ¿qué % para limpieza / arreglo / endodoncia / extracción / ortodoncia? | Sprint 1 (seed + RN-PAGO-02) | Admin clínica |
| Alta | TTL de `pendiente_sena` (propuesto 30 min en RN-RES-04): ¿30 min o más? | Sprint 1 (Flujo 1, job expiración) | Producto + Admin |
| Alta | Horarios de atención por sillón/odontólogo: ¿tabla propia o config? ¿franjas y tolerancias? | Sprint 1 (slots US-001, ERD seed) | Admin clínica |
| Media | Número WA transparente: ¿línea existente a portar o línea nueva Twilio? Costo/mes aceptado | Sprint 2 (Twilio setup) | Admin clínica |
| Media | Conciliación contable seña (contracargos, reembolsos parciales): ¿criterio fiscal ARCA-friendly aunque ARCA sea v2? | Conciliación US-008 | Admin + contador |
| Media | Excepción a bloqueo 30d por recepción: ¿tope de excepciones/mes? ¿doble aprobación? | Panel día US-005 | Admin clínica |
| Baja | Refuerzo WA 2hs además de 24hs: ¿se mide primero o se añade directo en v1.1? | v1.1 | Producto (con datos SU-04) |
| Baja | Google Calendar: ¿un calendario por sillón o por odontólogo? ¿sync uni o bidireccional? | Respaldo US-009 | Equipo técnico |

Resueltas en ronda 1 (ya cerradas, no re-preguntar): `system_type=web_app` (1a), `scale=team` (2a), MVP 3b, prioridad escalabilidad, bloqueo 30 días, seña % por práctica, proveedor Twilio.
