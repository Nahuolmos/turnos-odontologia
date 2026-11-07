"""Tests del ciclo de expiración de turnos ejecutado por el worker (C-05)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.clinica.models import Clinic, Sillon
from app.domain.personas.models import Paciente, User
from app.domain.turnos.models import TipoPractica, Turno
from app.domain.turnos.service import TurnoService
from app.infrastructure.queue.expirations import ejecutar_ciclo_expiracion
from app.infrastructure.queue.worker import ejecutar_ciclo

NOW = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)


async def _turno_pendiente(
    db_session: AsyncSession,
    *,
    minutos_creado: int,
) -> Turno:
    """Crear un turno pendiente de seña con created_at desplazado."""
    clinic = Clinic(nombre=f"Clínica {uuid4().hex[:8]}", timezone="America/Argentina/Buenos_Aires")
    db_session.add(clinic)
    await db_session.flush()
    paciente = Paciente(
        clinic_id=clinic.id,
        nombre="Paciente Worker",
        telefono=f"+54911{uuid4().int % 10_000_000:08d}",
        dni=str(uuid4().int % 100_000_000).zfill(8),
    )
    sillon = Sillon(clinic_id=clinic.id, nombre="Sillón A", activo=True)
    odontologo = User(
        clinic_id=clinic.id,
        email=f"odonto-{uuid4().hex[:8]}@clinica.com",
        password_hash="hash",
        rol="odonto",
        activo=True,
    )
    practica = TipoPractica(
        clinic_id=clinic.id,
        nombre="Práctica Worker",
        duracion_min=30,
        precio_base=Decimal("25000.00"),
        sena_pct=30,
    )
    db_session.add_all([paciente, sillon, odontologo, practica])
    await db_session.flush()

    turno = await TurnoService(db_session).crear_turno(
        clinic.id,
        paciente.id,
        sillon.id,
        odontologo.id,
        practica.id,
        datetime(2026, 11, 6, 10, 0, tzinfo=UTC),
        now=NOW,
    )
    turno.created_at = NOW - timedelta(minutes=minutos_creado)
    await db_session.flush()
    return turno


@pytest.mark.asyncio
async def test_ejecutar_ciclo_expiracion_commitea(db_session: AsyncSession) -> None:
    """El ciclo cancela los vencidos y deja el cambio persistido."""
    turno = await _turno_pendiente(db_session, minutos_creado=31)
    turno_id = turno.id

    liberados = await ejecutar_ciclo_expiracion(db_session, now=NOW, ttl_min=30)

    db_session.expire_all()
    recargado = await db_session.get(Turno, turno_id)
    assert liberados == 1
    assert recargado is not None
    assert recargado.estado == "cancelado"


@pytest.mark.asyncio
async def test_ciclo_sin_vencidos_devuelve_cero(db_session: AsyncSession) -> None:
    """Sin turnos vencidos el ciclo no libera ninguno."""
    turno = await _turno_pendiente(db_session, minutos_creado=29)
    turno_id = turno.id

    liberados = await ejecutar_ciclo_expiracion(db_session, now=NOW, ttl_min=30)

    db_session.expire_all()
    recargado = await db_session.get(Turno, turno_id)
    assert liberados == 0
    assert recargado is not None
    assert recargado.estado == "pendiente_sena"


class _SesionRota:
    """Sesión de mentira que falla al consultar la base."""

    def __init__(self) -> None:
        self.rolled_back: bool = False

    async def __aenter__(self) -> "_SesionRota":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def rollback(self) -> None:
        self.rolled_back = True

    def get_bind(self) -> Any:
        raise RuntimeError("base caída")


@pytest.mark.asyncio
async def test_ejecutar_ciclo_no_propaga_errores_de_base() -> None:
    """Un error de base en un ciclo se registra y no corta el worker."""
    sesion = _SesionRota()

    liberados = await ejecutar_ciclo(lambda: sesion)  # type: ignore[arg-type]

    assert liberados == 0
    assert sesion.rolled_back is True
