# Tasks — C-06 reserva pública, cancelación y reprogramación

**Change:** c-06-reserva-publica-cancel-reprog
**Schema:** spec-driven
**Governance:** MEDIO

> TDD obligatorio. Cada comportamiento sigue RED → GREEN → TRIANGULATE → REFACTOR.
> RED: el test falla por la razón correcta (atributo/import/endpoint inexistente), no por un error de entorno.
> GREEN: implementación mínima.
> TRIANGULATE: segundo caso que obligue a generalizar (borde de 12 h, estado terminal, recurso repetido).
> REFACTOR: limpiar sin cambiar comportamiento y dejar la suite completa verde.
>
> Comandos de referencia desde la raíz del repo:
> - Backend: `backend\.venv\Scripts\python.exe -m pytest -q` (o desde `backend/`: `.\.venv\Scripts\python.exe -m pytest -q`).
> - Lint backend: `backend\.venv\Scripts\python.exe -m ruff check backend\app backend\tests`.
> - Frontend: `npm run test`, `npm run build`, `npm run lint` dentro de `frontend/`.
> - OpenSpec: `openspec validate c-06-reserva-publica-cancel-reprog --strict`.

## 0. Preparación y contratos

- [x] **0.1 - Verificar la línea base de C-05**
  Ejecutar `backend\.venv\Scripts\python.exe -m pytest -q` y confirmar que la suite heredada está verde antes de tocar código.
  **Archivos**: ninguno (lectura).
  **Verificación**: salida con 0 fallos; anotar el total de passed/skipped como referencia.

- [x] **0.2 - Releer reglas y confirmar el alcance**
  Releer `knowledge-base/05_reglas_de_negocio.md` (§Cancelación), `knowledge-base/06_funcionalidades.md` (US-002/US-003) y `knowledge-base/08_arquitectura_propuesta.md` (§Seguridad `manage_token`). Confirmar que pagos (C-08/C-09) y notificaciones (C-10) quedan fuera y que no hay migración.
  **Verificación**: los supuestos coinciden con `design.md` §Decisions D1–D9; si algo difiere, actualizar `design.md` antes de seguir.

- [x] **0.3 - Resolver la política de design system/mockups**
  Invocar la skill `design-system` porque `.active-orchestrator-state.json` no tiene `visual_design` y no existe `design-system/`. Registrar la decisión en `design.md` con una sección `## UI Mockups` (`Decision: no (project policy)` o `Decision: yes` + mockups aprobados) antes de tocar `frontend/src/**`.
  **Verificación**: `design.md` contiene la decisión y, si aplica, la ruta de los mockups aprobados; no se inicia la fase 6 sin este registro.
  **Resultado**: el usuario eligió `off` el 2026-11-06. Quedó `design-system/README.md` (`Mode: off`, `Approval: skipped`), `visual_design` en `.active-orchestrator-state.json` y `## UI Mockups` en `design.md` con `Decision: no (project policy)`.

## 1. Consulta pública por token

- [x] **1.1 - RED: repositorio de consulta por token**
  Agregar a `backend/tests/test_turno_service.py` un test que cree un turno y verifique que un método de repositorio devuelve el turno solo con `manage_token`, y `None` con token inexistente. Debe fallar por `AttributeError`.
  **Archivos**: `backend/tests/test_turno_service.py`.
  **Verificación**: `pytest -q backend/tests/test_turno_service.py -k token_solo` falla por el método faltante.

- [x] **1.2 - GREEN: `TurnoRepository.get_by_manage_token_solo`**
  Implementar en `backend/app/domain/turnos/repository.py` la búsqueda por `clinic_id` + `manage_token`, sin `turno_id`.
  **Verificación**: el test de 1.1 pasa.

- [x] **1.3 - RED: servicio de consulta por token**
  Test que espere `TurnoNoEncontrado` cuando el token no existe y el turno cuando existe.
  **Verificación**: falla por el método de servicio inexistente.

- [x] **1.4 - GREEN: `TurnoService.get_por_token_solo`**
  Implementar el método reutilizando el repositorio de 1.2 y `TurnoNoEncontrado`.
  **Verificación**: tests de 1.3 en verde.

- [x] **1.5 - RED: indicadores de gestión**
  Tests de `TurnoService.indicadores_gestion` para: count 0 con 48 h (`puede_reprogramar_sin_sena = True`), count 1 con 48 h (sin seña = False), 6 h de anticipación (`puede_reprogramar = True`, `cancelacion_retiene_sena = True`, sin seña = False) y estado terminal (los tres false). Esperar los flags de `design.md` D7.
  **Verificación**: los cuatro tests fallan por el helper inexistente.

