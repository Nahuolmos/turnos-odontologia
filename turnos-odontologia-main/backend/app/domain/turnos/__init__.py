"""Dominio turnos: catálogo de prácticas y gestión de turnos."""

from app.domain.turnos.models import (
    ESTADOS_TURNO,
    ESTADOS_VIGENTES,
    TipoPractica,
    Turno,
)

__all__ = ["ESTADOS_TURNO", "ESTADOS_VIGENTES", "TipoPractica", "Turno"]
