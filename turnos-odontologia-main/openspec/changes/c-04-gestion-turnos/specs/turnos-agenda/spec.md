# Spec Delta — turnos-agenda

## Purpose

Define el núcleo de gestión de turnos de la clínica: catálogo mínimo de prácticas, modelo `Turno` con estados y token de gestión, cálculo de duración y seña, anti-solape por sillón y odontólogo, disponibilidad pública, reserva sin login, cancelación con ventana de 12 horas y agenda interna con RBAC.

## ADDED Requirements

### Requirement: Fin derivado de la duración de la práctica

Al crear un turno, el sistema SHALL calcular `fin` como `inicio + TipoPractica.duracion_min`; el cliente no impone `fin`. `inicio` y `fin` se persisten con timezone y el cálculo se evalúa en `America/Argentina/Buenos_Aires`. Si la práctica no existe o está inactiva, la creación SHALL fallar sin persistir el turno.

#### Scenario: Práctica de 45 minutos a las 10:00

- **WHEN** se crea un turno con `inicio = 10:00` y una práctica con `duracion_min = 45`
- **THEN** el turno persistido tiene `fin = 10:45` y `duracion_min` no se almacena en `Turno`

#### Scenario: El cliente envía un fin distinto

- **WHEN** el body de creación incluye un `fin` que no coincide con `inicio + duracion_min`
- **THEN** el sistema persiste el `fin` derivado de la práctica y no devuelve error de negocio

#### Scenario: Práctica inactiva

- **WHEN** se intenta crear un turno con un `tipo_practica_id` inactivo o inexistente
- **THEN** la API responde 404 o 422 y no se crea ningún `Turno`

### Requirement: Anti-solape por sillón

El sistema SHALL rechazar con 409 cualquier turno cuyo rango `[inicio, fin)` se intersecte con otro turno vigente del mismo `sillon_id`. Se consideran vigentes los estados `pendiente_sena`, `confirmado` y `reprogramado`. Turnos contiguos (`fin == inicio`) no se consideran solapados.

#### Scenario: Solape parcial en el mismo sillón

- **WHEN** existe un turno de 10:00 a 10:45 en el sillón A y se intenta crear otro de 10:30 a 11:15 en el sillón A
- **THEN** la API responde 409 y no persiste el segundo turno

#### Scenario: Turnos contiguos permitidos

- **WHEN** existe un turno de 10:00 a 10:45 en el sillón A y se intenta crear otro de 10:45 a 11:15 en el sillón A
- **THEN** la creación es exitosa

#### Scenario: Turno cancelado no bloquea el slot

- **WHEN** el único turno del sillón A en ese rango está en estado `cancelado`
- **THEN** se permite crear un turno nuevo en el mismo rango

### Requirement: Anti-solape por odontólogo

El sistema SHALL rechazar con 409 cualquier turno cuyo rango `[inicio, fin)` se intersecte con otro turno vigente del mismo `odontologo_id`, aunque el sillón sea distinto. La validación SHALL ejecutarse en la misma transacción que la creación.

#### Scenario: Mismo odontólogo en dos sillones

- **WHEN** el odontólogo 1 tiene un turno de 11:00 a 11:30 en el sillón A y se intenta crear otro de 11:15 a 11:45 en el sillón B
- **THEN** la API responde 409 con detalle de conflicto de odontólogo

#### Scenario: Mismo horario con otro odontólogo

- **WHEN** el sillón A está libre y se crea un turno de 11:00 a 11:30 para el odontólogo 2 mientras el odontólogo 1 atiende en el sillón B
- **THEN** la creación es exitosa

### Requirement: Snapshot del monto de seña

Al crear un turno, el sistema SHALL calcular `monto_sena = round(precio_base * sena_pct / 100)` y persistirlo en `Turno.monto_sena`. Cambios posteriores en `TipoPractica.precio_base` o `sena_pct` NO SHALL alterar turnos existentes.

#### Scenario: Cálculo con redondeo

- **WHEN** se crea un turno con `precio_base = 25000` y `sena_pct = 30`
- **THEN** `monto_sena = 7500`

#### Scenario: Cambio de arancel posterior

- **WHEN** un turno existente tiene `monto_sena = 7500` y luego la práctica cambia a `precio_base = 40000`
- **THEN** el turno conserva `monto_sena = 7500`

