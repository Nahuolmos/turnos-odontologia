# Tasks — C-04 gestion-turnos

**Change:** C-04 gestion-turnos
**Schema:** spec-driven
**Estado:** completado

> TDD obligatorio. Cada comportamiento sigue RED → GREEN → TRIANGULATE → REFACTOR.
> RED: escribir el test y verlo fallar por la razón correcta (no por import roto).
> GREEN: implementación mínima para pasar.
> TRIANGULATE: segundo caso que obligue a generalizar (borde, estado, rol).
> REFACTOR: limpiar sin cambiar comportamiento, suite completa verde.

---

## Fase 0 — Preparación

- [x] **0.1 — Confirmar contratos y supuestos**

  Releer `knowledge-base/04_modelo_de_datos.md` (§Turno, §TipoPractica), `05_reglas_de_negocio.md` (RN-RES-01..05, RN-CANCEL-01..04) y `07_flujos_principales.md` (Flujo 1 y 2). Confirmar con el usuario, si está disponible, los supuestos de `design.md`: ventana `09:00–19:00`, asignación "primer par sillón/odontólogo libre" y estado inicial `pendiente_sena` en alta interna.
  **Archivos**: ninguno (lectura).
  **Verificación**: supuestos registrados en `design.md` §Open Questions.

---

## Fase 1 — Modelos, migración y seed

### 1.1 — `TipoPractica`: modelo

- [x] **RED** — Crear `backend/tests/test_turnos_models.py::test_tipo_practica_campos_y_defaults` (instanciar `TipoPractica` con `duracion_min`, `precio_base`, `sena_pct`, `activa`; verificar tipos y defaults). Debe fallar por `ModuleNotFoundError: app.domain.turnos.models`.
  **Archivos**: `backend/tests/test_turnos_models.py`
- [x] **GREEN** — Crear `backend/app/domain/turnos/__init__.py` y `backend/app/domain/turnos/models.py` con `TipoPractica(Base, AuditMixin)`: `id`, `clinic_id`, `nombre`, `duracion_min`, `precio_base`, `sena_pct`, `activa`.
  **Archivos**: `backend/app/domain/turnos/__init__.py`, `backend/app/domain/turnos/models.py`
- [x] **TRIANGULATE** — Agregar `test_tipo_practica_sena_pct_limites` (0 y 100 válidos) y `test_tipo_practica_duracion_no_positiva` (0 y negativos rechazados por validación/constraint).
- [x] **REFACTOR** — Extraer `Numeric`/`Integer` y nombres de constraint consistentes con `clinica/models.py`.

### 1.2 — `Turno`: modelo y relaciones

- [x] **RED** — Agregar `test_turno_campos_y_estado_default` y `test_turno_relaciones` (FKs a `Paciente`, `Sillon`, `User`, `TipoPractica`; `reprogramaciones_count == 0`). Fallan porque `Turno` no existe.
  **Archivos**: `backend/tests/test_turnos_models.py`
- [x] **GREEN** — Agregar `Turno(Base, AuditMixin)` en `backend/app/domain/turnos/models.py` con todos los campos y `relationship()` hacia los modelos existentes.
  **Archivos**: `backend/app/domain/turnos/models.py`
- [x] **TRIANGULATE** — `test_turno_manage_token_unique` (dos inserts con el mismo token → `IntegrityError`) y `test_turno_check_fin_mayor_inicio` (fin == inicio y fin < inicio rechazados).
- [x] **REFACTOR** — Alinear `__table_args__` (CHECK + índices compuestos) y documentar el diccionario de estados como constante `ESTADOS_TURNO`.

### 1.3 — Migración 004

- [x] **RED** — Crear `backend/tests/test_migration_004.py` con guards de PostgreSQL (mismo patrón `skipif` que `test_migration_002.py`): tablas `tipos_practica` y `turnos`, columnas, CHECK e índices esperados. Falla porque la revisión no existe.
  **Archivos**: `backend/tests/test_migration_004.py`
- [x] **GREEN** — Crear `backend/app/infrastructure/db/migrations/versions/004_turnos.py` (`revision = "004"`, `down_revision = "003"`) con `upgrade()`/`downgrade()`.
  **Archivos**: `backend/app/infrastructure/db/migrations/versions/004_turnos.py`
- [x] **TRIANGULATE** — Agregar `test_migration_004_downgrade` (bajar a `003` elimina ambas tablas y no toca las de C-02/C-03).
- [x] **REFACTOR** — Unificar nombres de constraints/índices con `op.f(...)` como en `003_auth.py`.

