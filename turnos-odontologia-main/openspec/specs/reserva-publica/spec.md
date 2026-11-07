# reserva-publica Specification

## Purpose
Define la autogestión de un turno por parte del paciente usando el `manage_token` como credencial portadora: consultar la reserva sin conocer su `id`, cancelarla con la política de seña de 12 horas y reprogramarla conservando o perdiendo la seña según la regla de negocio.

## Requirements

### Requirement: Consulta de reserva por token

El sistema SHALL permitir consultar un turno con `GET /api/public/reservas/gestion/{token}` sin exigir el `id` del turno, usando `manage_token` como credencial. La respuesta SHALL incluir `id`, estado, inicio, fin, práctica, sillón, odontólogo, monto de seña, cantidad de reprogramaciones e indicadores de gestión. La ruta literal `gestion` NO SHALL interpretarse como UUID. Un token inexistente SHALL responder 404. La respuesta NO SHALL exponer `manage_token` ni datos de otros pacientes.

#### Scenario: Consulta con token válido sin conocer el id

- **WHEN** el paciente llama `GET /api/public/reservas/gestion/{token}` con un `manage_token` existente
- **THEN** la API responde 200 con el turno, incluyendo `id`, `estado`, `reprogramaciones_count` y los indicadores de gestión
- **AND** la respuesta no contiene `manage_token` ni datos personales de otros pacientes

#### Scenario: Token inexistente

- **WHEN** el paciente llama la ruta de gestión con un token que no pertenece a ningún turno
- **THEN** la API responde 404
- **AND** no se devuelve ningún dato del turno

#### Scenario: Consulta de un turno ya cancelado

- **WHEN** el token corresponde a un turno en estado `cancelado`
- **THEN** la API responde 200 con `estado = "cancelado"`
- **AND** los indicadores `puede_reprogramar` y `puede_reprogramar_sin_sena` son falsos

### Requirement: Cancelación anticipada sin retención de seña

El sistema SHALL permitir cancelar un turno vigente en cualquier momento. Cuando `inicio - now >= 12 h`, la cancelación SHALL marcar el turno como `cancelado` con `sena_retenida = false` y liberar el horario de inmediato. Cancelar un turno ya cancelado SHALL responder 409. Un token que no corresponde al turno SHALL responder 404.

#### Scenario: Cancelación con 13 horas de anticipación

- **WHEN** faltan 13 horas para el inicio y el paciente cancela con el token correcto
- **THEN** la API responde 200 con `sena_retenida = false` y `estado = "cancelado"`
- **AND** el horario deja de estar ocupado en la disponibilidad

#### Scenario: Cancelación exactamente 12 horas antes

- **WHEN** `inicio - now` es exactamente 12 horas
- **THEN** la cancelación se acepta con `sena_retenida = false`

#### Scenario: Cancelación repetida

- **WHEN** el paciente intenta cancelar un turno que ya está en estado `cancelado`
- **THEN** la API responde 409
- **AND** el turno no cambia de estado

#### Scenario: Token que no corresponde al turno

- **WHEN** el paciente envía un token válido de otro turno o un token inexistente
- **THEN** la API responde 404 y no cancela el turno

### Requirement: Cancelación tardía con seña retenida

Cuando `inicio - now < 12 h`, el sistema SHALL permitir igualmente la cancelación, marcar el turno como `cancelado`, responder `sena_retenida = true` y liberar el horario de inmediato. La retención NO SHALL impedir la liberación del slot.

#### Scenario: Cancelación 6 horas antes

- **WHEN** faltan 6 horas para el inicio y el paciente cancela
- **THEN** la API responde 200 con `sena_retenida = true` y `estado = "cancelado"`
- **AND** el horario vuelve a estar disponible para otra reserva

#### Scenario: Indicador de retención en la consulta

- **WHEN** el paciente consulta un turno vigente que empieza en menos de 12 horas
- **THEN** la respuesta indica `cancelacion_retiene_sena = true`

### Requirement: Primera reprogramación conserva la seña

El sistema SHALL reprogramar sin exigir una nueva seña cuando el turno tiene `reprogramaciones_count = 0`, está vigente y tanto el horario actual como el nuevo cumplen la ventana mínima. La operación SHALL conservar `manage_token`, `monto_sena` y `estado`, actualizar inicio, fin, sillón y odontólogo, e incrementar `reprogramaciones_count` a 1. La respuesta SHALL indicar `sena_migrada = true` y `requiere_nueva_sena = false`.

#### Scenario: Primera reprogramación con 48 horas de anticipación

- **WHEN** un turno vigente con `reprogramaciones_count = 0` se reprograma a un horario libre que empieza en 48 horas
- **THEN** la API responde 200 con `sena_migrada = true` y `requiere_nueva_sena = false`
- **AND** el turno conserva su `id`, `manage_token`, `monto_sena` y `estado`
- **AND** `reprogramaciones_count` pasa a 1

