"""Tests de modelos del dominio turnos (TipoPractica, Turno).

Siguen TDD: cada bloque de comportamiento se agregó después de verlo fallar.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.clinica.models import Clinic, Sillon
from app.domain.personas.models import Paciente, User
from app.domain.turnos.models import (
    ESTADOS_TURNO,
    ESTADOS_VIGENTES,
    TipoPractica,
    Turno,
)


@pytest.mark.asyncio
async def test_tipo_practica_campos_y_defaults(db_session: AsyncSession) -> None:
    """TipoPractica persiste sus campos y aplica defaults de sena_pct/activa."""
    clinic = Clinic(nombre="Clínica Prácticas", timezone="America/Argentina/Buenos_Aires")
    db_session.add(clinic)
    await db_session.flush()

    practica = TipoPractica(
        clinic_id=clinic.id,
        nombre="Limpieza",
        duracion_min=30,
        precio_base=Decimal("15000.00"),
    )
    db_session.add(practica)
    await db_session.flush()

    assert practica.id is not None
    assert practica.clinic_id == clinic.id
    assert practica.nombre == "Limpieza"
    assert practica.duracion_min == 30
    assert practica.precio_base == Decimal("15000.00")
    assert practica.sena_pct == 30
    assert practica.activa is True
    assert practica.is_active is True
    assert practica.created_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("sena_pct", [0, 100])
async def test_tipo_practica_sena_pct_limites(db_session: AsyncSession, sena_pct: int) -> None:
    """Los extremos 0 y 100 son válidos para sena_pct."""
    clinic = Clinic(nombre=f"Clínica Seña {sena_pct}", timezone="America/Argentina/Buenos_Aires")
    db_session.add(clinic)
    await db_session.flush()

    practica = TipoPractica(
        clinic_id=clinic.id,
        nombre="Práctica borde",
        duracion_min=15,
        precio_base=Decimal("1000.00"),
        sena_pct=sena_pct,
    )
    db_session.add(practica)
    await db_session.flush()

    assert practica.sena_pct == sena_pct


@pytest.mark.asyncio
@pytest.mark.parametrize("duracion_min", [0, -15])
async def test_tipo_practica_duracion_no_positiva(
    db_session: AsyncSession, duracion_min: int
) -> None:
    """duracion_min <= 0 debe ser rechazado por el CHECK de base de datos."""
    clinic = Clinic(nombre="Clínica Duración", timezone="America/Argentina/Buenos_Aires")
    db_session.add(clinic)
    await db_session.flush()

    db_session.add(
        TipoPractica(
            clinic_id=clinic.id,
            nombre="Práctica inválida",
            duracion_min=duracion_min,
            precio_base=Decimal("1000.00"),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def _contexto_turno(db_session: AsyncSession) -> dict[str, object]:
    """Crea las entidades mínimas para instanciar un Turno."""
    clinic = Clinic(nombre="Clínica Turnos", timezone="America/Argentina/Buenos_Aires")
    db_session.add(clinic)
    await db_session.flush()

    paciente = Paciente(
        clinic_id=clinic.id,
        nombre="Paciente Turno",
        telefono="+5491100000100",
        dni="30111222",
    )
    sillon = Sillon(clinic_id=clinic.id, nombre="Sillón A", activo=True)
    odontologo = User(
        clinic_id=clinic.id,
        email="odonto-turnos@clinica.com",
        password_hash="hash",
        rol="odonto",
        activo=True,
    )
    practica = TipoPractica(
        clinic_id=clinic.id,
        nombre="Limpieza",
        duracion_min=45,
        precio_base=Decimal("25000.00"),
        sena_pct=30,
    )
    db_session.add_all([paciente, sillon, odontologo, practica])
    await db_session.flush()

    return {
        "clinic": clinic,
        "paciente": paciente,
        "sillon": sillon,
        "odontologo": odontologo,
        "practica": practica,
    }


@pytest.mark.asyncio
async def test_turno_campos_y_estado_default(db_session: AsyncSession) -> None:
    """Turno persiste FKs, estado inicial y contador de reprogramaciones."""
    ctx = await _contexto_turno(db_session)
    clinic = ctx["clinic"]
    assert isinstance(clinic, Clinic)

    turno = Turno(
        clinic_id=clinic.id,
        paciente_id=ctx["paciente"].id,  # type: ignore[union-attr]
        sillon_id=ctx["sillon"].id,  # type: ignore[union-attr]
        odontologo_id=ctx["odontologo"].id,  # type: ignore[union-attr]
        tipo_practica_id=ctx["practica"].id,  # type: ignore[union-attr]
        inicio=datetime(2026, 11, 5, 10, 0),
        fin=datetime(2026, 11, 5, 10, 45),
        manage_token="token-de-prueba-000000000000000000000001",
        monto_sena=Decimal("7500.00"),
    )
    db_session.add(turno)
    await db_session.flush()

    assert turno.id is not None
    assert turno.estado == "pendiente_sena"
    assert turno.reprogramaciones_count == 0
    assert turno.monto_sena == Decimal("7500.00")
    assert turno.manage_token == "token-de-prueba-000000000000000000000001"
    assert ESTADOS_TURNO == (
        "pendiente_sena",
        "confirmado",
        "cancelado",
        "reprogramado",
        "completado",
        "ausente",
    )
    assert ESTADOS_VIGENTES == ("pendiente_sena", "confirmado", "reprogramado")


@pytest.mark.asyncio
async def test_turno_relaciones(db_session: AsyncSession) -> None:
    """Turno expone relaciones hacia Paciente, Sillon, User y TipoPractica."""
    ctx = await _contexto_turno(db_session)
    turno = Turno(
        clinic_id=ctx["clinic"].id,  # type: ignore[union-attr]
        paciente_id=ctx["paciente"].id,  # type: ignore[union-attr]
        sillon_id=ctx["sillon"].id,  # type: ignore[union-attr]
        odontologo_id=ctx["odontologo"].id,  # type: ignore[union-attr]
        tipo_practica_id=ctx["practica"].id,  # type: ignore[union-attr]
        inicio=datetime(2026, 11, 5, 11, 0),
        fin=datetime(2026, 11, 5, 11, 45),
        manage_token="token-de-prueba-000000000000000000000002",
    )
    db_session.add(turno)
    await db_session.flush()

    result = await db_session.execute(select(Turno).where(Turno.id == turno.id))
    cargado = result.scalar_one()

    assert cargado.paciente.id == ctx["paciente"].id  # type: ignore[union-attr]
    assert cargado.sillon.id == ctx["sillon"].id  # type: ignore[union-attr]
    assert cargado.odontologo.id == ctx["odontologo"].id  # type: ignore[union-attr]
    assert cargado.tipo_practica.id == ctx["practica"].id  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_turno_manage_token_unique(db_session: AsyncSession) -> None:
    """Dos turnos con el mismo manage_token violan el UNIQUE."""
    ctx = await _contexto_turno(db_session)
    token = "token-duplicado-000000000000000000000001"

    def nuevo_turno() -> Turno:
        return Turno(
            clinic_id=ctx["clinic"].id,  # type: ignore[union-attr]
            paciente_id=ctx["paciente"].id,  # type: ignore[union-attr]
            sillon_id=ctx["sillon"].id,  # type: ignore[union-attr]
            odontologo_id=ctx["odontologo"].id,  # type: ignore[union-attr]
            tipo_practica_id=ctx["practica"].id,  # type: ignore[union-attr]
            inicio=datetime(2026, 11, 5, 10, 0),
            fin=datetime(2026, 11, 5, 10, 45),
            manage_token=token,
        )

    db_session.add(nuevo_turno())
    await db_session.flush()

    db_session.add(nuevo_turno())
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("fin", [datetime(2026, 11, 5, 10, 0), datetime(2026, 11, 5, 9, 0)])
async def test_turno_check_fin_mayor_inicio(db_session: AsyncSession, fin: datetime) -> None:
    """fin == inicio y fin < inicio deben ser rechazados por el CHECK."""
    ctx = await _contexto_turno(db_session)
    db_session.add(
        Turno(
            clinic_id=ctx["clinic"].id,  # type: ignore[union-attr]
            paciente_id=ctx["paciente"].id,  # type: ignore[union-attr]
            sillon_id=ctx["sillon"].id,  # type: ignore[union-attr]
            odontologo_id=ctx["odontologo"].id,  # type: ignore[union-attr]
            tipo_practica_id=ctx["practica"].id,  # type: ignore[union-attr]
            inicio=datetime(2026, 11, 5, 10, 0),
            fin=fin,
            manage_token="token-fin-invalido-00000000000000000001",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


def test_schemas_turno_create_no_acepta_fin() -> None:
    """TurnoCreate no declara fin: lo deriva el servicio."""
    from app.domain.turnos.schemas import TurnoCreate

    assert "fin" not in TurnoCreate.model_fields
    assert set(TurnoCreate.model_fields) == {
        "paciente_id",
        "sillon_id",
        "odontologo_id",
        "tipo_practica_id",
        "inicio",
    }


def test_schema_turno_out_oculta_manage_token() -> None:
    """TurnoOut expone todos los campos salvo manage_token y con dinero float."""
    from app.domain.turnos.schemas import TurnoOut

    assert "manage_token" not in TurnoOut.model_fields
    assert TurnoOut.model_fields["monto_sena"].annotation is float
    assert TurnoOut.model_config.get("from_attributes") is True


def test_schema_publico_no_expone_datos_de_paciente() -> None:
    """TurnoPublicoOut no incluye identificadores ni datos del paciente."""
    from app.domain.turnos.schemas import TurnoPublicoOut

    campos = set(TurnoPublicoOut.model_fields)
    assert campos == {
        "id",
        "inicio",
        "fin",
        "estado",
        "monto_sena",
        "tipo_practica",
        "sillon",
        "odontologo",
        "reprogramaciones_count",
    }
    assert "paciente_id" not in campos
    assert "manage_token" not in campos


def test_schema_cancelacion_y_slot() -> None:
    """TurnoCancelOut y SlotOut exponen los campos esperados."""
    from app.domain.turnos.schemas import SlotOut, TurnoCancelOut

    assert set(TurnoCancelOut.model_fields) == {"turno", "sena_retenida"}
    assert set(SlotOut.model_fields) == {"inicio", "fin", "sillon_id", "odontologo_id"}
    assert SlotOut.model_config.get("from_attributes") is True