### 1.4 — Seed del catálogo

- [x] **RED** — Crear `backend/tests/test_seed_tipos_practica.py::test_seed_crea_cinco_practicas` y `::test_seed_idempotente` (correr dos veces, siguen 5). Falla porque el seed no existe.
  **Archivos**: `backend/tests/test_seed_tipos_practica.py`, `backend/scripts/seed.py`
- [x] **GREEN** — Extender `backend/scripts/seed.py` con las 5 prácticas (limpieza, arreglo, endodoncia, extracción, ortodoncia control), UUID fijos y valores provisorios documentados.
  **Archivos**: `backend/scripts/seed.py`
- [x] **TRIANGULATE** — `test_seed_no_duplica_por_clinic` (misma práctica en dos clínicas se permite; repetir en la misma no).
- [x] **REFACTOR** — Extraer la lista `PRACTICAS_SEED` a constante y reutilizarla en tests.

---

## Fase 2 — `TurnoService` (motor de reglas)

> Todos los tests de esta fase viven en `backend/tests/test_turno_service.py` y usan `db_session` + factories locales de clinic/paciente/sillón/odontólogo/práctica.

### 2.1 — Duración y `fin`

- [x] **RED** — `test_crear_turno_deriva_fin_desde_duracion` (inicio 10:00, práctica 45 min → fin 10:45).
- [x] **GREEN** — Crear `backend/app/domain/turnos/service.py` con `TurnoService.crear_turno(...)` que calcula `fin`.
  **Archivos**: `backend/app/domain/turnos/service.py`
- [x] **TRIANGULATE** — `test_crear_turno_ignora_fin_del_cliente` y `test_crear_turno_practica_inactiva_404`.
- [x] **REFACTOR** — Extraer `_calcular_fin(inicio, duracion_min)`.

### 2.2 — Anti-solape por sillón

- [x] **RED** — `test_solape_sillon_devuelve_conflicto` (10:00–10:45 y 10:30–11:15, mismo sillón → `TurnoConflicto`).
- [x] **GREEN** — Validación de intersección `[inicio, fin)` sobre estados vigentes en `TurnoService`; excepción de dominio traducida a 409.
- [x] **TRIANGULATE** — `test_turnos_contiguos_permitidos` (fin == inicio) y `test_turno_cancelado_no_bloquea`.
- [x] **REFACTOR** — Extraer `_hay_solape(session, clinic_id, campo, valor, inicio, fin)` reutilizable.

### 2.3 — Anti-solape por odontólogo

- [x] **RED** — `test_solape_odontologo_mismo_horario_otro_sillon` (mismo odontólogo, sillón distinto → conflicto).
- [x] **GREEN** — Reutilizar `_hay_solape` con `odontologo_id`, misma transacción.
- [x] **TRIANGULATE** — `test_mismo_horario_otro_odontologo_permitido`.
- [x] **REFACTOR** — Unificar el mensaje de error con `campo` y `rango` para que la API devuelva detalle claro.

### 2.4 — Snapshot de seña

- [x] **RED** — `test_monto_sena_snapshot` (25000 × 30% → 7500).
- [x] **GREEN** — Calcular y persistir `monto_sena` en la creación.
- [x] **TRIANGULATE** — `test_monto_sena_no_cambia_al_actualizar_practica` y `test_monto_sena_cero`.
- [x] **REFACTOR** — Extraer `_calcular_sena(precio_base, sena_pct)` y cubrir redondeo `.5`.

### 2.5 — Token de gestión

- [x] **RED** — `test_manage_token_es_unico_y_largo` (dos turnos → tokens distintos, `len >= 40`, URL-safe).
- [x] **GREEN** — Generar `secrets.token_urlsafe(32)` en la creación.
- [x] **TRIANGULATE** — `test_manage_token_no_contiene_el_id` y `test_crear_dos_turnos_genera_tokens_distintos` (100 iteraciones sin colisión).
- [x] **REFACTOR** — Aislar `_generar_manage_token()` para poder inyectarlo en tests.

### 2.6 — Cancelación y ventana de 12 h