- [x] **1.6 - GREEN: `indicadores_gestion`**
  Implementar el helper puro (sin persistencia) con el umbral inclusivo de 12 h y `ESTADOS_VIGENTES`; `puede_reprogramar` es verdadero para todo turno vigente.
  **Verificación**: los cuatro tests pasan; agregar un caso borde de exactamente 12 h.

- [x] **1.7 - RED: schemas públicos de gestión**
  Test de serialización de `TurnoPublicoOut` con `reprogramaciones_count` y de `TurnoGestionOut` con los flags. Debe fallar por campos inexistentes.
  **Archivos**: `backend/tests/test_turnos_api_public.py` o un test de schemas.
  **Verificación**: falla por `ValidationError`/atributo faltante.

- [x] **1.8 - GREEN: schemas**
  Agregar `reprogramaciones_count` a `TurnoPublicoOut` y crear `TurnoGestionOut(TurnoPublicoOut)` en `backend/app/domain/turnos/schemas.py`.
  **Verificación**: test de 1.7 en verde y `TurnoPublicoOut.model_validate(turno)` sigue funcionando con turnos existentes.

- [x] **1.9 - RED: endpoint `GET /reservas/gestion/{token}`**
  Tests de integración: 200 con token válido (incluye `id`, `reprogramaciones_count`, flags), 404 con token inexistente, 200 con estado `cancelado` y flags falsos, y ausencia de `manage_token` en el cuerpo.
  **Archivos**: `backend/tests/test_turnos_api_public.py`.
  **Verificación**: los tests fallan con 404/405 por ruta inexistente.

- [x] **1.10 - GREEN: ruta de consulta**
  Declarar `GET /reservas/gestion/{token}` en `backend/app/api/public/turnos.py` antes de `GET /reservas/{turno_id}` y construir `TurnoGestionOut` con `indicadores_gestion`.
  **Verificación**: tests de 1.9 en verde; probar además que `/reservas/gestion/abc` no se interpreta como UUID.

- [x] **1.11 - REFACTOR: helper de respuesta de gestión**
  Extraer un helper `_turno_gestion_out(turno, now)` en el router o servicio para no duplicar la construcción de flags entre consulta, cancelación y reprogramación.
  **Verificación**: suite de la fase 1 verde y `ruff check` sin errores.

## 2. Cancelación con política explícita

- [x] **2.1 - RED: contrato de cancelación con flags**
  Extender los tests de cancelación para assertar que la respuesta incluye `TurnoGestionOut` con `reprogramaciones_count` y que `sena_retenida` es coherente con el estado `cancelado` y el horario (13 h → false, 6 h → true, exactamente 12 h → false). Tras cancelar, los flags de reprogramación son falsos por estado terminal.
  **Archivos**: `backend/tests/test_turnos_api_public.py`, `backend/tests/test_turno_service.py`.
  **Verificación**: falla porque `CancelacionPublicaOut` todavía devuelve `TurnoPublicoOut` sin flags.

- [x] **2.2 - GREEN: `CancelacionPublicaOut` con `TurnoGestionOut`**
  Cambiar el schema y la construcción en ambos routers; conservar `sena_retenida` calculado por `TurnoService.cancelar`.
  **Verificación**: tests de 2.1 en verde.

- [x] **2.3 - RED: bordes de cancelación**
  Tests para 409 al cancelar dos veces, 404 con token inválido en público, 200 en interno con JWT y 403 de odontólogo sobre turno ajeno (si no existe ya).
  **Verificación**: al menos un test falla por comportamiento faltante o contrato incompleto.

- [x] **2.4 - GREEN: ajustes mínimos de cancelación**
  Corregir lo que expongan los tests sin cambiar la regla `sena_retenida = (inicio - now) < 12 h`. No bloquear estados terminales distintos de `cancelado` (decisión D2).
  **Verificación**: tests de 2.3 en verde.

- [x] **2.5 - RED: slot liberado re-reservable**
  Test que cancele un turno y luego cree una reserva pública en el mismo horario. Debe fallar si la disponibilidad sigue ocupada o el alta devuelve 409.
  **Verificación**: el test falla por el estado/slot, no por un error de setup.

