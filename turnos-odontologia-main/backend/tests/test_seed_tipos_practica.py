"""Tests del seed del catálogo de prácticas (Fase 1.4 de C-04)."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.clinica.models import Clinic
from app.domain.personas.models import User  # noqa: F401  # completa el metadata
from app.domain.turnos.models import TipoPractica

NOMBRES_ESPERADOS = {
    "Limpieza",
    "Arreglo",
    "Endodoncia",
    "Extracción",
    "Ortodoncia control",
}


def _clinic(nombre: str = "Clínica Test") -> Clinic:
    return Clinic(
        id=uuid4(),
        nombre=nombre,
        timezone="America/Argentina/Buenos_Aires",
        is_active=True,
    )


def test_practicas_seed_declara_cinco_practicas_validas() -> None:
    """La constante PRACTICAS_SEED debe describir las 5 prácticas del catálogo."""
    from scripts.seed import PRACTICAS_SEED

    assert len(PRACTICAS_SEED) == 5
    assert {practica["nombre"] for practica in PRACTICAS_SEED} == NOMBRES_ESPERADOS
    assert all(int(practica["duracion_min"]) > 0 for practica in PRACTICAS_SEED)
    assert all(
        0 <= int(practica["sena_pct"]) <= 100 for practica in PRACTICAS_SEED
    )
    assert all(
        Decimal(str(practica["precio_base"])) >= Decimal("0")
        for practica in PRACTICAS_SEED
    )


@pytest.mark.asyncio
async def test_seed_practicas_crea_cinco_practicas(db_session: AsyncSession) -> None:
    """Sembrar una clínica debe crear las 5 prácticas activas."""
    from scripts.seed import PRACTICAS_SEED, seed_practicas

    clinic = _clinic()
    db_session.add(clinic)
    await db_session.flush()

    await seed_practicas(db_session, clinic.id)
    await db_session.commit()

    result = await db_session.execute(
        select(TipoPractica).where(TipoPractica.clinic_id == clinic.id)
    )
    practicas = result.scalars().all()

    assert len(practicas) == 5
    assert {p.nombre for p in practicas} == NOMBRES_ESPERADOS
    assert all(p.activa for p in practicas)
    assert all(p.is_active for p in practicas)
    # La primera clínica usa los UUID fijos del catálogo.
    assert {p.id for p in practicas} == {practica["id"] for practica in PRACTICAS_SEED}


@pytest.mark.asyncio
async def test_seed_practicas_es_idempotente(db_session: AsyncSession) -> None:
    """Ejecutar el seed dos veces sobre la misma clínica no duplica prácticas."""
    from scripts.seed import seed_practicas

    clinic = _clinic()
    db_session.add(clinic)
    await db_session.flush()

    await seed_practicas(db_session, clinic.id)
    await seed_practicas(db_session, clinic.id)
    await db_session.commit()

    result = await db_session.execute(
        select(TipoPractica).where(TipoPractica.clinic_id == clinic.id)
    )
    assert len(result.scalars().all()) == 5


@pytest.mark.asyncio
async def test_seed_practicas_no_duplica_entre_clinicas(db_session: AsyncSession) -> None:
    """La misma práctica puede existir en dos clínicas sin colisión de datos."""
    from scripts.seed import seed_practicas

    clinic_a = _clinic("Clínica A")
    clinic_b = _clinic("Clínica B")
    db_session.add_all([clinic_a, clinic_b])
    await db_session.flush()

    await seed_practicas(db_session, clinic_a.id)
    await seed_practicas(db_session, clinic_b.id)
    await db_session.commit()

    result = await db_session.execute(select(TipoPractica))
    practicas = result.scalars().all()

    assert len(practicas) == 10
    por_clinic: dict[object, set[str]] = {}
    for practica in practicas:
        por_clinic.setdefault(practica.clinic_id, set()).add(practica.nombre)
    assert por_clinic[clinic_a.id] == NOMBRES_ESPERADOS
    assert por_clinic[clinic_b.id] == NOMBRES_ESPERADOS
    assert len({p.id for p in practicas}) == 10