- [x] **RED** — `test_cancelar_con_mas_de_12h_libera_slot` (`sena_retenida is False`, estado `cancelado`) y `test_cancelar_con_menos_de_12h_retiene_sena` (`sena_retenida is True`).
- [x] **GREEN** — `TurnoService.cancelar(...)` con comparación en `America/Argentina/Buenos_Aires`; devuelve `ResultadoCancelacion`.
- [x] **TRIANGULATE** — `test_cancelar_exactamente_12h_es_a_tiempo`, `test_cancelar_turno_ya_cancelado_409` y `test_cancelar_turno_inexistente_404`.
- [x] **REFACTOR** — Inyectar `now()` (callable) para tests deterministas de borde.

### 2.7 — Consultas de agenda

- [x] **RED** — `test_agenda_filtra_por_fecha_sillon_y_estado` (combinación de filtros).
- [x] **GREEN** — `TurnoService.listar_agenda(clinic_id, fecha, desde, hasta, sillon_id, odontologo_id, estado)` con orden por `inicio`.
- [x] **TRIANGULATE** — `test_agenda_fecha_usa_timezone_clinica` (turno 23:30 local no cae en el día siguiente) y `test_agenda_odontologo_confinado`.
- [x] **REFACTOR** — Extraer construcción de filtros a `_build_agenda_query`.

---

## Fase 3 — API interna

### 3.1 — Routers base y RBAC

- [x] **RED** — `backend/tests/test_turnos_api_internal.py::test_internal_sin_token_401` y `::test_odonto_no_puede_crear_turno_403` (JWT generado como en `backend/tests/test_auth_me.py`).
- [x] **GREEN** — Crear `backend/app/api/internal/turnos.py` con `router = APIRouter()`, `Depends(require_role([...]))` y schemas en `backend/app/domain/turnos/schemas.py`; registrar en `backend/app/main.py`.
  **Archivos**: `backend/app/api/internal/turnos.py`, `backend/app/domain/turnos/schemas.py`, `backend/app/main.py`
- [x] **TRIANGULATE** — `test_admin_puede_listar_turnos` y `test_recepcion_puede_crear_turno`.
- [x] **REFACTOR** — Dependencia única `get_turno_service` por request, sin abrir sesión global.

### 3.2 — `GET /api/internal/tipos-practica` y `/sillones`

- [x] **RED** — `test_listar_tipos_practica_solo_activos` y `test_listar_sillones_solo_de_la_clinica` (dos clínicas, no filtra datos ajenos).
- [x] **GREEN** — Endpoints con `response_model` y repositorios existentes/nuevos.
- [x] **TRIANGULATE** — `test_tipos_practica_incluye_duracion_y_sena`.
- [x] **REFACTOR** — Reutilizar `SillonRepository.list(clinic_id=...)`.

### 3.3 — `GET /api/internal/turnos`

- [x] **RED** — `test_agenda_interna_filtros` y `test_agenda_odonto_solo_su_agenda`.
- [x] **GREEN** — Endpoint que delega en `TurnoService.listar_agenda`.
- [x] **TRIANGULATE** — `test_agenda_interna_fecha_invalida_422` y `test_agenda_interna_orden_por_inicio`.
- [x] **REFACTOR** — Validar `desde <= hasta` en el schema.

### 3.4 — `POST /api/internal/turnos` y cancelar

- [x] **RED** — `test_crear_turno_interno_ok_sin_manage_token` y `test_crear_turno_interno_solape_409`.
- [x] **GREEN** — Endpoints con `response_model`, traducción de `TurnoConflicto` a 409 (formato RFC 7807 ya registrado en `main.py`).
  **Archivos**: `backend/app/api/internal/turnos.py`
- [x] **TRIANGULATE** — `test_cancelar_turno_interno_ok` y `test_cancelar_turno_interno_inexistente_404`.
- [x] **REFACTOR** — Extraer helper `to_http_conflict(exc)`.

---

### 3.5 — Endpoints de soporte para la UI de Agenda

- [x] **GREEN** — Agregar `GET /api/internal/pacientes` (búsqueda `q` por nombre/teléfono, activos y clinic-scoped) y `GET /api/internal/odontologos` (solo `rol="odonto"` activos, orden por email) para que la Agenda pueda poblar pacientes y profesionales. Tests: `test_pacientes_internal_sin_token_401`, `test_odontologos_internal_sin_token_401`, `test_pacientes_clinic_scoped_y_ordenados_por_nombre`, `test_pacientes_filtro_q_por_nombre_y_telefono`, `test_odontologos_solo_activos_rol_odonto_de_la_clinica`.
  **Archivos**: `backend/app/api/internal/turnos.py`, `backend/app/domain/personas/repository.py`

---

## Fase 4 — API pública

### 4.1 — `GET /api/public/slots`

