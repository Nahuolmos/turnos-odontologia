# Tasks - C-05 motor-reservas-slots-turnos

**Change:** C-05 motor-reservas-slots-turnos
**Schema:** spec-driven
**Estado:** completo

> TDD obligatorio. Cada comportamiento sigue RED -> GREEN -> TRIANGULATE -> REFACTOR.
> RED: escribir el test y verlo fallar por la razón correcta (no por import roto).
> GREEN: implementación mínima para pasar.
> TRIANGULATE: segundo caso que obligue a generalizar (borde, estado, rol).
> REFACTOR: limpiar sin cambiar comportamiento, suite completa verde.

---

## Fase 0 - Línea base y contratos

- [x] **0.1 - Verificar el núcleo heredado de C-04**

  Ejecutar desde `backend/`: `.\.venv\Scripts\python.exe -m pytest -q --no-cov`. Confirmar que el modelo `Turno`, el anti-solape, la disponibilidad y la reserva pública siguen verdes antes de tocar nada.
  **Archivos**: ninguno (lectura).
  **Verificación**: suite base verde (125 passed, 20 skipped al momento de escribir este change).

- [x] **0.2 - Confirmar reglas y supuestos**

  Releer `knowledge-base/05_reglas_de_negocio.md` (RN-RES-04, RN-AUS-01/02), `knowledge-base/07_flujos_principales.md` (Flujo 1) y `knowledge-base/04_modelo_de_datos.md` (§Turno, §Bloqueo). Confirmar que la excepción de recepción queda en C-07 y que el TTL es uniforme.
  **Verificación**: supuestos registrados en `design.md` §Decisions y §Open Questions.

---

## Fase 1 - Bloqueo de 30 días

### 1.1 - Repositorio de bloqueo vigente

- [x] **RED** - Agregar `backend/tests/test_turno_service.py::test_bloqueo_vigente_impide_crear_turno` (crear `Bloqueo` con `desde <= NOW < hasta` y esperar `PacienteBloqueado`). Debe fallar por `ImportError`/`AttributeError` del nuevo error de dominio.
  **Archivos**: `backend/tests/test_turno_service.py`
- [x] **GREEN** - Agregar `BloqueoRepository.get_vigente(clinic_id, paciente_id, now)` en `backend/app/domain/clinica/repository.py` y `PacienteBloqueado` en `backend/app/domain/turnos/service.py`.
- [x] **TRIANGULATE** - `test_bloqueo_vencido_permite_crear_turno` y `test_bloqueo_de_otra_clinica_no_aplica`.
- [x] **REFACTOR** - Extraer `_verificar_bloqueo(clinic_id, paciente_id, now)` dentro de `TurnoService` y reutilizar `_as_aware`.

### 1.2 - Integración en `TurnoService.crear_turno`

- [x] **RED** - `test_crear_turno_con_bloqueo_vigente_no_persiste_turno`: assertar que la cantidad de `Turno` no cambia.
- [x] **GREEN** - Invocar `_verificar_bloqueo` después de validar el paciente y antes de las consultas de solape.
- [x] **TRIANGULATE** - `test_bloqueo_justo_en_el_limite_hasta_permite` (rango semiabierto `[desde, hasta)`).

### 1.3 - Respuesta 403 en API pública e interna

- [x] **RED** - En `backend/tests/test_turnos_api_public.py`: `test_reserva_publica_paciente_bloqueado_403_con_bloqueado_hasta`. En `backend/tests/test_turnos_api_internal.py`: `test_crear_turno_interno_paciente_bloqueado_403`.
- [x] **GREEN** - Traducir `PacienteBloqueado` en `_traducir_error` de ambos routers a `403` con `detail = {"message": ..., "bloqueado_hasta": <ISO>}`.
- [x] **TRIANGULATE** - `test_bloqueo_vencido_permite_reserva_publica` (200/201).
- [x] **REFACTOR** - Unificar el formato del detalle en un helper compartido si la duplicación supera dos líneas.

---

## Fase 2 - Expiración de `pendiente_sena`

### 2.1 - Consulta de vencidos

- [x] **RED** - `test_expirar_pendientes_cancela_vencidos`: crear un turno, forzar `created_at = NOW - 31 min`, llamar `expirar_pendientes(now=NOW, ttl_min=30)` y esperar `estado == "cancelado"`.
  **Archivos**: `backend/tests/test_turno_service.py`
- [x] **GREEN** - Agregar `TurnoRepository.list_pendientes_expirados(clinic_id, cutoff)` y `TurnoService.expirar_pendientes(...)`.
- [x] **TRIANGULATE** - `test_expirar_pendientes_respeta_ttl` (29 min), `test_expirar_pendientes_no_toca_confirmados` y `test_expirar_pendientes_es_idempotente`.
- [x] **REFACTOR** - Normalizar el cutoff según dialecto (SQLite naive / PostgreSQL aware) en un helper privado.

### 2.2 - Liberación observable del slot

- [x] **RED** - `test_turno_expirado_libera_slot_en_disponibilidad`: tras expirar, el inicio del turno vuelve a estar en `disponibilidad(...)`.
- [x] **GREEN** - Verificar que `estado = cancelado` excluye el turno de `ESTADOS_VIGENTES` (sin cambios adicionales si ya se cumple).
- [x] **TRIANGULATE** - `test_turno_expirado_aparece_como_cancelado_en_agenda`.

