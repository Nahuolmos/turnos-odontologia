# Discovery — SaaS Odontología (turnos-odontologia)

**Fecha**: 2026-10-07
**Fuentes investigadas**: relevamiento 18 sistemas AR/Latam/Global (2026-10-06, re-verificación estricta URL por URL) — ver punto 4. Notas en `discovery/sources/` pendientes de volcado detallado.

## 1. Problema que resuelve

Los consultorios odontológicos chicos y medianos coordinan turnos por WhatsApp/papel, lo que genera dobles reservas, ausentismo sin seña y tiempo perdido confirmando manualmente cada turno.

## 2. Usuarios / roles

- **Paciente**: reserva online 24/7, login opcional desde v1 para ver historial. Sin login obligatorio para no frenar conversión.
- **Recepcionista**: ve agenda multi-sillón día/semana, confirma, cancela y reprograma.
- **Odontólogo**: ve su agenda por sillón, su día y sus pacientes.
- **Admin clínica**: configura aranceles/nomenclador, precios, usuarios y ve reportes. Una sola clínica en v1 (sin multi-sede).

## 3. Casos de uso

1. Como paciente, quiero ver horarios libres y reservar 24/7 para no tener que escribir por WhatsApp.
2. Como recepcionista, quiero ver la agenda multi-sillón día/semana para ubicar turnos sin solapar sillón ni odontólogo.
3. Como paciente, quiero pagar seña (%) por Mercado Pago y recibir recordatorio por WhatsApp 24hs antes para no perder el turno.
4. Como recepcionista, quiero cancelar/reprogramar liberando el horario según reglas de anticipación.
5. Como odontólogo, quiero ver mi día y la historia/odontograma de mi paciente.
6. Como admin, quiero configurar aranceles y ver quién debe qué.

## 4. Competidores / soluciones existentes

Relevamiento A-D de 18 sistemas con matriz ponderada y re-verificación estricta (vara: URL que no demuestra lo citado va a "No evidenciado").

| Competidor | Problema que resuelve | Pricing observado | Diferenciadores / nota evidencia |
|---|---|---|---|
| Fresha | Turnos belleza/barbería con pagos y CRM | Planes ARS 8k / 5,3k observados | Referencia UX rubro belleza, no odontológico puro |
| Historia Dental | Gestión odontológica Latam | Mini 25,5k / Básico 49,7k / Premium 59,6k / Clínica 110,5k COP (precios nuevos más bajos) | Competidor directo odontológico |
| DentalSoft | Agenda odontológica | Sin precio público verificado | URL /agenda-odontologica redirige a demo; canónica válida /funcionalidades/agenda-odontologica (sí evidencia agenda). Pendiente decidir si canónica se acepta o va a demo |
| Nimbo | Gestión salud | Sin precios oficiales | No evidencia pricing |
| Tab32 | Dental cloud EE.UU. | N/D | Online Booking en "Coming soon" — no evidencia reserva real |
| Bilog (demo turnos) | Demo turnos | N/D | Demo SPA sin SSR — no sirve como evidencia dura |
| Dentaly | Directorio/contenido dental | N/D | SPA vacía — no evidencia funcional |
| Doctolib | Reserva médica | N/D | Agenda devuelve 403 en verificación — no evidencia |

**Notas**: ningún competidor AR combina multi-sillón + 24/7 sin login obligatorio + seña Mercado Pago (%) + WhatsApp transparente + obra social/nomenclador + ARCA + liquidaciones. Ese es el hueco.

## 5. Funcionalidades necesarias

- Reserva online 24/7 sin login obligatorio (login opcional desde v1 para historial).
- Agenda multi-sillón vista día/semana para recepción, sin solape por sillón ni odontólogo.
- Cancelar/reprogramar con liberación de horario.
- Panel recepción del día.
- Seña (%) por Mercado Pago en v1.
- Recordatorio automático por WhatsApp 24hs antes (un solo envío).
- Login paciente desde v1 (opcional para reservar, requerido para historial).
- Odontograma + historia clínica en v1 (lectura y carga básica).
- ABM aranceles/nomenclador por Administrador.

## 6. Funcionalidades opcionales

- Obra social / nomenclador automático.
- Facturación ARCA.
- Liquidaciones por profesional.
- Portal post-tratamiento y recordatorios de control.
- Multi-sede / multi-sucursal (explícitamente fuera de v1).

## 7. Reglas de negocio

- Un sillón/odontólogo no puede tener dos turnos superpuestos.
- Cancelación mínima 12hs de anticipación.
- 1 reprogramación sin perder seña; si cancela tarde, seña (%) no reembolsable.
- Bloqueo si el paciente falta 2 veces (a definir duración del bloqueo en KB).
- Seña en % del tratamiento (monto exacto por tipo de práctica, configura Admin).

## 8. Integraciones

- Mercado Pago (seña %) — obligatoria v1.
- WhatsApp (confirmación/recordatorio transparente, vía proveedor Meta/Twilio a definir en KB) — obligatoria v1.
- Google Calendar + email como respaldo — v1.
- Ninguna integración OS/ARCA obligatoria para v1 (decisión consciente, van a v2).

## 9. Restricciones

- Stack obligatorio (dado por usuario):
  - Backend: Python, FastAPI, JWT autenticación, SQLAlchemy ORM, PostgreSQL, Redis para async, Docker / Docker Compose.
  - Frontend: React, TypeScript, Vite.
- 1 clínica en v1, sin multi-sede.
- Mobile-first: la mayoría reserva desde el teléfono.
- Presupuesto acotado clínica chica/mediana (no cadena en v1).

## 10. Riesgos

- **Supuesto sin probar**: que los pacientes prefieran reservar online y pagar seña (%) sin fricción — no validado con usuarios reales. Riesgo de adopción: siguen prefiriendo WhatsApp por costumbre y abandonan ante la seña.
- **Riesgo operativo**: si recepción no actualiza disponibilidad, el sistema muestra huecos que no existen.
- **Riesgo WhatsApp**: costos/bloqueos proveedor (Meta/Twilio), número transparente.
- **Riesgo MP**: fricción pago seña, contracargos, conciliación.

## 11. Preguntas abiertas

Resueltas en esta ronda (2026-10-07):
- ¿Odontograma en v1 o v2? → En v1.
- ¿Quién configura aranceles? → Administrador.
- ¿Seña fija o %? → %.
- ¿Recordatorio 24hs o 2hs? → 24hs antes, un envío.
- ¿Multi-sede día 1 o una clínica? → 1 clínica.
- ¿Login paciente? → Login opcional desde v1 (reserva sin login para conversión + login para historial).

Pendiente para KB/diseño (no bloquea Discovery):
- Duración exacta bloqueo por 2 faltas.
- % seña por tipo de práctica.
- Proveedor WhatsApp final (Meta directo vs Twilio).