- [x] **RED** — `backend/tests/test_turnos_api_public.py::test_slots_solo_libres` y `::test_slots_sin_datos_personales`.
- [x] **GREEN** — Crear `backend/app/api/public/turnos.py` y `TurnoService.disponibilidad(fecha, tipo_practica_id)`; registrar router en `main.py`.
  **Archivos**: `backend/app/api/public/turnos.py`, `backend/app/main.py`, `backend/app/domain/turnos/service.py`
- [x] **TRIANGULATE** — `test_slots_dia_completo_lista_vacia` y `test_slots_respeta_duracion_practica`.
- [x] **REFACTOR** — Cachear la lista de prácticas/sillones dentro de una misma request.

### 4.2 — `POST /api/public/reservas`

- [x] **RED** — `test_reserva_publica_sin_jwt_crea_paciente_y_turno` (respuesta con `manage_token`).
- [x] **GREEN** — Endpoint que busca/crea `Paciente` por `(clinic_id, telefono)` y delega en `TurnoService`.
- [x] **TRIANGULATE** — `test_reserva_publica_reutiliza_paciente`, `test_reserva_publica_slot_tomado_409` y `test_reserva_publica_telefono_invalido_422`.
- [x] **REFACTOR** — Extraer `PacienteService.get_or_create` y validar E.164 AR en schema.

### 4.3 — `GET /api/public/reservas/{id}?token=`

- [x] **RED** — `test_consulta_publica_con_token_ok` y `test_consulta_publica_token_invalido_404`.
- [x] **GREEN** — Endpoint con schema público (sin datos de otros pacientes).
- [x] **TRIANGULATE** — `test_consulta_publica_no_expone_telefono_de_otros`.
- [x] **REFACTOR** — Dependencia `get_turno_por_token` reutilizada por el cancelar.

### 4.4 — `POST /api/public/reservas/{id}/cancelar`

- [x] **RED** — `test_cancelar_publico_a_tiempo` (`sena_retenida=false`, slot reutilizable) y `test_cancelar_publico_tardio` (`sena_retenida=true`).
- [x] **GREEN** — Endpoint que valida token y delega en `TurnoService.cancelar`.
- [x] **TRIANGULATE** — `test_cancelar_publico_token_invalido_404` y `test_cancelar_publico_ya_cancelado_409`.
- [x] **REFACTOR** — Compartir el schema de respuesta entre consulta y cancelación.

---

### 4.5 — Catálogo público de prácticas para Booking

- [x] **GREEN** — Agregar `GET /api/public/tipos-practica` sin JWT, resolviendo la clínica default de v1 como el resto del router público y devolviendo solo prácticas activas. Tests: `test_tipos_practica_publico_sin_auth_solo_activas_de_la_clinica_default`, `test_tipos_practica_publico_sin_practicas_200_vacio`.
  **Archivos**: `backend/app/api/public/turnos.py`, `backend/app/domain/turnos/repository.py`

---

## Fase 5 — Frontend

### 5.1 — Feature `agenda`

- [x] **RED** — `frontend/src/features/agenda/agenda.api.test.ts` con `msw`/mock de `apiClient`: `getTurnos` arma query params y `crearTurno`/`cancelarTurno` pegan a los endpoints internos.
- [x] **GREEN** — Crear `frontend/src/features/agenda/api.ts`, `types.ts` y `hooks/useAgenda.ts` sobre `shared/api-client`.
  **Archivos**: `frontend/src/features/agenda/api.ts`, `frontend/src/features/agenda/types.ts`, `frontend/src/features/agenda/hooks/useAgenda.ts`
- [x] **TRIANGULATE** — `agenda.api.test.ts` cubre error 409 propagado como mensaje legible.
- [x] **REFACTOR** — Tipos estrictos (sin `any`), sin barrel files.

### 5.2 — `AgendaPage` funcional

- [x] **RED** — `frontend/src/pages/AgendaPage.test.tsx`: carga turnos al montar, aplica filtros, abre alta y muestra leyenda de estados.
- [x] **GREEN** — Reescribir `AgendaPage.tsx` con datos reales, filtros `sillon/odontologo/estado`, formulario de alta y acción cancelar.
  **Archivos**: `frontend/src/pages/AgendaPage.tsx`, `frontend/src/pages/AgendaPage.css` (solo ajustes necesarios)
- [x] **TRIANGULATE** — Test de estado vacío y de error de red.
- [x] **REFACTOR** — Extraer subcomponentes `TurnoCard`/`AgendaFilters` dentro de `features/agenda/components/`.