- [x] **2.6 - GREEN: liberación inmediata**
  Confirmar que `disponibilidad` excluye `cancelado` vía `ESTADOS_VIGENTES`; si el test falla, corregir la consulta sin tocar el contrato.
  **Verificación**: el test de 2.5 pasa y el horario reaparece en `GET /api/public/slots`.

- [x] **2.7 - REFACTOR: traducción de errores compartida**
  Unificar en cada router la traducción de `TurnoNoEncontrado`/`TurnoYaCancelado` para consulta, cancelación y reprogramación, sin duplicar ramas.
  **Verificación**: suite de la fase 2 verde y `ruff check` limpio.

## 3. Reprogramación en el dominio

- [x] **3.1 - RED: primera reprogramación en la misma fila**
  Test de servicio: turno vigente, count 0, inicio a 48 h; reprogramar a un slot libre con ≥ 12 h. Esperar mismo `id`, mismo `manage_token`, mismo `monto_sena`, `estado` conservado, `reprogramaciones_count = 1`, `sena_migrada = True`, `requiere_nueva_sena = False`.
  **Archivos**: `backend/tests/test_turno_service.py`.
  **Verificación**: falla por `TurnoService.reprogramar`/resultado inexistente.

- [x] **3.2 - GREEN: resultado y esqueleto de `reprogramar`**
  Crear `ResultadoReprogramacion { turno, turno_anterior, inicio_anterior, sena_migrada, requiere_nueva_sena }` y el método `reprogramar(clinic_id, turno_id, inicio, sillon_id=None, odontologo_id=None, now=None)` con el camino de misma fila.
  **Verificación**: test de 3.1 pasa y `inicio_anterior` conserva el valor previo a la mutación.

- [x] **3.3 - RED: validaciones de reprogramación**
  Tests para: turno `cancelado`/`completado`/`ausente` → 409; nuevo inicio a 11 h → 409; exactamente 12 h → permitido; práctica inactiva → error de práctica; sillón/odontólogo de otra clínica → no encontrado.
  **Verificación**: cada test falla por la validación faltante, con el tipo de error de dominio esperado.

- [x] **3.4 - GREEN: validaciones**
  Implementar el orden de `design.md` D5: estado → ventana → práctica → sillón/odontólogo → anti-solape → escritura. Reutilizar las excepciones existentes o agregar una específica para “turno no reprogramable” si el mensaje lo requiere, y mapearla a 409 en ambos routers (no dejar que caiga en el 404 genérico).
  **Verificación**: tests de 3.3 en verde.

- [x] **3.5 - RED: anti-solape excluyendo el turno actual**
  Tests: mover al mismo inicio/sillón/odontólogo no da 409; solape de sillón da 409; solape de odontólogo en otro sillón da 409; turno contiguo se acepta.
  **Verificación**: al menos el caso “mismo turno” falla si no se pasa `excluir_turno_id`.

- [x] **3.6 - GREEN: exclusión del turno actual**
  Pasar `excluir_turno_id=turno.id` a las dos llamadas de `exists_overlap`; no modificar la firma del repositorio (ya la soporta).
  **Verificación**: tests de 3.5 en verde.

- [x] **3.7 - RED: segunda reprogramación y reprogramación tardía**
  Tests: count 1 + 48 h → turno viejo `cancelado`, turno nuevo `pendiente_sena`, `manage_token` distinto, `reprogramaciones_count = 2`, `monto_sena` recalculado con el precio actual, `sena_migrada = False`, `requiere_nueva_sena = True`. Caso count 0 + 6 h → mismo comportamiento con count 1. Assertar que el `created_at` del turno nuevo es posterior al del viejo.
  **Verificación**: fallan por el camino de turno nuevo inexistente.

- [x] **3.8 - GREEN: camino de turno nuevo**
  Marcar el viejo `cancelado`, hacer `flush`, llamar a `crear_turno` con el paciente, práctica y recursos resueltos, y ajustar `reprogramaciones_count = anterior + 1`. No hacer commit en el servicio.
  **Verificación**: tests de 3.7 en verde; verificar que el turno nuevo aparece ocupando el slot y el viejo lo libera.

- [x] **3.9 - RED: atomicidad**
  Test que fuerce un fallo de `crear_turno` (monkeypatch o recurso inválido) durante una reprogramación que exige nueva seña; tras rollback, el turno viejo debe seguir vigente con su horario, estado, seña y token.
  **Verificación**: el test falla si el viejo quedó cancelado o si se creó un turno parcial.

