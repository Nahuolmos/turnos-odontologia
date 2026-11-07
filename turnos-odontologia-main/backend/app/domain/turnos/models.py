"""Modelos del dominio turnos: catálogo de prácticas y turnos."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.mixins import AuditMixin
from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.domain.clinica.models import Clinic, Sillon
    from app.domain.personas.models import Paciente, User

ESTADOS_TURNO: tuple[str, ...] = (
    "pendiente_sena",
    "confirmado",
    "cancelado",
    "reprogramado",
    "completado",
    "ausente",
)

ESTADOS_VIGENTES: tuple[str, ...] = ("pendiente_sena", "confirmado", "reprogramado")


class TipoPractica(Base, AuditMixin):
    """Práctica odontológica con duración, precio base y porcentaje de seña."""

    __tablename__ = "tipos_practica"
    __table_args__ = (
        CheckConstraint("duracion_min > 0", name="ck_tipos_practica_duracion_positiva"),
        CheckConstraint(
            "sena_pct >= 0 AND sena_pct <= 100",
            name="ck_tipos_practica_sena_pct_rango",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    clinic_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinic.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    duracion_min: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    sena_pct: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    activa: Mapped[bool] = mapped_column(default=True, nullable=False)

    clinic: Mapped["Clinic"] = relationship("Clinic")


class Turno(Base, AuditMixin):
    """Turno reservado en la agenda de la clínica."""

    __tablename__ = "turnos"
    __table_args__ = (
        CheckConstraint("fin > inicio", name="ck_turnos_fin_mayor_inicio"),
        CheckConstraint(
            "estado IN (" + ", ".join(f"'{estado}'" for estado in ESTADOS_TURNO) + ")",
            name="ck_turnos_estado_valido",
        ),
        UniqueConstraint("manage_token", name="uq_turnos_manage_token"),
        Index("ix_turnos_clinic_id_inicio", "clinic_id", "inicio"),
        Index("ix_turnos_sillon_id_inicio", "sillon_id", "inicio"),
        Index("ix_turnos_odontologo_id_inicio", "odontologo_id", "inicio"),
        Index("ix_turnos_paciente_id_inicio", "paciente_id", "inicio"),
        Index("ix_turnos_estado", "estado"),
        Index("ix_turnos_estado_created_at", "estado", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    clinic_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinic.id", ondelete="CASCADE"),
        nullable=False,
    )
    paciente_id: Mapped[UUID] = mapped_column(
        ForeignKey("pacientes.id", ondelete="CASCADE"),
        nullable=False,
    )
    sillon_id: Mapped[UUID] = mapped_column(
        ForeignKey("sillones.id", ondelete="CASCADE"),
        nullable=False,
    )
    odontologo_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo_practica_id: Mapped[UUID] = mapped_column(
        ForeignKey("tipos_practica.id", ondelete="CASCADE"),
        nullable=False,
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(32),
        default="pendiente_sena",
        nullable=False,
    )
    manage_token: Mapped[str] = mapped_column(String(128), nullable=False)
    reprogramaciones_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monto_sena: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )

    paciente: Mapped["Paciente"] = relationship("Paciente", lazy="joined")
    sillon: Mapped["Sillon"] = relationship("Sillon", lazy="joined")
    odontologo: Mapped["User"] = relationship(
        "User",
        foreign_keys=[odontologo_id],
        lazy="joined",
    )
    tipo_practica: Mapped["TipoPractica"] = relationship("TipoPractica", lazy="joined")


__all__ = ["ESTADOS_TURNO", "ESTADOS_VIGENTES", "TipoPractica", "Turno"]
