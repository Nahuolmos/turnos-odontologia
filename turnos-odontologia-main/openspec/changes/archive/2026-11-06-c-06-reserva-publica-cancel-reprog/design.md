# Design — C-06 reserva pública, cancelación y reprogramación

## Context

C-05 dejó el motor de reservas estable: `Turno.manage_token` UNIQUE, `reprogramaciones_count`, `monto_sena` como snapshot, `TurnoService.crear_turno` con anti-solape y bloqueo RN-AUS-02, `TurnoService.cancelar` con ventana de 12 h y los endpoints públicos/internos de consulta y cancelación. La suite corre sobre SQLite (ver `backend/tests/conftest.py`) y no hay migración pendiente.

Restricciones verificadas en el código:

- `Turno.manage_token` es UNIQUE global, no por clínica; en v1 hay una sola clínica activa, así que el token alcanza para resolver el turno.
- `TurnoRepository.exists_overlap` ya acepta `excluir_turno_id`; no hace falta agregar el parámetro.
- `TurnoService.crear_turno` ya valida práctica activa, paciente de la clínica, sillón, odontólogo, bloqueo y anti-solape.
- `TurnoService.cancelar` y `crear_turno` no hacen commit; los routers usan `UnitOfWork`.
- `frontend/src/router.tsx` **no** envuelve `/gestionar/:token` en `PublicRoute`: la ruta es accesible con o sin sesión. El riesgo de redirección de usuarios logueados descripto en el relevamiento no existe en el código actual.
- No existe `design-system/` ni `visual_design` en `.active-orchestrator-state.json`; la política visual está pendiente.

## Goals / Non-Goals

**Goals:**

- Resolver una reserva por `manage_token` sin exigir el `id` en la URL.
- Unificar la semántica de cancelación anticipada/tardía y hacerla observable en la respuesta.
- Implementar reprogramación con dos caminos: migración de seña en la misma fila o turno nuevo con nueva seña.
- Exponer indicadores de elegibilidad calculados en servidor para que la UI no dependa del reloj del dispositivo.
- Cubrir el flujo público y el equivalente interno con RBAC.
- Extraer la lógica de gestión a `features/booking/` reutilizando `getSlots`.

**Non-Goals:**

- Checkout, preferencia, webhook o reembolso de Mercado Pago (C-08/C-09).
- Envío real de WhatsApp, cancelación de jobs de recordatorio o reprogramación del job (C-10). Solo se documenta el hook.
- Migración Alembic: no hay columnas ni tablas nuevas.
- Login de paciente, historial o multi-clínica (C-11).
- Endurecimiento `EXCLUDE USING gist`, bloqueo pesimista o rate limit específico de los endpoints por token.
- Mockups y sistema de diseño: se resuelven antes de la fase de UI según la política del proyecto.

## Decisions

### D1 — Consulta por token en una ruta literal separada

**Decisión**: agregar `GET /api/public/reservas/gestion/{token}` que devuelve `TurnoGestionOut`. La ruta se declara antes de `GET /reservas/{turno_id}` y usa un método de repositorio que busca solo por `manage_token`. Token inexistente → 404.

**Alternativas**:

- Reutilizar `GET /reservas/{turno_id}?token=`: obliga al paciente a conocer dos secretos y no sirve para una URL que solo lleva el token.
- `GET /reservas?token=`: compite con la ruta de colección y pierde claridad de contrato.
- Resolver en el frontend con un endpoint interno: viola RN-RES-03 (gestión sin login).

**Rationale**: `manage_token` es una credencial portadora de 256 bits y UNIQUE; el token identifica el turno por sí solo. La ruta de gestión tiene tres segmentos y no colisiona con `/reservas/{turno_id}`; se declara antes por precedencia explícita y para que un futuro `/reservas/{turno_id}/{accion}` no la capture. El método de repositorio devuelve `None` si no hay coincidencia y el router traduce a 404 sin distinguir "token inválido" de "turno inexistente", para no filtrar información.

### D2 — La cancelación conserva su contrato y explicita la política