- [x] **3.10 - GREEN: transacción segura**
  Asegurar que `reprogramar` solo hace `flush` y que el router es el único que commitea; documentar en el docstring que un fallo requiere rollback del llamador.
  **Verificación**: test de 3.9 en verde.

- [x] **3.11 - REFACTOR: helpers del algoritmo**
  Extraer `_validar_ventana_reprogramacion`, `_resolver_recursos_reprogramacion` y `_reprogramar_misma_fila` si el método supera ~40 líneas. Mantener type hints explícitos.
  **Verificación**: `pytest -q backend/tests/test_turno_service.py` verde y `ruff check backend/app backend/tests` limpio.

## 4. Endpoints de reprogramación

- [x] **4.1 - RED: reprogramación pública**
  Tests de integración con token: 200 en primera reprogramación, 200 en segunda (devuelve `manage_token` nuevo), 404 con token inválido, 409 por solape, 409 por nuevo horario a menos de 12 h y 409 por turno terminal. Assertar el contrato `ReprogramacionPublicaOut`.
  **Archivos**: `backend/tests/test_turnos_api_public.py`.
  **Verificación**: fallan por ruta/schema inexistente.

- [x] **4.2 - GREEN: endpoint público**
  Agregar `ReprogramarPayload` y `ReprogramacionPublicaOut` en schemas y `POST /reservas/{turno_id}/reprogramar?token=` en el router público. Validar token con `get_por_token`, llamar al servicio y commitear con `UnitOfWork`; rollback ante `TurnoError`.
  **Verificación**: tests de 4.1 en verde.

- [x] **4.3 - RED: reprogramación interna y RBAC**
  Tests: recepción reprograma sin token → 200; odontólogo sobre turno propio → 200; odontólogo sobre turno ajeno → 403; sin JWT → 401; la respuesta incluye `manage_token` solo cuando hay turno nuevo.
  **Archivos**: `backend/tests/test_turnos_api_internal.py`.
  **Verificación**: fallan por endpoint inexistente.

- [x] **4.4 - GREEN: endpoint interno**
  Agregar `POST /turnos/{turno_id}/reprogramar` en `backend/app/api/internal/turnos.py` con `RolLectura` y la misma restricción de odontólogo que la cancelación interna. Responder `ReprogramacionInternaOut`.
  **Verificación**: tests de 4.3 en verde.

- [x] **4.5 - RED: integración de liberación y token viejo**
  Test E2E de API: reservar → consultar por `/gestion/{token}` → reprogramar a un slot → consultar el viejo token (debe devolver el turno viejo `cancelado`) → reservar el slot liberado con otro paciente.
  **Verificación**: el test falla si el slot viejo sigue ocupado o el token viejo desaparece.

- [x] **4.6 - GREEN: cierre de integración**
  Ajustar lo necesario para que 4.5 pase sin cambiar los contratos definidos en el spec.
  **Verificación**: test de 4.5 en verde.

- [x] **4.7 - Verificación de fase backend**
  Ejecutar `backend\.venv\Scripts\python.exe -m pytest -q` y `backend\.venv\Scripts\python.exe -m ruff check backend\app backend\tests`.
  **Verificación**: suite completa verde y lint sin errores.

## 5. Capa de datos del frontend

- [x] **5.1 - Tipos de gestión**
  Agregar en `frontend/src/features/booking/types.ts`: `reprogramaciones_count` en `TurnoPublico`, `TurnoGestion` con los tres flags, `ReprogramarPayload` y `ReprogramacionPublica`. Sin `any`.
  **Verificación**: `npm run build` compila los tipos sin errores.

- [x] **5.2 - RED: API de gestión**
  Tests en `frontend/src/features/booking/booking.api.test.ts` para `getReservaPorToken(token)` (`GET /api/public/reservas/gestion/{token}`) y `reprogramarReserva(turnoId, token, payload)` (`POST .../reprogramar` con `params.token`), mockeando `apiClient`.
  **Verificación**: fallan por funciones inexistentes.

- [x] **5.3 - GREEN: API**
  Implementar ambas funciones en `frontend/src/features/booking/api.ts` con tipos explícitos.
  **Verificación**: tests de 5.2 en verde.

- [x] **5.4 - RED: mensajes de error de gestión**
  Tests de `getBookingErrorMessage` para 404 (token inválido), 409 por ventana de 12 h y 409 por solape, verificando que no se pisen los mensajes actuales de reserva.
  **Verificación**: al menos un test falla por el mensaje faltante.