#### Scenario: Práctica sin seña

- **WHEN** se crea un turno con `sena_pct = 0`
- **THEN** `monto_sena = 0` y el turno se crea igualmente

### Requirement: Turno nace pendiente de seña con token único

Todo turno SHALL crearse en estado `pendiente_sena` con `reprogramaciones_count = 0` y un `manage_token` generado con `secrets.token_urlsafe(32)`. El token SHALL ser único en la tabla y no derivarse del `id` ni de datos del paciente. La API interna NO SHALL exponerlo; la reserva pública sí lo devuelve.

#### Scenario: Estado y contador iniciales

- **WHEN** se crea un turno por cualquier vía
- **THEN** `estado = pendiente_sena` y `reprogramaciones_count = 0`

#### Scenario: Tokens distintos entre turnos

- **WHEN** se crean dos turnos en el mismo request de prueba
- **THEN** sus `manage_token` son distintos, URL-safe y de al menos 40 caracteres

#### Scenario: Intento de token duplicado

- **WHEN** se fuerza la inserción de dos turnos con el mismo `manage_token`
- **THEN** la base rechaza la segunda inserción por constraint UNIQUE

### Requirement: Disponibilidad pública solo con huecos libres

`GET /api/public/slots?fecha=&tipo_practica_id=` SHALL devolver únicamente horarios libres para la práctica indicada, con `inicio` alineado a la grilla de `duracion_min` dentro del horario de atención, excluyendo turnos vigentes del sillón y del odontólogo. La respuesta NO SHALL incluir nombre, teléfono ni DNI de pacientes.

#### Scenario: Huecos según duración

- **WHEN** se consulta disponibilidad para una práctica de 30 minutos en una fecha con dos turnos tomados
- **THEN** la respuesta lista solo inicios libres de 30 minutos, cada uno con `sillon_id` y `odontologo_id`

#### Scenario: Sin datos personales

- **WHEN** se consulta disponibilidad pública
- **THEN** ningún elemento de la respuesta contiene nombre, teléfono o DNI de pacientes

#### Scenario: Fecha completa

- **WHEN** todos los horarios de atención de la fecha están ocupados
- **THEN** la respuesta es 200 con lista vacía

### Requirement: Reserva pública sin login

`POST /api/public/reservas` SHALL crear un turno sin requerir JWT, recibiendo `tipo_practica_id`, `inicio`, `sillon_id`, `odontologo_id`, `nombre` y `telefono`. Si no existe un `Paciente` con ese `telefono` en la clínica, SHALL crearlo; si existe, SHALL reutilizarlo. La respuesta SHALL incluir el turno creado y su `manage_token`.

#### Scenario: Paciente nuevo

- **WHEN** se reserva con un teléfono que no existe en la clínica
- **THEN** se crea el `Paciente` y el `Turno` asociado, y la respuesta incluye `manage_token`

#### Scenario: Paciente existente

- **WHEN** se reserva con un teléfono ya registrado en la clínica
- **THEN** no se duplica el `Paciente` y el turno se asocia al existente

#### Scenario: Slot tomado en el intervalo

- **WHEN** el slot elegido fue ocupado entre la consulta de disponibilidad y el POST
- **THEN** la API responde 409 y no crea paciente ni turno

### Requirement: Gestión pública por token y ventana de cancelación

`GET /api/public/reservas/{id}?token=` y `POST /api/public/reservas/{id}/cancelar` SHALL exigir un `manage_token` válido y responder 404 si el turno no existe o el token no coincide. La cancelación SHALL evaluar `inicio - now() >= 12h` en `America/Argentina/Buenos_Aires`: a tiempo libera el slot y habilita devolución de seña; tardía también libera el slot pero retiene la seña. En ambos casos `estado` pasa a `cancelado`.

#### Scenario: Consulta con token válido

- **WHEN** se consulta la reserva con el `manage_token` correcto
- **THEN** la API responde 200 con fecha, práctica, estado y `monto_sena` del turno

#### Scenario: Token inválido

- **WHEN** se consulta o cancela con un token que no coincide
- **THEN** la API responde 404 sin revelar si el turno existe

#### Scenario: Cancelación con 12 horas o más

- **WHEN** faltan 12 horas o más para `inicio` y el paciente cancela
- **THEN** `estado = cancelado`, el slot queda libre y la respuesta indica `sena_retenida = false`