**Decisión**: se mantienen `POST /api/public/reservas/{turno_id}/cancelar?token=` y `POST /api/internal/turnos/{turno_id}/cancelar`. La política es `sena_retenida = (inicio - now) < 12 h`, con 12 h exactas consideradas a tiempo. `estado = "cancelado"` en todos los casos; 409 si ya estaba cancelado; 404 si el token no corresponde. El router público valida token antes de cancelar; el interno usa JWT y RBAC existente.

**Alternativas**:

- Devolver 409 cuando la cancelación es tardía: contradice RN-CANCEL-03, que permite cancelar y solo impide el reembolso.
- Bloquear la cancelación con menos de 12 h: dejaría el slot ocupado y empeoraría la operación.

**Rationale**: el servicio ya implementa la ventana y la liberación del slot vía `ESTADOS_VIGENTES`; C-06 solo hace explícita la semántica y la refleja en la respuesta. No se endurecen los estados terminales (`completado`, `ausente`) para no ampliar el alcance de C-07; la UI pública solo ofrece cancelar turnos vigentes.

### D3 — Payload de reprogramación con herencia de recursos

**Decisión**: `POST /api/public/reservas/{turno_id}/reprogramar?token=` recibe `ReprogramarPayload { inicio: datetime, sillon_id: UUID | None, odontologo_id: UUID | None }`. Si falta un recurso, se hereda del turno actual. La ruta interna equivalente es `POST /api/internal/turnos/{turno_id}/reprogramar` con JWT y sin token. Interno responde `ReprogramacionInternaOut { turno: TurnoOut, sena_migrada, requiere_nueva_sena, manage_token: str | None }`; el `manage_token` solo aparece cuando se creó un turno nuevo, y se expone al personal autenticado para que pueda enviárselo al paciente.

**Alternativas**:

- Exigir siempre `sillon_id` y `odontologo_id`: obliga al paciente a elegir recursos internos que no entiende.
- Reutilizar el payload de `ReservaCreate`: incluye nombre/teléfono y no aplica a un turno existente.
- Devolver `TurnoPublicoOut` en el interno: ocultaría el token nuevo que recepción necesita comunicar.

**Rationale**: heredar recursos preserva la práctica y reduce errores; el paciente solo elige el horario que le ofrece `getSlots`. El schema interno mantiene la regla de que `TurnoOut` nunca expone `manage_token`, pero permite que el personal lo reciba en un campo explícito de la respuesta de reprogramación.

### D4 — Dos caminos de reprogramación en `TurnoService.reprogramar`

**Decisión**: el servicio calcula `tardia = (inicio_actual - now) < 12 h` y `es_segunda = reprogramaciones_count >= 1`.

- **Caso libre** (`not tardia and not es_segunda`): actualiza la misma fila con nuevo `inicio`, `fin`, `sillon_id` y `odontologo_id`; incrementa `reprogramaciones_count`; conserva `estado`, `monto_sena` y `manage_token`.
- **Caso 2.ª o tardía**: marca el turno viejo como `cancelado` y hace `flush`; luego llama a `crear_turno` para crear un turno nuevo `pendiente_sena` con nuevo `manage_token`, `monto_sena` recalculado y `reprogramaciones_count = anterior + 1`.

**Alternativas**:

- Reutilizar la misma fila también en la 2.ª/tardía: es más simple, pero `created_at` alimenta `list_pendientes_expirados` y el TTL de `MP_TTL_MIN`. Al quedar `pendiente_sena` con el `created_at` original, el worker lo cancelaría en el siguiente ciclo (o de inmediato si el turno tenía horas de antigüedad). Un turno nuevo nace con `created_at = now` y tiene el TTL completo para pagar.
- Crear el turno nuevo antes de cancelar el viejo: el anti-solape detectaría el propio turno si se mantiene el mismo sillón u odontólogo. Cancelar y hacer `flush` primero libera el rango dentro de la misma transacción.
- Guardar una fila de historial separada: no hay modelo de historial en v1 y no es necesario para las reglas.

