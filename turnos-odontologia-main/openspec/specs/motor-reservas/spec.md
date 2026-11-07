# motor-reservas Specification

## Purpose
Definir las reglas de admisión y ciclo de vida del turno que completan el motor de reservas: rechazo de pacientes bloqueados por ausentismo, expiración de turnos `pendiente_sena` no abonados y contrato público de disponibilidad. El modelo `Turno`, el anti-solape y la creación de reservas ya fueron entregados por C-04; esta capacidad agrega los deltas de C-05.

## Requirements

### Requirement: Bloqueo de reservas por ausentismo

El sistema SHALL rechazar la creación de un turno cuando el paciente tenga un `Bloqueo` vigente en su clínica, entendiendo por vigente aquel cuyo rango cumple `desde <= now < hasta` y `is_active = true`. La validación SHALL aplicarse tanto a la reserva pública como al alta interna. La respuesta SHALL ser **403** e incluir `bloqueado_hasta` en el cuerpo. La excepción manual de recepción con motivo auditado NO forma parte de esta capacidad (C-07).

#### Scenario: Paciente bloqueado intenta reservar en el portal público

- **WHEN** el paciente tiene un bloqueo con `hasta = now + 30 días` y envía `POST /api/public/reservas`
- **THEN** la API responde 403 con `bloqueado_hasta` igual a la fecha de fin del bloqueo
- **AND** no se crea ningún `Turno` ni se modifica el paciente

#### Scenario: Paciente bloqueado intenta un alta interna

- **WHEN** recepción envía `POST /api/internal/turnos` para un paciente con bloqueo vigente
- **THEN** la API responde 403 con `bloqueado_hasta`
- **AND** no se persiste el turno

#### Scenario: Bloqueo vencido no impide reservar

- **WHEN** el último bloqueo del paciente tiene `hasta` anterior a `now`
- **THEN** la reserva pública y el alta interna se crean normalmente

#### Scenario: Bloqueo de otra clínica no aplica

- **WHEN** el paciente tiene un bloqueo vigente en otra clínica pero ninguno en la clínica de la reserva
- **THEN** la creación del turno es exitosa

### Requirement: Expiración de turnos pendientes de seña

El sistema SHALL cancelar automáticamente todo turno en estado `pendiente_sena` cuyo `created_at` sea menor o igual a `now - MP_TTL_MIN`, donde `MP_TTL_MIN` proviene de la configuración (`Settings.mp_ttl_min`, default 30 minutos). La cancelación SHALL liberar el slot de inmediato. Los turnos en otros estados NO SHALL modificarse. El barrido SHALL ser idempotente: ejecutarlo dos veces no altera turnos ya cancelados.

#### Scenario: Turno pendiente supera el TTL

- **WHEN** un turno `pendiente_sena` fue creado hace 31 minutos y se ejecuta el barrido con `MP_TTL_MIN=30`
- **THEN** el turno pasa a `cancelado`
- **AND** su slot vuelve a aparecer en `GET /api/public/slots`

#### Scenario: Turno pendiente dentro del TTL

- **WHEN** un turno `pendiente_sena` fue creado hace 29 minutos y se ejecuta el barrido con `MP_TTL_MIN=30`
- **THEN** el turno permanece en `pendiente_sena` y el slot sigue ocupado

#### Scenario: Turno confirmado no expira

- **WHEN** un turno en estado `confirmado` fue creado hace más de 30 minutos
- **THEN** el barrido no lo modifica

#### Scenario: Barrido repetido

- **WHEN** el barrido se ejecuta dos veces sobre el mismo conjunto de turnos vencidos
- **THEN** la segunda ejecución no encuentra turnos `pendiente_sena` vencidos y no produce cambios adicionales

### Requirement: Worker periódico de expiraciones

El worker SHALL ejecutar un ciclo de expiración cada `WORKER_POLL_SECONDS` (default 60) con una sesión de base de datos propia y `commit` al finalizar cada ciclo. Un error de base de datos en un ciclo NO SHALL terminar el proceso del worker; SHALL registrarse y reintentarse en el siguiente ciclo.

#### Scenario: Ciclo exitoso

- **WHEN** el worker ejecuta un ciclo y hay turnos vencidos
- **THEN** los turnos quedan `cancelado` en la base y el worker registra la cantidad liberada

#### Scenario: Error transitorio de base de datos

- **WHEN** un ciclo falla al abrir o usar la sesión
- **THEN** el worker registra el error y continúa con el siguiente ciclo

### Requirement: Contrato público de disponibilidad

`GET /api/public/slots` SHALL aceptar el parámetro `practica` como alias de `tipo_practica_id`, manteniendo compatibilidad con el nombre anterior. La API SHALL responder **422** si no se envía ninguno de los dos o si ambos llegan con valores distintos. La respuesta SHALL seguir devolviendo únicamente huecos libres, sin datos de otras reservas.

#### Scenario: Alias `practica`

- **WHEN** el cliente llama `GET /api/public/slots?fecha=2026-11-06&practica=<uuid>`
- **THEN** la API devuelve los mismos slots que con `tipo_practica_id=<uuid>`

#### Scenario: Parámetros ambiguos

- **WHEN** el cliente envía `practica=<uuid-a>` y `tipo_practica_id=<uuid-b>` con valores distintos
- **THEN** la API responde 422 sin consultar disponibilidad

#### Scenario: Falta el identificador de práctica

- **WHEN** el cliente llama `GET /api/public/slots?fecha=2026-11-06` sin `practica` ni `tipo_practica_id`
- **THEN** la API responde 422
