# Visión y Objetivos

## Propósito del sistema

Eliminar la coordinación por WhatsApp/papel en consultorios odontológicos chicos y medianos de Argentina, que hoy genera dobles reservas, ausentismo sin seña y horas perdidas confirmando turnos manualmente.

SaaS de turnos odontológicos mobile-first: el paciente reserva online 24/7 sin login obligatorio, deja seña en % por Mercado Pago y recibe recordatorio por WhatsApp 24hs antes; recepción gestiona una agenda multi-sillón sin solapes y un panel del día.

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|-------|--------------------|-----------------------|
| Paciente | Reservar 24/7 desde el celular sin fricción (sin login obligatorio) | Pagar seña online, cancelar/reprogramar, recibir recordatorio WA |
| Recepcionista | Ubicar turnos sin solapar sillón ni odontólogo | Confirmar, cancelar/reprogramar, ver panel del día |
| Odontólogo | Ver su día y sus pacientes sin depender de recepción | (v1.1) Cargar odontograma / historia clínica |
| Admin clínica | Cobrar seña % configurable y reducir ausentismo | (v1.1) ABM aranceles; ver reportes de deuda/cobro |

## Alcance v1.0 (MVP lanzable — respuesta 3b)

- Reserva online 24/7 sin login obligatorio.
- Agenda multi-sillón vista día/semana sin solape por sillón ni odontólogo.
- Cancelar/reprogramar con liberación de horario (reglas RN-RES-*).
- Panel recepción del día.
- Seña en % por Mercado Pago REAL (no simulada), % según tipo de práctica, configurable por Admin.
- Recordatorio WhatsApp REAL 24hs antes, un solo envío, proveedor Twilio.

## v1.1 fast-follow (explícitamente fuera del corte lanzable)

Por decisión de ronda 1 (3b), lo siguiente NO entra en el MVP lanzable pero es el fast-follow inmediato:

- Login paciente (opcional para reservar, requerido para historial).
- Odontograma + historia clínica (lectura y carga básica).
- ABM aranceles/nomenclador por Administrador (en v1.0 se usa seed/config inicial; ver IN-01 en `10_preguntas_abiertas.md`).

## Fuera de alcance

- Obra social / nomenclador automático (v2).
- Facturación ARCA (v2).
- Liquidaciones por profesional (v2).
- Portal post-tratamiento y recordatorios de control (v2).
- Multi-sede / multi-sucursal (explícitamente fuera de v1; el modelo lleva `clinic_id` desde día 1 solo como preparación, ver `09_decisiones_y_supuestos.md`).

## Métricas de éxito

- Ausentismo (no-show) mensual a la baja tras activar seña + WA.
- % de reservas creadas fuera de horario de recepción (uso real del 24/7).
- Tiempo de confirmación manual por turno (objetivo: tender a cero en turnos con seña pagada).
- Tasa de abandono en checkout de seña MP (riesgo de fricción — ver `09_decisiones_y_supuestos.md`).
