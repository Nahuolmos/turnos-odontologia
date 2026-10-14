# Actores y Roles

## Actores del sistema

| Actor | Descripción | Cómo interactúa |
|-------|-------------|-----------------|
| Paciente (visitante) | Persona que reserva sin cuenta | Rutas públicas: slots, reservar, pagar seña, cancelar/reprogramar con token |
| Paciente (registrado, v1.1) | Paciente con login para ver historial | Login JWT opcional; reserva igual que visitante |
| Recepcionista | Gestiona agenda multi-sillón y panel del día | SPA con JWT rol `recepcion`; agenda día/semana, cancela/reprograma |
| Odontólogo | Ve su día y sus pacientes | SPA con JWT rol `odonto`; vista filtrada por su sillón/usuario; (v1.1) odontograma |
| Admin clínica | Configura % seña por práctica, aranceles, usuarios; ve reportes | SPA con JWT rol `admin`; 1 clínica en v1 |

## RBAC — Matriz de permisos

| Rol | Turnos | Agenda multi-sillón | Panel día | Pagos/señas | Aranceles | Usuarios | Reportes |
|-----|--------|---------------------|-----------|-------------|-----------|----------|----------|
| Paciente (público/token) | Crear propio, cancelar/reprogramar propio (con token + ventana 12hs) | Ver slots libres (solo huecos) | — | Pagar su seña | Ver precios vigentes | — | — |
| `recepcion` | CRUD turnos + confirmar | Total | Total | Ver estado, reenviar link pago | Lectura (v1.0) | — | Día/cobro |
| `odonto` | Ver/confirmar propios | Propia (su sillón) | Propio | Ver estado propios | Lectura | — | Propios |
| `admin` | Total | Total | Total | Total + config % seña | Lectura v1.0 / CRUD v1.1 | CRUD | Total |

- RBAC simple rol → permisos (no ABAC en v1).
- Sin herencia entre roles; `admin` no hereda, tiene permisos explícitos totales.
- Reserva pública sin auth emite token de gestión (`manage_token`) para cancelar/reprogramar sin cuenta.

## Rutas públicas

- `GET /` landing + buscador de slots.
- `GET /reservar` (slots + formulario + checkout MP).
- `GET /gestionar/:token` (ver/cancelar/reprogramar con `manage_token`).
- `POST /api/public/*` (slots, reservas, cancelar, reprogramar).
- `POST /api/webhooks/mercadopago` (webhook MP; firma validada, no JWT).
- Login (`/login`) existe desde v1.0 solo para roles internos; login paciente llega en v1.1.
