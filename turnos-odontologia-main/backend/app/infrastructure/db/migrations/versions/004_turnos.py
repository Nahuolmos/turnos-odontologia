"""Migración 004: catálogo de prácticas y turnos (C-04).

Crea las tablas ``tipos_practica`` y ``turnos`` con sus CHECK, UNIQUE e índices.
Inserta un catálogo inicial de 5 prácticas asociado a la primera clínica
existente. Los valores de ``duracion_min``, ``precio_base`` y ``sena_pct`` son
PROVISORIOS: no son datos del negocio y C-13 los reemplaza con el ABM real.

El seed es idempotente por ``(clinic_id, nombre)``. Si todavía no existe una
clínica, no inserta nada (el seed de ``scripts/seed.py`` lo completa después).
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

# UUID fijos para que el seed sea determinista e idempotente.
PRACTICAS_SEED: tuple[dict[str, Any], ...] = (
    {
        "id": UUID("00000000-0000-4000-8000-000000000001"),
        "nombre": "Limpieza",
        "duracion_min": 30,
        "precio_base": Decimal("15000.00"),
        "sena_pct": 30,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000002"),
        "nombre": "Arreglo",
        "duracion_min": 45,
        "precio_base": Decimal("25000.00"),
        "sena_pct": 30,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000003"),
        "nombre": "Endodoncia",
        "duracion_min": 60,
        "precio_base": Decimal("40000.00"),
        "sena_pct": 30,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000004"),
        "nombre": "Extracción",
        "duracion_min": 30,
        "precio_base": Decimal("20000.00"),
        "sena_pct": 30,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000005"),
        "nombre": "Ortodoncia control",
        "duracion_min": 20,
        "precio_base": Decimal("12000.00"),
        "sena_pct": 30,
    },
)


def _tabla_tipos_practica() -> sa.TableClause:
    """Tabla Core liviana para insertar el seed sin depender del modelo actual."""
    return sa.table(
        "tipos_practica",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("clinic_id", postgresql.UUID(as_uuid=True)),
        sa.column("nombre", sa.String()),
        sa.column("duracion_min", sa.Integer()),
        sa.column("precio_base", sa.Numeric(12, 2)),
        sa.column("sena_pct", sa.Integer()),
        sa.column("activa", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


def _seed_practicas() -> None:
    """Insertar el catálogo provisorio en la primera clínica, sin duplicar."""
    bind = op.get_bind()
    clinic_id = bind.execute(sa.text("SELECT id FROM clinic ORDER BY created_at LIMIT 1")).scalar()
    if clinic_id is None:
        return

    tipos = _tabla_tipos_practica()
    for practica in PRACTICAS_SEED:
        existe = bind.execute(
            sa.select(tipos.c.id).where(
                tipos.c.clinic_id == clinic_id,
                tipos.c.nombre == practica["nombre"],
            )
        ).first()
        if existe is not None:
            continue
        bind.execute(
            sa.insert(tipos).values(
                id=practica["id"],
                clinic_id=clinic_id,
                nombre=practica["nombre"],
                duracion_min=practica["duracion_min"],
                precio_base=practica["precio_base"],
                sena_pct=practica["sena_pct"],
                activa=True,
                is_active=True,
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
            )
        )


def upgrade() -> None:
    op.create_table(
        "tipos_practica",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("duracion_min", sa.Integer(), nullable=False),
        sa.Column("precio_base", sa.Numeric(12, 2), nullable=False),
        sa.Column("sena_pct", sa.Integer(), server_default="30", nullable=False),
        sa.Column("activa", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "duracion_min > 0",
            name=op.f("ck_tipos_practica_duracion_positiva"),
        ),
        sa.CheckConstraint(
            "sena_pct >= 0 AND sena_pct <= 100",
            name=op.f("ck_tipos_practica_sena_pct_rango"),
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id"],
            ["clinic.id"],
            name=op.f("fk_tipos_practica_clinic_id_clinic"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tipos_practica")),
    )
    op.create_index(
        op.f("ix_tipos_practica_clinic_id"),
        "tipos_practica",
        ["clinic_id"],
        unique=False,
    )

    op.create_table(
        "turnos",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paciente_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sillon_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("odontologo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tipo_practica_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=32),
            server_default="pendiente_sena",
            nullable=False,
        ),
        sa.Column("manage_token", sa.String(length=128), nullable=False),
        sa.Column(
            "reprogramaciones_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "monto_sena",
            sa.Numeric(12, 2),
            server_default="0",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fin > inicio",
            name=op.f("ck_turnos_fin_mayor_inicio"),
        ),
        sa.CheckConstraint(
            "estado IN ('pendiente_sena', 'confirmado', 'cancelado', "
            "'reprogramado', 'completado', 'ausente')",
            name=op.f("ck_turnos_estado_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id"],
            ["clinic.id"],
            name=op.f("fk_turnos_clinic_id_clinic"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["pacientes.id"],
            name=op.f("fk_turnos_paciente_id_pacientes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sillon_id"],
            ["sillones.id"],
            name=op.f("fk_turnos_sillon_id_sillones"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["odontologo_id"],
            ["users.id"],
            name=op.f("fk_turnos_odontologo_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tipo_practica_id"],
            ["tipos_practica.id"],
            name=op.f("fk_turnos_tipo_practica_id_tipos_practica"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_turnos")),
        sa.UniqueConstraint("manage_token", name=op.f("uq_turnos_manage_token")),
    )
    op.create_index(
        "ix_turnos_clinic_id_inicio",
        "turnos",
        ["clinic_id", "inicio"],
        unique=False,
    )
    op.create_index(
        "ix_turnos_sillon_id_inicio",
        "turnos",
        ["sillon_id", "inicio"],
        unique=False,
    )
    op.create_index(
        "ix_turnos_odontologo_id_inicio",
        "turnos",
        ["odontologo_id", "inicio"],
        unique=False,
    )
    op.create_index(
        "ix_turnos_paciente_id_inicio",
        "turnos",
        ["paciente_id", "inicio"],
        unique=False,
    )
    op.create_index("ix_turnos_estado", "turnos", ["estado"], unique=False)

    _seed_practicas()


def downgrade() -> None:
    op.drop_table("turnos")
    op.drop_table("tipos_practica")