**Rationale**: el historial queda igual de auditable porque el turno viejo permanece como `cancelado` con su seña (la retención se deriva de `requiere_nueva_sena = true`). La fila nueva permite recalcular el precio actual y reiniciar el TTL. El `flush` intermedio es seguro porque no hay commit: si `crear_turno` falla, el router hace rollback y el turno viejo vuelve a su estado anterior.

### D5 — Orden de validaciones y exclusión del turno actual

**Decisión**: `reprogramar` valida en este orden: turno existe → estado vigente → `nuevo_inicio - now >= 12 h` → práctica activa (la del turno; no se permite cambiar de práctica en C-06) → sillón y odontólogo de la clínica → anti-solape con `excluir_turno_id=turno.id` en ambas consultas. El router público valida el token antes de invocar el servicio. Recién después de las validaciones se decide el camino y se escribe.

**Alternativas**:

- Validar el anti-solape sin excluir el turno actual: al mover un turno dentro del mismo sillón/odontólogo, el rango viejo puede intersectar el nuevo y producir un 409 falso.
- Cambiar de práctica en la reprogramación: cambia duración y precio, y excede RN-CANCEL-02; queda para otro change.

**Rationale**: el orden evita escrituras parciales y da el error más específico. `exists_overlap` ya soporta `excluir_turno_id`; se pasa en las dos llamadas. En el caso de turno nuevo, el viejo ya está `cancelado` y flusheado, por lo que tampoco bloquea, pero la exclusión explícita hace el contrato independiente del orden. Los errores de estado no reprogramable y de ventana mínima se traducen a **409** en ambos routers; no deben caer en el 404 genérico de `TurnoError`.

### D6 — 409 para el nuevo horario fuera de ventana

**Decisión**: si `nuevo_inicio - now < 12 h`, la API responde 409 con un mensaje que menciona la ventana mínima. No se usa 422.

**Alternativas**:

- 422: semánticamente reservado a payload inválido por forma/tipo; el datetime es válido pero viola una regla de negocio.
- 400: más genérico y menos accionable para el frontend.

**Rationale**: el frontend ya trata 409 como "horario no disponible, elegí otro" y puede mostrar el mensaje del servidor. Un 422 se confundiría con el error de validación del teléfono/fecha y no permitiría distinguir la regla de negocio.

### D7 — Schemas y flags derivados en servidor

**Decisión**:

- `TurnoPublicoOut` suma `reprogramaciones_count: int` (dato persistido).
- `TurnoGestionOut(TurnoPublicoOut)` agrega `puede_reprogramar`, `puede_reprogramar_sin_sena` y `cancelacion_retiene_sena`, calculados por `TurnoService.indicadores_gestion(turno, now)` y asignados en el router; no se persisten.
- Reglas de los flags, solo para estados en `ESTADOS_VIGENTES`:
  - `puede_reprogramar = true` para todo turno vigente. La reprogramación tardía se permite con nueva seña; la disponibilidad del nuevo horario se valida al confirmar.
  - `puede_reprogramar_sin_sena = puede_reprogramar and reprogramaciones_count == 0 and (inicio - now) >= 12 h`.
  - `cancelacion_retiene_sena = (inicio - now) < 12 h`.
  - En `cancelado`, `completado` o `ausente`, los tres son `false`.
- `CancelacionPublicaOut.turno` pasa a `TurnoGestionOut` (cambio aditivo).
- `ReprogramacionPublicaOut { turno: TurnoGestionOut, sena_migrada: bool, requiere_nueva_sena: bool, manage_token: str | None }`; el token solo se completa cuando hay turno nuevo.

**Alternativas**:

- Calcular los flags en el frontend con `Date.now()`: el reloj del dispositivo puede estar desfasado y la UI habilitaría acciones que el servidor rechaza; además duplicaría la regla de 12 h.
- Persistir los flags: se desactualizan con el tiempo y no aportan auditoría.
- Devolver los flags dentro de `TurnoPublicoOut` para todos los endpoints: obligaría a calcularlos también en la creación y en la consulta por id, donde no se usan.

