# Arquitectura Propuesta

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|--------|--------------|---------|
| Monolito modular por dominios | Backend (routers `turnos`, `pagos`, `notificaciones`, `admin`) | Prioridad escalabilidad (ronda 1): separa para partir a servicios sin pagar microservicios día 1 |
| REST + webhooks idempotentes | MP/Twilio inbound | Pagos y entregas con reintentos exigen idempotencia |
| Job queue + scheduler | Redis (WA T-24hs, expiración `pendiente_sena`) | Desacopla envío programado del request |
| RBAC por rol | JWT claims `rol` + guards por router | 4 roles, sin ABAC en v1 |
| Foto de precio en turno | `Turno.monto_sena` | Cambios de arancel no reescriben historia |
| Soft states + auditoría | `estado`, `raw_webhook`, `Bloqueo.created_by` | Trazabilidad pagos/bloqueos/excepciones |

## Estructura de directorios

```
saas-odontologia/
├── backend/
│   └── app/
│       ├── main.py                 # FastAPI app, routers, middlewares
│       ├── core/                   # config, security (JWT), deps, timezone AR
│       ├── domain/
│       │   ├── turnos/             # modelos, schemas, service (solape, ventanas)
│       │   ├── pagos/              # MP preference, webhook, conciliación
│       │   ├── notificaciones/     # Twilio, email, Calendar, scheduler
│       │   ├── clinica/            # clinic, sillones, prácticas, aranceles
│       │   └── personas/           # pacientes, users, bloqueos
│       ├── infrastructure/
│       │   ├── db/                 # SQLAlchemy base, session, migrations (Alembic)
│       │   ├── queue/              # Redis jobs (recordatorio, expiración)
│       │   └── integrations/       # mp_client, twilio_client, gcal_client
│       └── api/
│           ├── public/             # slots, reservas, gestionar/:token (sin JWT)
│           ├── internal/           # agenda, panel, admin (JWT por rol)
│           └── webhooks/           # mercadopago, twilio (firma, sin JWT)
├── frontend/
│   └── src/
│       ├── features/
│       │   ├── booking/            # slots, reservar, checkout, gestionar/token
│       │   ├── agenda/             # día/semana multi-sillón
│       │   ├── panel-dia/          # jornada recepción
│       │   └── admin/              # aranceles (lectura v1.0), reportes
│       ├── shared/                 # api-client, ui mobile-first, timezone
│       └── pages/ + router         # públicas vs protegidas por rol
├── docker-compose.yml              # api + postgres + redis (+ worker)
└── knowledge-base/
```

## Seguridad

- Autenticación: JWT Bearer para panel interno; rutas públicas sin JWT (con `manage_token` unguessable para gestión); webhooks con firma MP/Twilio, sin JWT.
- Autorización: guards por rol (`recepcion`, `odonto`, `admin`; `paciente` en v1.1); odontólogo confinado a su `odontologo_id`.
- Validación de input: schemas Pydantic (teléfono E.164 AR, DNI, ventanas 12hs, rangos fecha); 409 ante solape con mensaje accionable.
- Secrets management: solo env vars / secret store; nunca en repo. Claves MP/Twilio/JWT rotables.

## Variables de entorno

| Variable | Descripción | Ejemplo | Sensible |
|----------|-------------|---------|----------|
| `DATABASE_URL` | DSN PostgreSQL | `postgresql+psycopg://user:pass@db:5432/turnos` | Y |
| `REDIS_URL` | Cola/scheduler | `redis://redis:6379/0` | N |
| `JWT_SECRET` | Firma JWT | `changeme-32+` | Y |
| `JWT_EXPIRES_MIN` | Expiración JWT | `480` | N |
| `TZ_CLINICA` | Timezone negocio | `America/Argentina/Buenos_Aires` | N |
| `MP_ACCESS_TOKEN` | Credencial Mercado Pago | `APP_USR-...` | Y |
| `MP_WEBHOOK_SECRET` | Firma webhook MP | `...` | Y |
| `MP_TTL_MIN` | Expiración `pendiente_sena` | `30` | N |
| `TWILIO_SID` / `TWILIO_TOKEN` | Credencial Twilio | `AC...` | Y |
| `TWILIO_WA_FROM` | Número WA transparente | `whatsapp:+54911...` | N |
| `GCAL_CALENDAR_ID` | Calendario respaldo | `clinica@group.calendar...` | N |
| `SMTP_URL` | Email respaldo | `smtp://user:pass@host:587` | Y |
| `FRONTEND_URL` | Links en WA/email | `https://turnos.clinica.com.ar` | N |
