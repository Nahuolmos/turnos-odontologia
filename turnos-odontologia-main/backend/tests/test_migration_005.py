"""Tests de la migración 005 (índices de expiración y bloqueo vigente)."""

import importlib
from typing import Any

from app.domain.clinica import models as _clinica_models  # noqa: F401
from app.domain.turnos import models as _turnos_models  # noqa: F401
from app.infrastructure.db.base import Base

MODULE_PATH = "app.infrastructure.db.migrations.versions.005_turnos_expiracion_bloqueos"


def _migracion() -> Any:
    """Importar el módulo de migración 005."""
    return importlib.import_module(MODULE_PATH)


def test_migracion_005_cadena_de_revisiones() -> None:
    """La migración 005 encadena desde 004."""
    migracion = _migracion()
    assert migracion.revision == "005"
    assert migracion.down_revision == "004"


def test_migracion_005_indices_en_metadata() -> None:
    """Los índices de soporte están declarados en los modelos."""
    _migracion()
    turnos = Base.metadata.tables["turnos"]
    bloqueos = Base.metadata.tables["bloqueos"]

    indices_turnos = {i.name: tuple(c.name for c in i.columns) for i in turnos.indexes}
    indices_bloqueos = {i.name: tuple(c.name for c in i.columns) for i in bloqueos.indexes}

    assert indices_turnos["ix_turnos_estado_created_at"] == ("estado", "created_at")
    assert indices_bloqueos["ix_bloqueos_paciente_id_hasta"] == ("paciente_id", "hasta")


def test_migracion_005_define_upgrade_y_downgrade() -> None:
    """La migración expone upgrade y downgrade reversibles."""
    migracion = _migracion()

    assert callable(migracion.upgrade)
    assert callable(migracion.downgrade)
