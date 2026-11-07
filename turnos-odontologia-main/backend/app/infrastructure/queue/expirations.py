"""Ciclo de expiración de turnos pendientes de seña (C-05).

El barrido usa la base como fuente de verdad y es idempotente: puede
ejecutarse repetidamente sin efectos adicionales sobre turnos ya cancelados.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.turnos.service import TurnoService


async def ejecutar_ciclo_expiracion(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    ttl_min: int | None = None,
) -> int:
    """Cancelar los turnos vencidos, commitear y devolver la cantidad liberada."""
    expirados = await TurnoService(session).expirar_pendientes(now=now, ttl_min=ttl_min)
    await session.commit()
    return len(expirados)


__all__ = ["ejecutar_ciclo_expiracion"]
