# Design system

- **Mode:** off
- **Approval:** skipped
- **Decision source:** user, 2026-11-06
- **Revision:** n/a

## Decisión

El proyecto eligió no tener sistema de diseño propio ni mockups por change. El
trabajo visual usa los estilos, tokens y componentes que ya existen en
`frontend/src/` (por ejemplo `index.css`, `BookingPage.css`,
`ManageAppointmentPage.css` y el patrón de componentes de `features/booking/`).

Esta decisión es política del proyecto y no se vuelve a preguntar en cada
change. Un pedido explícito posterior del usuario puede cambiarla.

## Alcance

- No se crean `brand.md`, `brand.js`, `tokens.css`, `components.html` ni
  previews.
- No hay gate de mockups antes de implementar UI.
- Ante un pedido de rebrand o rediseño, se reabre la conversación de política
  visual.
