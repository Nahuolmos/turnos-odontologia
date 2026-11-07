"""Migración 005: índices de expiración de turnos y bloqueo vigente (C-05).

Agrega dos índices aditivos, sin cambios de datos ni de columnas:

- ``ix_turnos_estado_created_at``: soporta el barrido de turnos
  ``pendiente_sena`` vencidos por ``(estado, created_at)``.
- ``ix_bloqueos_paciente_id_hasta``: soporta la consulta de bloqueo vigente
  por ``(paciente_id, hasta)``.

La migración 004 ya está aplicada; por eso estos índices viven en una
revisión nueva en lugar de editar el historial existente.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crear los índices de soporte para expiración y bloqueos."""
    op.create_index(
        "ix_turnos_estado_created_at",
        "turnos",
        ["estado", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_bloqueos_paciente_id_hasta",
        "bloqueos",
        ["paciente_id", "hasta"],
        unique=False,
    )


def downgrade() -> None:
    """Eliminar los índices creados por esta revisión."""
    op.drop_index("ix_bloqueos_paciente_id_hasta", table_name="bloqueos")
    op.drop_index("ix_turnos_estado_created_at", table_name="turnos")