- [x] **5.5 - GREEN: errores**
  Extender `frontend/src/features/booking/errors.ts` manteniendo compatibilidad con los códigos existentes.
  **Verificación**: tests de 5.4 y los existentes de `booking.api.test.ts` en verde.

## 6. UI de gestión

- [x] **6.1 - RED: hook `useManageAppointment`**
  Tests del hook con mocks de la API: carga inicial, token inválido, cancelación exitosa con retención, y reprogramación con/sin nueva seña.
  **Archivos**: `frontend/src/features/booking/hooks/useManageAppointment.test.ts`.
  **Verificación**: fallan por hook inexistente.

- [x] **6.2 - GREEN: hook**
  Implementar `useManageAppointment(token)` con estados `cargando`, `turno`, `error`, `cancelando`, `reprogramando` y acciones `cancelar`, `buscarSlots`, `reprogramar`, `limpiarError`.
  **Verificación**: tests de 6.1 en verde.

- [x] **6.3 - RED: carga y estados de la página**
  Tests de `ManageAppointmentPage` con `MemoryRouter`/ruta: muestra fecha, práctica, sillón, estado, seña y reprogramaciones; muestra error para token inválido; muestra el estado `cancelado` sin acciones.
  **Archivos**: `frontend/src/pages/ManageAppointmentPage.test.tsx`.
  **Verificación**: fallan porque la página sigue siendo el placeholder.

- [x] **6.4 - GREEN: página de consulta**
  Reescribir `ManageAppointmentPage` para consumir el hook y renderizar los datos; extraer subcomponentes a `frontend/src/features/booking/components/`.
  **Verificación**: tests de 6.3 en verde.

- [x] **6.5 - RED: modal de cancelación**
  Tests: el botón abre el modal; si `cancelacion_retiene_sena` es verdadero, advierte la retención; confirmar llama a `cancelar`; cancelar el modal no llama a la API.
  **Verificación**: fallan por modal inexistente.

- [x] **6.6 - GREEN: modal de cancelación**
  Implementar el modal accesible (rol `dialog`, foco, botones “Volver”/“Confirmar cancelación”) y refrescar el turno tras la respuesta.
  **Verificación**: tests de 6.5 en verde.

- [x] **6.7 - RED: flujo de reprogramación**
  Tests: elegir fecha, buscar slots con `getSlots` usando `turno.tipo_practica.id`, elegir slot, confirmar y llamar a `reprogramarReserva`; error 409 permite reintentar con otra fecha.
  **Verificación**: fallan por flujo inexistente.

- [x] **6.8 - GREEN: flujo de reprogramación**
  Implementar selector de fecha + grilla de slots + confirmación dentro de la página, reutilizando los componentes/estilos de `SlotStep` cuando sea posible.
  **Verificación**: tests de 6.7 en verde.

- [x] **6.9 - RED: nueva seña requerida**
  Test: cuando la respuesta trae `requiere_nueva_sena = true`, la UI muestra el monto de la nueva seña, el estado `pendiente_sena` y el `manage_token` nuevo.
  **Verificación**: falla por la vista de resultado inexistente.

- [x] **6.10 - GREEN: resultado con nueva seña**
  Renderizar el bloque de resultado y actualizar el token usado por la página para las acciones siguientes.
  **Verificación**: test de 6.9 en verde.

- [x] **6.11 - Estilos mobile-first**
  Ajustar `ManageAppointmentPage.css` reutilizando variables/tokens existentes; verificar 390x844 y 1440x900. Si la política de 0.3 exige mockup, comparar contra el aprobado.
  **Verificación**: revisión visual sin overflow horizontal ni controles inaccesibles; capturas guardadas si la política lo requiere.

- [x] **6.12 - Verificación de fase frontend**
  Ejecutar `npm run test`, `npm run build` y `npm run lint` dentro de `frontend/`.
  **Verificación**: tests, typecheck/build y lint sin errores; sin `any` nuevos.

## 7. Verificación final e integración

- [x] **7.1 - Suite backend completa**
  `backend\.venv\Scripts\python.exe -m pytest -q` con cobertura ≥ 50 %.
  **Verificación**: 0 fallos y umbral de cobertura cumplido.
  **Resultado (2026-11-06)**: `203 passed, 20 skipped, 7 warnings in 80.17s`; cobertura total **85.20 %** (umbral 50 %). 52 tests nuevos respecto de la baseline de C-05 (151 passed).

