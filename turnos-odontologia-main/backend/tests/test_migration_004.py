"""Tests de la migración 004 (turnos) y del esquema del catálogo.

La mayor parte se valida leyendo el módulo de migración y `Base.metadata`, de
modo que también aporta cobertura en SQLite. Solo las consultas a catálogos de
PostgreSQL quedan saltadas cuando la suite corre sobre SQLite.
"""

import importlib
from typing import Any

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.turnos import models as _turnos_models  # noqa: F401
from app.infrastructure.db.base import Base

MODULE_PATH = "app.infrastructure.db.migrations.versions.004_turnos"


def _migracion() -> Any:
    """Importar el módulo de migración 004."""
    return importlib.import_module(MODULE_PATH)


def test_migracion_004_cadena_de_revisiones() -> None:
    """La migración 004 encadena desde 003."""
    migracion = _migracion()
    assert migracion.revision == "004"
    assert migracion.down_revision == "003"


def test_migracion_004_tablas_y_columnas() -> None:
    """tipos_practica y turnos exponen las columnas requeridas."""
    _migracion()
    tipos = Base.metadata.tables["tipos_practica"]
    turnos = Base.metadata.tables["turnos"]

    assert {
        "id",
        "clinic_id",
        "nombre",
        "duracion_min",
        "precio_base",
        "sena_pct",
        "activa",
        "is_active",
        "created_at",
        "updated_at",
    } <= set(tipos.columns.keys())

    assert {
        "id",
        "clinic_id",
        "paciente_id",
        "sillon_id",
        "odontologo_id",
        "tipo_practica_id",
        "inicio",
        "fin",
        "estado",
        "manage_token",
        "reprogramaciones_count",
        "monto_sena",
        "is_active",
        "created_at",
        "updated_at",
    } <= set(turnos.columns.keys())

    assert "id" in {c.name for c in tipos.primary_key.columns}
    assert "id" in {c.name for c in turnos.primary_key.columns}


def test_migracion_004_checks_unique_e_indices() -> None:
    """Los CHECK, UNIQUE e índices esperados están declarados en los modelos."""
    _migracion()
    tipos = Base.metadata.tables["tipos_practica"]
    turnos = Base.metadata.tables["turnos"]

    tipos_checks = {c.name for c in tipos.constraints if isinstance(c, CheckConstraint)}
    assert "ck_tipos_practica_duracion_positiva" in tipos_checks
    assert "ck_tipos_practica_sena_pct_rango" in tipos_checks

    turnos_checks = {c.name for c in turnos.constraints if isinstance(c, CheckConstraint)}
    assert "ck_turnos_fin_mayor_inicio" in turnos_checks
    assert "ck_turnos_estado_valido" in turnos_checks

    turnos_unique = {c.name for c in turnos.constraints if isinstance(c, UniqueConstraint)}
    assert "uq_turnos_manage_token" in turnos_unique

    turnos_indexes = {i.name for i in turnos.indexes}
    assert {
        "ix_turnos_clinic_id_inicio",
        "ix_turnos_sillon_id_inicio",
        "ix_turnos_odontologo_id_inicio",
        "ix_turnos_paciente_id_inicio",
        "ix_turnos_estado",
    } <= turnos_indexes


def test_migracion_004_seed_provisorio() -> None:
    """El seed de migración define 5 prácticas con UUID fijos y valores provisorios."""
    migracion = _migracion()
    seed = migracion.PRACTICAS_SEED

    assert len(seed) == 5
    assert [p["nombre"] for p in seed] == [
        "Limpieza",
        "Arreglo",
        "Endodoncia",
        "Extracción",
        "Ortodoncia control",
    ]
    assert [p["duracion_min"] for p in seed] == [30, 45, 60, 30, 20]
    assert [p["precio_base"] for p in seed] == [15000, 25000, 40000, 20000, 12000]
    assert all(p["sena_pct"] == 30 for p in seed)
    assert len({str(p["id"]) for p in seed}) == 5


@pytest.mark.skipif(
    "sqlite" in settings.database_url,
    reason="Requires PostgreSQL for information_schema queries",
)
@pytest.mark.asyncio
async def test_migracion_004_tablas_en_postgres(db_session: AsyncSession) -> None:
    """Con PostgreSQL, ambas tablas deben existir en el esquema public."""
    from sqlalchemy import text

    result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    )
    tablas = {row[0] for row in result.fetchall()}
    assert {"tipos_practica", "turnos"} <= tablas
