"""Schemas Pydantic v2 del dominio turnos."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TipoPracticaBase(BaseModel):
    """Datos editables de una práctica odontológica."""

    nombre: str
    duracion_min: int
    precio_base: float
    sena_pct: int = 30
    activa: bool = True


class TipoPracticaCreate(TipoPracticaBase):
    """Payload de alta de práctica (el clinic_id lo aporta el contexto de auth)."""


class TipoPracticaOut(TipoPracticaBase):
    """Práctica devuelta por la API."""

    id: UUID
    clinic_id: UUID

    model_config = ConfigDict(from_attributes=True)


class TurnoCreate(BaseModel):
    """Alta de turno: el fin se deriva de la duración de la práctica."""

    paciente_id: UUID
    sillon_id: UUID
    odontologo_id: UUID
    tipo_practica_id: UUID
    inicio: datetime


class TurnoOut(BaseModel):
    """Turno interno; nunca expone manage_token."""

    id: UUID
    clinic_id: UUID
    paciente_id: UUID
    sillon_id: UUID
    odontologo_id: UUID
    tipo_practica_id: UUID
    inicio: datetime
    fin: datetime
    estado: str
    reprogramaciones_count: int
    monto_sena: float
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SillonResumenOut(BaseModel):
    """Sillón embebido en la vista pública."""

    id: UUID
    nombre: str

    model_config = ConfigDict(from_attributes=True)


class OdontologoResumenOut(BaseModel):
    """Odontólogo embebido en la vista pública (sin datos sensibles)."""

    id: UUID
    email: str

    model_config = ConfigDict(from_attributes=True)


class TurnoPublicoOut(BaseModel):
    """Vista pública de una reserva: sin datos de otros pacientes ni token."""

    id: UUID
    inicio: datetime
    fin: datetime
    estado: str
    monto_sena: float
    reprogramaciones_count: int
    tipo_practica: TipoPracticaOut
    sillon: SillonResumenOut
    odontologo: OdontologoResumenOut

    model_config = ConfigDict(from_attributes=True)


class TurnoGestionOut(TurnoPublicoOut):
    """Vista pública enriquecida con los indicadores de autogestión."""

    puede_reprogramar: bool
    puede_reprogramar_sin_sena: bool
    cancelacion_retiene_sena: bool


class TurnoCancelOut(BaseModel):
    """Resultado de cancelación con la política de seña."""

    turno: TurnoOut
    sena_retenida: bool


class ReprogramarPayload(BaseModel):
    """Nuevo horario de una reprogramación; los recursos faltantes se heredan."""

    inicio: datetime
    sillon_id: UUID | None = None
    odontologo_id: UUID | None = None


class ReprogramacionInternaOut(BaseModel):
    """Resultado interno de reprogramación; expone el token solo si es turno nuevo."""

    turno: TurnoOut
    sena_migrada: bool
    requiere_nueva_sena: bool
    manage_token: str | None = None


class SlotOut(BaseModel):
    """Hueco disponible devuelto por la disponibilidad pública."""

    inicio: datetime
    fin: datetime
    sillon_id: UUID
    odontologo_id: UUID

    model_config = ConfigDict(from_attributes=True)


class ReservaCreate(BaseModel):
    """Payload de reserva pública: sin JWT ni datos extra del paciente."""

    tipo_practica_id: UUID
    inicio: datetime
    sillon_id: UUID
    odontologo_id: UUID
    nombre: str = Field(..., min_length=1, max_length=200)
    telefono: str = Field(..., pattern=r"^\+?[1-9]\d{7,14}$")


class ReservaCreadaOut(BaseModel):
    """Reserva pública creada: única respuesta que expone el manage_token."""

    turno: TurnoPublicoOut
    manage_token: str


class CancelacionPublicaOut(BaseModel):
    """Cancelación pública con la política de seña aplicada."""

    turno: TurnoGestionOut
    sena_retenida: bool


class ReprogramacionPublicaOut(BaseModel):
    """Reprogramación pública; el token solo aparece cuando se creó un turno nuevo."""

    turno: TurnoGestionOut
    sena_migrada: bool
    requiere_nueva_sena: bool
    manage_token: str | None = None


__all__ = [
    "CancelacionPublicaOut",
    "OdontologoResumenOut",
    "ReprogramacionInternaOut",
    "ReprogramacionPublicaOut",
    "ReprogramarPayload",
    "ReservaCreate",
    "ReservaCreadaOut",
    "SillonResumenOut",
    "SlotOut",
    "TipoPracticaBase",
    "TipoPracticaCreate",
    "TipoPracticaOut",
    "TurnoCancelOut",
    "TurnoCreate",
    "TurnoGestionOut",
    "TurnoOut",
    "TurnoPublicoOut",
]
