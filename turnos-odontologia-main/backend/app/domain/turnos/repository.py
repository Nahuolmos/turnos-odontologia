"""Repositorios del dominio turnos."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.domain.turnos.models import ESTADOS_VIGENTES, TipoPractica, Turno


class TipoPracticaRepository(BaseRepository[TipoPractica]):
    """Acceso a datos del catálogo de prácticas."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, TipoPractica)

    async def get_activas(self, clinic_id: UUID) -> list[TipoPractica]:
        """Listar prácticas activas de una clínica."""
        result = await self.session.execute(
            select(TipoPractica)
            .where(
                TipoPractica.clinic_id == clinic_id,
                TipoPractica.activa.is_(True),
                TipoPractica.is_active.is_(True),
            )
            .order_by(TipoPractica.nombre.asc())
        )
        return list(result.scalars().all())

    async def get_by_id_and_clinic(
        self,
        clinic_id: UUID,
        tipo_practica_id: UUID,
    ) -> TipoPractica | None:
        """Obtener una práctica por id restringida a su clínica."""
        result = await self.session.execute(
            select(TipoPractica).where(
                TipoPractica.id == tipo_practica_id,
                TipoPractica.clinic_id == clinic_id,
            )
        )
        return result.scalar_one_or_none()


class TurnoRepository(BaseRepository[Turno]):
    """Acceso a datos de turnos."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Turno)

    async def get_by_id_and_clinic(self, clinic_id: UUID, turno_id: UUID) -> Turno | None:
        """Obtener un turno por id restringido a su clínica."""
        result = await self.session.execute(
            select(Turno).where(
                Turno.id == turno_id,
                Turno.clinic_id == clinic_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_manage_token(
        self,
        clinic_id: UUID,
        turno_id: UUID,
        token: str,
    ) -> Turno | None:
        """Obtener un turno solo si id y manage_token coinciden."""
        result = await self.session.execute(
            select(Turno).where(
                Turno.id == turno_id,
                Turno.clinic_id == clinic_id,
                Turno.manage_token == token,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_manage_token_solo(
        self,
        clinic_id: UUID,
        token: str,
    ) -> Turno | None:
        """Obtener un turno por manage_token dentro de su clínica (sin id)."""
        result = await self.session.execute(
            select(Turno).where(
                Turno.clinic_id == clinic_id,
                Turno.manage_token == token,
            )
        )
        return result.scalar_one_or_none()

    async def list_agenda(
        self,
        clinic_id: UUID,
        *,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        sillon_id: UUID | None = None,
        odontologo_id: UUID | None = None,
        estado: str | None = None,
    ) -> list[Turno]:
        """Listar turnos de la agenda clínica con filtros combinables."""
        query = select(Turno).where(Turno.clinic_id == clinic_id)
        if desde is not None:
            query = query.where(Turno.inicio >= desde)
        if hasta is not None:
            query = query.where(Turno.inicio < hasta)
        if sillon_id is not None:
            query = query.where(Turno.sillon_id == sillon_id)
        if odontologo_id is not None:
            query = query.where(Turno.odontologo_id == odontologo_id)
        if estado is not None:
            query = query.where(Turno.estado == estado)
        query = query.order_by(Turno.inicio.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def exists_overlap(
        self,
        clinic_id: UUID,
        *,
        inicio: datetime,
        fin: datetime,
        sillon_id: UUID | None = None,
        odontologo_id: UUID | None = None,
        excluir_turno_id: UUID | None = None,
    ) -> bool:
        """Detectar si algún turno vigente intersecta el rango [inicio, fin)."""
        if sillon_id is None and odontologo_id is None:
            return False

        query = select(Turno.id).where(
            Turno.clinic_id == clinic_id,
            Turno.inicio < fin,
            Turno.fin > inicio,
            Turno.estado.in_(ESTADOS_VIGENTES),
        )
        if sillon_id is not None:
            query = query.where(Turno.sillon_id == sillon_id)
        if odontologo_id is not None:
            query = query.where(Turno.odontologo_id == odontologo_id)
        if excluir_turno_id is not None:
            query = query.where(Turno.id != excluir_turno_id)

        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def list_pendientes_expirados(
        self,
        clinic_id: UUID | None,
        cutoff: datetime,
    ) -> list[Turno]:
        """Listar los turnos pendiente_sena creados antes del cutoff."""
        query = select(Turno).where(
            Turno.estado == "pendiente_sena",
            Turno.created_at <= cutoff,
        )
        if clinic_id is not None:
            query = query.where(Turno.clinic_id == clinic_id)
        query = query.order_by(Turno.created_at.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())


__all__ = ["TipoPracticaRepository", "TurnoRepository"]