#### Scenario: Cancelación tardía

- **WHEN** faltan menos de 12 horas para `inicio` y el paciente cancela
- **THEN** `estado = cancelado`, el slot queda libre y la respuesta indica `sena_retenida = true`

#### Scenario: Cancelación repetida

- **WHEN** se intenta cancelar un turno que ya está en estado `cancelado`
- **THEN** la API responde 409 y no modifica el turno

### Requirement: Agenda interna con filtros

`GET /api/internal/turnos` SHALL listar turnos de la clínica del JWT con filtros combinables por `fecha`, `desde`, `hasta`, `sillon_id`, `odontologo_id` y `estado`. El filtro `fecha` SHALL interpretarse en la zona de la clínica. Un usuario con rol `odonto` SHALL ver solo los turnos de su propio `odontologo_id`.

#### Scenario: Filtro por fecha y sillón

- **WHEN** se consulta la agenda con `fecha=2026-11-05` y `sillon_id=<A>`
- **THEN** solo se devuelven turnos de esa fecha en el sillón A, ordenados por `inicio`

#### Scenario: Filtro por estado

- **WHEN** se consulta con `estado=pendiente_sena`
- **THEN** la respuesta contiene únicamente turnos en ese estado

#### Scenario: Confinamiento del odontólogo

- **WHEN** un usuario con rol `odonto` consulta la agenda sin `odontologo_id`
- **THEN** la respuesta solo incluye turnos cuyo `odontologo_id` es el del usuario

### Requirement: Creación interna de turno

`POST /api/internal/turnos` SHALL permitir a recepción o admin crear un turno presencial/teléfono reutilizando el mismo motor de duración, seña y anti-solape, recibiendo `paciente_id`, `sillon_id`, `odontologo_id`, `tipo_practica_id` e `inicio`. La respuesta NO SHALL incluir `manage_token`.

#### Scenario: Alta desde mostrador

- **WHEN** recepción crea un turno con un paciente existente y un slot libre
- **THEN** se persiste en `pendiente_sena` y la respuesta no contiene `manage_token`

#### Scenario: Solape en alta interna

- **WHEN** recepción intenta crear un turno sobre un slot ya ocupado
- **THEN** la API responde 409 con el mismo detalle que la reserva pública

### Requirement: RBAC en endpoints internos

Los endpoints bajo `/api/internal/` SHALL exigir JWT Bearer válido y rol `recepcion`, `odonto` o `admin` según la operación. Sin token la respuesta SHALL ser 401; con rol no autorizado, 403. Los endpoints públicos SHALL funcionar sin cabecera `Authorization`.

#### Scenario: Sin token

- **WHEN** se llama `GET /api/internal/turnos` sin header `Authorization`
- **THEN** la respuesta es 401

#### Scenario: Rol sin permiso de escritura

- **WHEN** un usuario con rol `odonto` llama `POST /api/internal/turnos`
- **THEN** la respuesta es 403 y no se crea el turno

#### Scenario: Acceso público sin token

- **WHEN** se llama `GET /api/public/slots` sin header `Authorization`
- **THEN** la respuesta es 200

### Requirement: Esquema, constraints y seed del catálogo

La migración `004` SHALL crear `tipos_practica` y `turnos` con `CHECK (duracion_min > 0)`, `CHECK (sena_pct BETWEEN 0 AND 100)`, `CHECK (fin > inicio)`, `manage_token UNIQUE` e índices `(clinic_id,inicio)`, `(sillon_id,inicio)`, `(odontologo_id,inicio)`, `(paciente_id,inicio)`, `(estado)`. El seed SHALL insertar 5 prácticas y ser idempotente.

#### Scenario: Upgrade y downgrade

- **WHEN** se ejecuta `alembic upgrade head` y luego `alembic downgrade 003`
- **THEN** ambas tablas se crean y se eliminan sin error

#### Scenario: CHECK de rango inválido

- **WHEN** se intenta persistir un turno con `fin <= inicio`
- **THEN** la base rechaza la operación

#### Scenario: Seed ejecutado dos veces

- **WHEN** se corre el seed de prácticas dos veces
- **THEN** siguen existiendo exactamente 5 prácticas y sus valores provisorios no se duplican