**Rationale**: un único helper en el servicio concentra la política y el router solo lo invoca. `TurnoGestionOut` mantiene compatibilidad con lo que ya consume el frontend y agrega la información que necesita la pantalla de gestión.

### D8 — Transacciones y hook de notificaciones

**Decisión**: `reprogramar` no hace commit; el router confirma con `UnitOfWork` y hace rollback ante cualquier `TurnoError`. El servicio devuelve un `ResultadoReprogramacion { turno, turno_anterior, inicio_anterior, sena_migrada, requiere_nueva_sena }`, donde `inicio_anterior` se captura antes de mutar la fila. No se agrega código de notificaciones: C-10 deberá envolver cancelación y reprogramación para cancelar/reprogramar el job de recordatorio cuando el cambio ocurra antes de T-24 h (RN-NOTIF-03), usando el `turno_anterior` y el `turno` que devuelve el resultado.

**Alternativas**:

- Commit dentro del servicio: rompe el patrón existente y deja a los routers sin control del límite transaccional.
- Emitir un evento o encolar un job ahora: no existe infraestructura de colas ni modelo `Notificacion`; sería código muerto.

**Rationale**: mantiene el patrón `Service` sin commit + `UnitOfWork` en el router, ya usado por `crear_turno` y `cancelar`. El resultado con ambos turnos y el inicio anterior es suficiente para que C-10 implemente el hook sin reconsultar la base ni perder el horario original del recordatorio.

### D9 — Sin migración Alembic

**Decisión**: no se crea migración. `manage_token`, `reprogramaciones_count` y `monto_sena` ya existen; no hay columnas nuevas ni cambios de constraints.

**Alternativas**:

- Agregar una columna de historial de reprogramaciones: no la pide ninguna regla y complicaría el modelo sin uso concreto.
- Agregar un índice por `manage_token`: ya es UNIQUE y PostgreSQL crea el índice implícito.

**Rationale**: el change es de comportamiento, no de esquema. Evita un `alembic upgrade` innecesario y mantiene el rollback a nivel de aplicación.

### D10 — UI de gestión sobre el feature `booking`

**Decisión**: `ManageAppointmentPage` consume `GET /reservas/gestion/{token}` al montar. Extrae la lógica a `useManageAppointment` con estados `cargando`, `turno`, `error`, `cancelando`, `reprogramando`. Para reprogramar reutiliza `getSlots({ fecha, tipoPracticaId: turno.tipo_practica.id })` y `reprogramarReserva(turnoId, token, payload)`. El modal de cancelación usa `cancelacion_retiene_sena` del servidor para el texto de advertencia. Si la reprogramación devuelve `requiere_nueva_sena`, la pantalla muestra el nuevo token y el monto de la nueva seña. Nada de `any`; mobile-first y clases/tokens existentes.

**Alternativas**:

- Crear un feature `manage` separado: duplica tipos y API; `booking` ya contiene el dominio público de reservas.
- Reutilizar `useBooking`: mezcla el flujo de alta con el de gestión y arrastra estado que no aplica.

**Rationale**: un hook específico mantiene la página delgada y testeable, y reutiliza la API y los componentes de slots ya probados.

## UI Mockups

- **Design system mode:** `off` (política del proyecto, elegida por el usuario el 2026-11-06).
- **Decision:** no (project policy).
- **Mockups:** no aplica.
- **Approval:** skipped.
- **Preview:** no aplica.
- **Visual verify:** manual con la suite de frontend y revisión responsive; no hay mockup contra el cual comparar.

La política vive en `design-system/README.md` y en `visual_design` de
`.active-orchestrator-state.json`. No se vuelve a preguntar por change.

## Risks / Trade-offs