### 2.3 - Ciclo del worker

- [x] **RED** - `test_ejecutar_ciclo_expiracion_commitea`: usar `db_session`, crear un vencido y llamar `ejecutar_ciclo_expiracion(session, now=NOW)`; assertar cantidad y estado persistido tras `expire_all()`.
  **Archivos**: `backend/tests/test_worker_expiraciones.py`
- [x] **GREEN** - Crear `backend/app/infrastructure/queue/expirations.py` con `ejecutar_ciclo_expiracion(session, now=None) -> int`.
- [x] **TRIANGULATE** - `test_ciclo_sin_vencidos_devuelve_cero`.
- [x] **REFACTOR** - Integrar el ciclo en `worker.py` con `WORKER_POLL_SECONDS` y manejo de excepciones que no corte el loop.

---

## Fase 3 - Alias `practica` en disponibilidad

- [x] **RED** - `test_slots_acepta_alias_practica` en `backend/tests/test_turnos_api_public.py` (mismos slots que `tipo_practica_id`).
- [x] **GREEN** - Agregar `practica: UUID | None` al endpoint y resolver el id efectivo.
- [x] **TRIANGULATE** - `test_slots_parametros_ambiguos_422` y `test_slots_sin_practica_422`.
- [x] **REFACTOR** - Documentar la precedencia y el 422 en el docstring del endpoint.

---

## Fase 4 - Migración e índices

- [x] **RED** - `backend/tests/test_migration_005.py::test_migracion_005_cadena_y_indices`: assertar `revision == "005"`, `down_revision == "004"` y los índices en `Base.metadata`.
- [x] **GREEN** - Crear `005_turnos_expiracion_bloqueos.py` con `ix_turnos_estado_created_at` e `ix_bloqueos_paciente_id_hasta`.
- [x] **TRIANGULATE** - Declarar los mismos índices en `Turno.__table_args__` y `Bloqueo.__table_args__`; agregar el test de metadata.
- [x] **REFACTOR** - Verificar que `alembic upgrade head` y `downgrade 004` son reversibles (skip si no hay PostgreSQL).

---

## Fase 5 - Verificación final

- [x] **5.1 - Suite backend completa**

  Desde `backend/`: `.\.venv\Scripts\python.exe -m pytest -q`. Criterio: todo verde y cobertura ≥ 50% (`--cov-fail-under=50`).

- [x] **5.2 - Lint**

  Desde `backend/`: `.\.venv\Scripts\python.exe -m ruff check app tests`. Criterio: sin errores.

- [x] **5.3 - OpenSpec**

  Desde la raíz: `openspec validate c-05-motor-reservas-slots-turnos --strict`. Criterio: `valid: true`.

- [x] **5.4 - Registrar evidencia y cerrar tasks**

  Agregar una sección "Notas de verificación" con los resultados y marcar todas las casillas. Guardar el progreso en Engram (`topic_key: opsx/c-05-motor-reservas-slots-turnos/apply`).

---

## Notas de verificación

- **Fecha**: 2026-11-05.
- **Línea base**: 125 passed / 20 skipped antes de tocar código.
- **Suite completa**: `pytest -q` → **151 passed, 20 skipped**; cobertura **83.63%** (umbral 50%).
- **Lint**: `ruff check app tests` → **All checks passed**.
- **OpenSpec**: `openspec validate c-05-motor-reservas-slots-turnos --strict` → **valid**.
- **TDD**: todos los comportamientos nuevos se escribieron como test fallando por la razón correcta (import de `PacienteBloqueado`, módulo `expirations` y migración 005 inexistentes) antes de implementarlos.

### Deltas entregados

1. **Bloqueo RN-AUS-02**: `BloqueoRepository.get_vigente` (rango `[desde, hasta)` y `is_active`), `TurnoService._verificar_bloqueo` en el choke point de `crear_turno`, error `PacienteBloqueado`, y traducción **403** con `detail.bloqueado_hasta` en routers público e interno.
2. **Expiración RN-RES-04**: `TurnoRepository.list_pendientes_expirados`, `TurnoService.expirar_pendientes` (TTL desde `Settings.mp_ttl_min`), `ejecutar_ciclo_expiracion` con commit y worker periódico (`WORKER_POLL_SECONDS=60`) tolerante a errores.
3. **Alias `practica`**: `GET /api/public/slots` acepta `practica` y `tipo_practica_id`; 422 si faltan ambos o si difieren; mismo resultado que el nombre anterior.
4. **Migración 005**: `ix_turnos_estado_created_at` e `ix_bloqueos_paciente_id_hasta`, declarados también en `Turno.__table_args__` y `Bloqueo.__table_args__`.

### Ajuste transversal

- `http_exception_handler` ahora preserva `detail` estructurado (dict) en el envelope RFC7807. Los detalles string mantienen el comportamiento previo; es lo que permite exponer `bloqueado_hasta` sin romper el contrato de errores.

### Pendientes explícitos (fuera de C-05)

- Excepción auditada de recepción para pacientes bloqueados → C-07.
- Checkout/webhook de Mercado Pago y confirmación de pago → C-08/C-09.
- `EXCLUDE USING gist` y caché Redis de disponibilidad → endurecimiento futuro documentado en `design.md`.