#### Scenario: Seña viaja al nuevo horario

- **WHEN** el turno original tenía una seña de $7.500 y se reprograma por primera vez
- **THEN** el turno reprogramado conserva `monto_sena = 7500`
- **AND** la respuesta no incluye un `manage_token` nuevo

### Requirement: Segunda reprogramación o reprogramación tardía exige nueva seña

El sistema SHALL exigir nueva seña cuando `reprogramaciones_count >= 1` o falten menos de 12 h para el inicio actual. En ese caso SHALL cancelar el turno viejo con seña retenida y crear un turno nuevo `pendiente_sena` con `manage_token` nuevo, `monto_sena` recalculado y `reprogramaciones_count` incrementado. La respuesta SHALL indicar `sena_migrada = false`, `requiere_nueva_sena = true` y el nuevo `manage_token`.

#### Scenario: Segunda reprogramación

- **WHEN** un turno con `reprogramaciones_count = 1` se reprograma a un horario libre con al menos 12 horas de anticipación
- **THEN** el turno viejo queda `cancelado` con seña retenida
- **AND** se crea un turno nuevo `pendiente_sena` con `reprogramaciones_count = 2` y un `manage_token` distinto
- **AND** la respuesta incluye `sena_migrada = false`, `requiere_nueva_sena = true` y el nuevo `manage_token`

#### Scenario: Reprogramación tardía en la primera oportunidad

- **WHEN** un turno con `reprogramaciones_count = 0` empieza en 6 horas y se reprograma
- **THEN** el turno viejo queda `cancelado` con `sena_retenida = true`
- **AND** se crea un turno nuevo `pendiente_sena` con `reprogramaciones_count = 1` y `manage_token` nuevo

#### Scenario: La seña del turno nuevo se recalcula

- **WHEN** el precio de la práctica cambió desde la reserva original y la reprogramación exige nueva seña
- **THEN** el turno nuevo usa el `precio_base` y `sena_pct` vigentes para calcular `monto_sena`
- **AND** el monto del turno viejo no se modifica

#### Scenario: El token viejo queda asociado al turno cancelado

- **WHEN** el paciente consulta con el `manage_token` del turno viejo después de una reprogramación que exigió nueva seña
- **THEN** la consulta devuelve el turno viejo en estado `cancelado`
- **AND** el nuevo turno solo se gestiona con el `manage_token` devuelto por la reprogramación

### Requirement: Ventana mínima del nuevo horario

El sistema SHALL rechazar la reprogramación cuando `nuevo_inicio - now < 12 h`, sin modificar el turno original. El umbral SHALL ser inclusivo: exactamente 12 horas se considera válido.

#### Scenario: Nuevo horario con 11 horas de anticipación

- **WHEN** el paciente intenta reprogramar a un horario que empieza en 11 horas
- **THEN** la API responde 409 con un mensaje que explica la ventana mínima de 12 horas
- **AND** el turno original conserva su horario, estado y `reprogramaciones_count`

#### Scenario: Nuevo horario exactamente 12 horas antes

- **WHEN** el nuevo horario empieza exactamente 12 horas después de `now`
- **THEN** la reprogramación se acepta

### Requirement: Anti-solape al reprogramar

El sistema SHALL rechazar con 409 la reprogramación cuyo nuevo rango `[inicio, fin)` se solape con otro turno vigente del mismo sillón o del mismo odontólogo. La validación SHALL excluir el turno que se está reprogramando para permitir moverlo dentro del mismo recurso sin falsos positivos. Los turnos contiguos NO SHALL considerarse solapados.

#### Scenario: Solape de sillón

- **WHEN** el nuevo horario se solapa con otro turno vigente del sillón elegido
- **THEN** la API responde 409
- **AND** el turno original no se modifica

#### Scenario: Solape de odontólogo en otro sillón

- **WHEN** el nuevo horario se solapa con otro turno vigente del odontólogo elegido aunque el sillón esté libre
- **THEN** la API responde 409

#### Scenario: Mover el turno dentro del mismo sillón y horario actual

- **WHEN** el paciente reprograma al mismo inicio, sillón y odontólogo del turno actual
- **THEN** la operación no se considera solape consigo misma y la API responde 200

#### Scenario: Turno contiguo

- **WHEN** el nuevo horario empieza exactamente cuando termina otro turno vigente del mismo recurso
- **THEN** la reprogramación se acepta

### Requirement: Turnos no reprogramables

El sistema SHALL responder 409 cuando se intente reprogramar un turno en estado `cancelado`, `completado` o `ausente`. Un token inválido o un turno inexistente SHALL responder 404.

#### Scenario: Reprogramar un turno cancelado

- **WHEN** el paciente intenta reprogramar un turno en estado `cancelado`
- **THEN** la API responde 409 y no crea ni modifica turnos