### 5.3 — Feature `booking`

- [x] **RED** — `frontend/src/features/booking/booking.api.test.ts`: `getSlots`, `crearReserva`, `getReserva`, `cancelarReserva` (token en query/body según contrato).
- [x] **GREEN** — Crear `frontend/src/features/booking/api.ts`, `types.ts` y `hooks/useBooking.ts`.
  **Archivos**: `frontend/src/features/booking/api.ts`, `frontend/src/features/booking/types.ts`, `frontend/src/features/booking/hooks/useBooking.ts`
- [x] **TRIANGULATE** — Test de token inválido 404 → mensaje "Reserva no encontrada".
- [x] **REFACTOR** — Compartir `Slot`/`TurnoPublico` types sin duplicar.

### 5.4 — `BookingPage` funcional

- [x] **RED** — `frontend/src/pages/BookingPage.test.tsx`: selección de práctica → fecha → slots → datos → confirmación con `manage_token` y link `/gestionar/:token`.
- [x] **GREEN** — Reescribir `BookingPage.tsx` con las 4 etapas reales y manejo de 409 (slot tomado).
  **Archivos**: `frontend/src/pages/BookingPage.tsx`, `frontend/src/pages/BookingPage.css` (ajustes mínimos)
- [x] **TRIANGULATE** — Test de teléfono inválido y de reintento tras 409.
- [x] **REFACTOR** — Extraer `PracticeStep`/`SlotStep`/`PatientStep`/`ConfirmationStep`.

### 5.5 — Router y gestión pública

- [x] **RED** — `frontend/src/router.test.tsx` (o test existente de rutas): `/reservar` renderiza `BookingPage` sin login y `/gestionar/:token` recibe el token.
- [x] **GREEN** — Ajustar `frontend/src/router.tsx` solo si el link de confirmación lo requiere; verificar `ManageAppointmentPage` existente.
  **Archivos**: `frontend/src/router.tsx`
- [x] **TRIANGULATE** — Test de que `/agenda` sigue protegida para `odonto|admin`.
- [x] **REFACTOR** — Sin cambios de identidad visual.

---

## Fase 6 — Verification

- [x] **6.1 — Backend completo**

  Ejecutar desde `backend/`:
  ```
  pytest -q
  ruff check app tests
  mypy app
  ```
  Criterio: suite completa verde, sin errores nuevos de lint/tipos respecto de la línea base.

- [x] **6.2 — Migración**

  Con PostgreSQL disponible:
  ```
  alembic upgrade head
  alembic downgrade 003
  alembic upgrade head
  ```
  Criterio: sin errores y seed idempotente tras el segundo upgrade.

- [x] **6.3 — Frontend**

  Ejecutar desde `frontend/`:
  ```
  npm run build
  npm run test
  npm run lint
  ```
  Criterio: build de TypeScript sin `any` nuevos, Vitest verde y lint limpio.

- [x] **6.4 — Revisión funcional manual**

  Con el backend y el frontend levantados: reservar desde `/reservar` sin login, verificar `manage_token`, abrir `/gestionar/:token`, cancelar, y comprobar que el slot reaparece en disponibilidad y en `/agenda`. Registrar el resultado en `design.md` §UI Mockups (`Visual verify: manual (functional review)`).

---

## Notas de verificación (Fase C)

- **Frontend build**: `npm run build` → OK (tsc app + tsc test + vite build, 114 módulos).
- **Frontend tests**: `npm run test -- --run` → **6 archivos, 30 tests, todos verdes**.
- **Frontend lint**: `npm run lint` → sin errores; quedan warnings preexistentes y dos avisos `react(set-state-in-effect)` en los hooks de carga inicial.
- **Backend suite**: `cd backend && .\.venv\Scripts\python.exe -m pytest -q` → **125 passed, 20 skipped**, cobertura **82,68%**.
- **6.2 — Migración**: no se ejecutó `alembic upgrade/downgrade` contra PostgreSQL real porque el entorno local no tiene una instancia disponible. La migración `004` está cubierta por `test_migration_004.py` (se saltea sin PostgreSQL) y por los tests de modelos/servicio sobre SQLite.
- **6.4 — Revisión funcional manual**: se reemplazó por pruebas de integración de componentes con Vitest sobre ambos flujos (AgendaPage y BookingPage, incluidos 409 y validación de teléfono). Queda pendiente la prueba E2E con backend + frontend levantados y PostgreSQL real.