- [x] **7.2 - Lint backend**
  `backend\.venv\Scripts\python.exe -m ruff check backend\app backend\tests`.
  **Verificación**: “All checks passed”.
  **Resultado (2026-11-06)**: `All checks passed!` sin hallazgos.

- [x] **7.3 - Suite frontend**
  Desde `frontend/`: `npm run test`.
  **Verificación**: todos los tests verdes, incluidos los nuevos de gestión.
  **Resultado (2026-11-06)**: `Test Files 8 passed (8)`, `Tests 57 passed (57)` (Vitest 5.0.4, 3.81 s). Incluye `booking.api.test.ts`, `useManageAppointment.test.ts` y `ManageAppointmentPage.test.tsx`.

- [x] **7.4 - Build y lint frontend**
  Desde `frontend/`: `npm run build` y `npm run lint`.
  **Verificación**: build de producción y lint sin errores.
  **Resultado (2026-11-06)**: `npm run build` OK, 119 módulos transformados, `dist/assets/index-cog7nNY2.js` 409.17 kB (127.71 kB gzip). `npm run lint` exit 0: solo warnings preexistentes (`router.tsx`, `RouteGuard.tsx`, `useBooking.ts`) más uno nuevo en `useManageAppointment.ts:65` (`set-state-in-effect`); sin errores.

- [x] **7.5 - Validación OpenSpec**
  `openspec validate c-06-reserva-publica-cancel-reprog --strict`.
  **Verificación**: `valid: true`.
  **Resultado (2026-11-06)**: `Change 'c-06-reserva-publica-cancel-reprog' is valid`. `openspec status` reporta los 4 artefactos `done` y `isComplete: true`.

- [x] **7.6 - Smoke manual del flujo**
  Con backend y frontend levantados: reservar, abrir `/gestionar/:token`, consultar, cancelar anticipado, reprogramar por primera vez, reprogramar por segunda vez y verificar la nueva seña; probar token inválido y horario con menos de 12 h.
  **Verificación**: checklist marcada con resultado observado; documentar cualquier diferencia en `design.md` §Risks.
  **Resultado (2026-11-06)**: ejecutado con API real (uvicorn) sobre SQLite aislado y Vite dev server + navegador Playwright.
  - API: **18/18 checks OK** — health, prácticas, slots, reserva, gestión por token, token inválido 404, 1.ª reprogramación (misma fila, `sena_migrada=True`, count=1, token/monto intactos), slot original re-publicado, 2.ª reprogramación (turno nuevo `pendiente_sena`, token nuevo, count=2, `requiere_nueva_sena=True`), turno viejo cancelado, horario <12 h 409, reprogramar cancelado 409, cancelación anticipada sin retención, cancelación repetida 409, login de recepción, reprogramación interna con JWT y 401 sin JWT.
  - UI (Playwright): `/gestionar/:token` renderiza resumen completo; modal de cancelación con aviso correcto y “Volver”; reprogramación con búsqueda de slots y confirmación; 1.ª repro actualiza el resumen (count=1); 2.ª repro muestra el bloque de nueva seña con monto, estado y token nuevo + link `/gestionar/<token-nuevo>`; cancelación del turno nuevo deja estado `Cancelado`, mensaje de liberación y sin acciones; token inválido muestra “Reserva no encontrada” con “Reintentar”. Sin overflow horizontal a 390x844 (`scrollWidth = clientWidth = 390`). Consola: solo los 404 esperados del token inválido.
  - Diferencia documentada: con SQLite la API serializa datetimes naive, así que el resumen muestra la hora UTC en lugar de ART (la grilla sí convierte). Con PostgreSQL (`timestamptz`) el ISO lleva offset y la conversión es correcta; queda anotado en `design.md` §Risks.
  - Límite del smoke: Redis no estaba levantado (el health lo reporta `disconnected`) y no se usó PostgreSQL; los endpoints de C-06 no dependen de Redis.

## Workflow follow-up

- Actualizar `CHANGES.md` (estado de C-06) recién al archivar el change; no modificar el roadmap durante el apply.
- Guardar el cierre en Engram con `topic_key: opsx/c-06-reserva-publica-cancel-reprog/apply`.
- Archivar el change con `openspec archive` cuando la verificación y la revisión estén completas.