#### Scenario: Reprogramar un turno completado o ausente

- **WHEN** el paciente intenta reprogramar un turno en estado `completado` o `ausente`
- **THEN** la API responde 409 con un mensaje que indica que el turno ya no se puede reprogramar

#### Scenario: Token inválido

- **WHEN** la reprogramación se envía con un token que no corresponde al turno
- **THEN** la API responde 404 y no modifica el turno

### Requirement: Reprogramación interna equivalente

El sistema SHALL ofrecer `POST /api/internal/turnos/{turno_id}/reprogramar` para recepción y odontología, autenticado con JWT y sin `manage_token`, aplicando las mismas reglas de seña, ventana y anti-solape que el flujo público. El odontólogo SHALL poder reprogramar únicamente turnos propios.

#### Scenario: Recepción reprograma sin token

- **WHEN** recepción envía `POST /api/internal/turnos/{id}/reprogramar` con un JWT válido y un nuevo horario libre
- **THEN** la API aplica la misma política de seña que el flujo público y responde 200

#### Scenario: Odontólogo reprograma un turno ajeno

- **WHEN** un odontólogo intenta reprogramar un turno cuyo `odontologo_id` no coincide con su usuario
- **THEN** la API responde 403 y no modifica el turno

#### Scenario: Reprogramación interna sin JWT

- **WHEN** se llama el endpoint interno sin token de autenticación
- **THEN** la API responde 401

### Requirement: Liberación inmediata del horario

Después de una cancelación o de una reprogramación que exige nueva seña, el horario del turno viejo SHALL quedar disponible de inmediato para una nueva reserva. Después de una reprogramación que conserva la seña, el horario viejo SHALL liberarse y el nuevo SHALL quedar ocupado.

#### Scenario: Slot cancelado re-reservable

- **WHEN** un turno se cancela y otro paciente consulta la disponibilidad de esa fecha
- **THEN** el horario liberado aparece como slot disponible
- **AND** una nueva reserva sobre ese horario se crea con éxito

#### Scenario: Reprogramación que exige nueva seña libera el horario viejo

- **WHEN** una segunda reprogramación mueve el turno a otro horario
- **THEN** el horario viejo aparece disponible y el nuevo queda ocupado

#### Scenario: Primera reprogramación mueve la ocupación

- **WHEN** una primera reprogramación cambia el turno de horario
- **THEN** el horario viejo aparece disponible y el nuevo deja de aparecer en la disponibilidad

### Requirement: Reprogramación atómica

La reprogramación SHALL ejecutarse en una única transacción. Si falla la validación o la creación del turno nuevo, el turno original SHALL permanecer vigente, con su horario, estado, seña y `manage_token` sin cambios.

#### Scenario: Falla la creación del turno nuevo

- **WHEN** una reprogramación que exige nueva seña falla después de cancelar el turno viejo
- **THEN** la transacción se revierte
- **AND** el turno viejo sigue vigente y mantiene su `manage_token`

#### Scenario: Falla la validación del nuevo horario

- **WHEN** el nuevo horario viola la ventana de 12 horas o se solapa con otro turno
- **THEN** no se persiste ningún cambio en el turno original

### Requirement: Indicadores de gestión derivados

La respuesta de gestión SHALL calcular sin persistir `puede_reprogramar`, `puede_reprogramar_sin_sena` y `cancelacion_retiene_sena`. Los tres SHALL ser falsos para estados no vigentes. `puede_reprogramar` SHALL ser verdadero para todo turno vigente; la reprogramación tardía exige nueva seña. `puede_reprogramar_sin_sena` SHALL requerir `reprogramaciones_count = 0` y al menos 12 h de anticipación. `cancelacion_retiene_sena` SHALL reflejar menos de 12 h.

#### Scenario: Turno elegible para primera reprogramación

- **WHEN** un turno vigente tiene `reprogramaciones_count = 0` y empieza en 48 horas
- **THEN** `puede_reprogramar = true`, `puede_reprogramar_sin_sena = true` y `cancelacion_retiene_sena = false`

#### Scenario: Turno con una reprogramación previa

- **WHEN** un turno vigente tiene `reprogramaciones_count = 1` y empieza en 48 horas
- **THEN** `puede_reprogramar = true` y `puede_reprogramar_sin_sena = false`

#### Scenario: Turno dentro de las próximas 12 horas

- **WHEN** un turno vigente empieza en 6 horas
- **THEN** `puede_reprogramar = true`, `cancelacion_retiene_sena = true` y `puede_reprogramar_sin_sena = false`
- **AND** la reprogramación se permite solo si el nuevo horario cumple al menos 12 horas de anticipación

#### Scenario: Turno en estado terminal

- **WHEN** el turno está `cancelado`, `completado` o `ausente`
- **THEN** `puede_reprogramar`, `puede_reprogramar_sin_sena` y `cancelacion_retiene_sena` son falsos