- **Concurrencia de reprogramación** → el patrón es leer-validar-escribir. Dos reprogramaciones simultáneas del mismo turno podrían pasar la validación y pisarse (o perder un incremento de `reprogramaciones_count`). Mitigación para C-06: mantener todo en una transacción y escribir el contador como `viejo + 1`; endurecimiento futuro con `SELECT ... FOR UPDATE` sobre el turno o un `UPDATE ... WHERE reprogramaciones_count = :viejo`. No se implementa ahora para no romper SQLite.
- **Doble reserva del mismo slot** → el anti-solape es check-then-insert. Dos pacientes podrían reservar el mismo hueco antes del commit. Es deuda heredada de C-05; el `EXCLUDE USING gist` en PostgreSQL sigue pendiente.
- **TTL en la primera reprogramación de un `pendiente_sena`** → el camino de misma fila conserva `created_at`, así que un turno impago que se reprograma puede expirar con el TTL original (`MP_TTL_MIN`). Mitigación: la UI prioriza reprogramar turnos confirmados; si el negocio necesita conservar el TTL completo, se refresca `created_at` al mover la fila o se crea turno nuevo también en ese caso. Se documenta como deuda para C-08/C-10.
- **Reloj del cliente** → mitigado con flags calculados en el servidor. La UI no debe recalcular la ventana de 12 h con `Date.now()`.
- **Token en la URL** → puede filtrarse por logs, historial o `Referer`. Es el diseño de RN-RES-03 y ya existe en C-04; no se agrega rate limit específico en este change. Mitigación futura: `Referrer-Policy: no-referrer` y rate limit por IP/token.
- **Token viejo tras una 2.ª reprogramación** → sigue devolviendo el turno viejo `cancelado`. La UI debe mostrar ese estado y el nuevo token; no se invalida el token viejo a nivel de datos para conservar trazabilidad.
- **Cancelación de estados terminales** → el servicio actual permite cancelar `completado`/`ausente` (solo rechaza `cancelado`). C-06 no lo restringe para no invadir C-07; la UI pública solo ofrece la acción sobre turnos vigentes. Queda como pregunta abierta de operación.
- **Notificaciones desincronizadas** → hasta C-10, cancelar o reprogramar no cancela el recordatorio. Se documenta el hook y la respuesta devuelve los datos necesarios; el riesgo es funcional, no de datos.
- **Design system resuelto** → política `off` registrada el 2026-11-06 por decisión del usuario (`design-system/README.md` y `visual_design` en `.active-orchestrator-state.json`). No hay foundation ni mockups; la UI reutiliza los estilos existentes y el gate visual queda desactivado para este y los próximos changes hasta que el usuario pida lo contrario.
- **Smoke E2E ejecutado (2026-11-06)** → API real con uvicorn sobre SQLite aislado + Vite dev server y navegador Playwright: 18/18 checks de API y recorrido completo de UI (resumen, modal, 1.ª y 2.ª reprogramación con nueva seña, cancelación y token inválido) sin defectos funcionales. El detalle está en `tasks.md` §7.6. No se probó con PostgreSQL ni con Redis levantado; los endpoints de C-06 no dependen de Redis.
- **Datetimes naive en SQLite** → el smoke mostró que, con SQLite, la API serializa `inicio` sin offset y el resumen de gestión muestra la hora UTC mientras la grilla de slots la convierte a ART. Con PostgreSQL (`timestamptz`) el ISO incluye `+00:00` y ambas vistas coinciden. No se cambia el contrato: es una diferencia del dialecto de desarrollo, no de producción. Si en el futuro se adopta SQLite para demo, habría que normalizar el offset en el borde de la API.

## Migration / Rollout

1. Backend primero: los endpoints nuevos son aditivos y no requieren migración. Desplegar y verificar con la suite.
2. Frontend después: `ManageAppointmentPage` sigue funcionando con el placeholder si el backend no está; al activar la nueva versión, depende de `/reservas/gestion/{token}`.
3. Rollback: revertir el deploy de frontend y backend. No hay cambios de datos ni migraciones que deshacer.
4. Jobs/notificaciones: no se tocan; C-10 los incorporará sobre los mismos endpoints.

## Open Questions

- ¿La cancelación de un turno `completado` o `ausente` debe seguir permitida para recepción? C-06 conserva el comportamiento actual; la decisión operativa puede cerrarse en C-07.
- ¿Conviene rate-limitar los endpoints públicos por token en v1.0 o alcanza con el tamaño del `manage_token`? Se difiere hasta medir tráfico real.
