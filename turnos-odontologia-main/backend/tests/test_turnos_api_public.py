"""Tests de integración de la API pública de turnos (Fase 4)."""

from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public.turnos import get_turno_service
from app.domain.clinica.models import Bloqueo, Clinic, Sillon
from app.domain.personas.models import Paciente, User
from app.domain.turnos.models import TipoPractica, Turno
from app.domain.turnos.schemas import TurnoGestionOut, TurnoPublicoOut
from app.domain.turnos.service import TurnoService
from app.infrastructure.db.base import get_db
from app.main import create_app

INICIO = datetime(2026, 11, 6, 10, 0, tzinfo=UTC)
TZ_CLINICA = ZoneInfo("America/Argentina/Buenos_Aires")


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """Cliente HTTP ASGI sin JWT que comparte la sesión de db_session."""
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@dataclass
class Contexto:
    """Entidades mínimas para ejercitar la API pública."""

    clinic: Clinic
    paciente: Paciente
    sillon: Sillon
    odontologo: User
    practica: TipoPractica


async def _contexto(
    db_session: AsyncSession,
    *,
    duracion_min: int = 30,
    activa: bool = True,
    sena_pct: int = 30,
) -> Contexto:
    clinic = Clinic(
        nombre=f"Clínica {uuid4().hex[:8]}",
        timezone="America/Argentina/Buenos_Aires",
    )
    db_session.add(clinic)
    await db_session.flush()
    paciente = Paciente(
        clinic_id=clinic.id,
        nombre="Paciente Existente",
        telefono="+5491100000001",
        dni="30111222",
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
        nombre="Práctica Test",
        duracion_min=duracion_min,
        precio_base=Decimal("25000.00"),
        sena_pct=sena_pct,
        activa=activa,
    )
    db_session.add_all([paciente, sillon, odontologo, practica])
    await db_session.flush()
    await db_session.commit()
    return Contexto(clinic, paciente, sillon, odontologo, practica)


def _payload(
    ctx: Contexto,
    *,
    inicio: datetime = INICIO,
    telefono: str = "+5491122334455",
    nombre: str = "Ana Pérez",
) -> dict[str, str]:
    return {
        "tipo_practica_id": str(ctx.practica.id),
        "inicio": inicio.isoformat(),
        "sillon_id": str(ctx.sillon.id),
        "odontologo_id": str(ctx.odontologo.id),
        "nombre": nombre,
        "telefono": telefono,
    }


def _slots_url(ctx: Contexto, fecha: str = "2026-11-06") -> str:
    return f"/api/public/slots?fecha={fecha}&tipo_practica_id={ctx.practica.id}"


async def test_slots_sin_auth_200_y_sin_datos_personales(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La disponibilidad es pública y no expone datos del paciente."""
    ctx = await _contexto(db_session, duracion_min=30)

    response = await client.get(_slots_url(ctx))

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 20
    assert all(
        set(item) == {"inicio", "fin", "sillon_id", "odontologo_id"} for item in data
    )
    texto = response.text
    assert ctx.paciente.nombre not in texto
    assert ctx.paciente.telefono not in texto
    assert ctx.paciente.dni not in texto


async def test_slots_excluye_ocupados_y_respeta_duracion(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Los huecos ocupados se excluyen y cada slot dura lo que la práctica."""
    ctx = await _contexto(db_session, duracion_min=30)
    await db_session.commit()
    await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime(2026, 11, 6, 10, 0, tzinfo=TZ_CLINICA),
    )
    await db_session.commit()

    response = await client.get(_slots_url(ctx))

    assert response.status_code == 200
    data = response.json()
    inicios = {datetime.fromisoformat(item["inicio"]).replace(tzinfo=None) for item in data}
    assert datetime(2026, 11, 6, 10, 0) not in inicios
    assert datetime(2026, 11, 6, 10, 30) in inicios
    for item in data:
        inicio = datetime.fromisoformat(item["inicio"]).replace(tzinfo=None)
        fin = datetime.fromisoformat(item["fin"]).replace(tzinfo=None)
        assert fin - inicio == timedelta(minutes=30)


async def test_slots_dia_completo_lista_vacia(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un día completo responde 200 con lista vacía."""
    ctx = await _contexto(db_session, duracion_min=600)
    await db_session.commit()
    await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime(2026, 11, 6, 9, 0, tzinfo=TZ_CLINICA),
    )
    await db_session.commit()

    response = await client.get(_slots_url(ctx))

    assert response.status_code == 200
    assert response.json() == []


async def test_slots_practica_inexistente_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Una práctica inexistente o inactiva responde 404."""
    ctx = await _contexto(db_session, activa=False)

    response = await client.get(_slots_url(ctx))

    assert response.status_code == 404


async def test_reserva_publica_crea_paciente_y_turno(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La reserva pública crea paciente y turno y devuelve manage_token."""
    ctx = await _contexto(db_session)
    telefono = "+5491133344455"
    payload = _payload(ctx, telefono=telefono)

    response = await client.post("/api/public/reservas", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert len(data["manage_token"]) >= 40
    assert data["turno"]["estado"] == "pendiente_sena"
    assert "manage_token" not in data["turno"]
    assert "paciente_id" not in data["turno"]
    paciente = await db_session.scalar(
        select(Paciente).where(
            Paciente.clinic_id == ctx.clinic.id,
            Paciente.telefono == telefono,
        )
    )
    turno = await db_session.scalar(
        select(Turno).where(Turno.id == UUID(data["turno"]["id"]))
    )
    assert paciente is not None
    assert turno is not None
    assert turno.paciente_id == paciente.id


async def test_reserva_publica_reutiliza_paciente(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un teléfono ya registrado reutiliza el paciente existente."""
    ctx = await _contexto(db_session)
    paciente_id = ctx.paciente.id
    payload = _payload(ctx, telefono=ctx.paciente.telefono)

    response = await client.post("/api/public/reservas", json=payload)

    assert response.status_code == 201
    total = await db_session.scalar(
        select(func.count())
        .select_from(Paciente)
        .where(
            Paciente.clinic_id == ctx.clinic.id,
            Paciente.telefono == ctx.paciente.telefono,
        )
    )
    assert total == 1
    turno = await db_session.scalar(
        select(Turno).where(Turno.id == UUID(response.json()["turno"]["id"]))
    )
    assert turno is not None
    assert turno.paciente_id == paciente_id


async def test_reserva_publica_conflicto_409_no_crea_paciente_ni_turno(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un slot tomado responde 409 sin persistir paciente ni turno."""
    ctx = await _contexto(db_session)
    clinic_id = ctx.clinic.id
    await db_session.commit()
    await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        INICIO,
    )
    await db_session.commit()
    telefono = "+5491166677788"

    response = await client.post(
        "/api/public/reservas",
        json=_payload(ctx, telefono=telefono),
    )

    assert response.status_code == 409
    pacientes = await db_session.scalar(
        select(func.count())
        .select_from(Paciente)
        .where(Paciente.clinic_id == clinic_id, Paciente.telefono == telefono)
    )
    turnos = await db_session.scalar(
        select(func.count()).select_from(Turno).where(Turno.clinic_id == clinic_id)
    )
    assert pacientes == 0
    assert turnos == 1


@pytest.mark.parametrize("telefono", ["123456", "+0123456789", "abcdefgh", "+5491122"])
async def test_reserva_publica_telefono_invalido_422(
    client: AsyncClient, db_session: AsyncSession, telefono: str
) -> None:
    """Un teléfono que no matchea E.164-ish responde 422."""
    ctx = await _contexto(db_session)

    response = await client.post(
        "/api/public/reservas",
        json=_payload(ctx, telefono=telefono),
    )

    assert response.status_code == 422


async def test_consulta_publica_con_token_ok_y_sin_datos_sensibles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET con token válido devuelve la reserva sin datos sensibles."""
    ctx = await _contexto(db_session)
    reserva = await client.post("/api/public/reservas", json=_payload(ctx))
    assert reserva.status_code == 201
    body = reserva.json()

    response = await client.get(
        f"/api/public/reservas/{body['turno']['id']}",
        params={"token": body["manage_token"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == body["turno"]["id"]
    assert data["estado"] == "pendiente_sena"
    assert "manage_token" not in data
    assert "paciente_id" not in data
    assert "telefono" not in data
    assert "dni" not in data


async def test_consulta_publica_token_invalido_o_id_inexistente_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Token incorrecto o id inexistente responden 404."""
    ctx = await _contexto(db_session)
    reserva = await client.post("/api/public/reservas", json=_payload(ctx))
    turno_id = reserva.json()["turno"]["id"]

    token_incorrecto = await client.get(
        f"/api/public/reservas/{turno_id}", params={"token": "token-invalido"}
    )
    sin_token = await client.get(f"/api/public/reservas/{turno_id}")
    inexistente = await client.get(
        f"/api/public/reservas/{uuid4()}", params={"token": reserva.json()["manage_token"]}
    )

    assert token_incorrecto.status_code == 404
    assert sin_token.status_code == 404
    assert inexistente.status_code == 404


async def test_cancelar_publico_a_tiempo_y_tardio(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La cancelación pública distingue a tiempo y tardía."""
    ctx = await _contexto(db_session)
    await db_session.commit()
    service = TurnoService(db_session)
    ahora = datetime.now(UTC)
    a_tiempo = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(days=3),
    )
    tardio = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=2),
    )
    await db_session.commit()
    a_tiempo_id, a_tiempo_token = a_tiempo.id, a_tiempo.manage_token
    tardio_id, tardio_token = tardio.id, tardio.manage_token

    response_a_tiempo = await client.post(
        f"/api/public/reservas/{a_tiempo_id}/cancelar",
        params={"token": a_tiempo_token},
    )
    response_tardio = await client.post(
        f"/api/public/reservas/{tardio_id}/cancelar",
        params={"token": tardio_token},
    )

    assert response_a_tiempo.status_code == 200
    assert response_a_tiempo.json()["sena_retenida"] is False
    assert response_a_tiempo.json()["turno"]["estado"] == "cancelado"
    assert response_tardio.status_code == 200
    assert response_tardio.json()["sena_retenida"] is True
    assert response_tardio.json()["turno"]["estado"] == "cancelado"


async def test_tipos_practica_publico_sin_auth_solo_activas_de_la_clinica_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """El catálogo público no exige auth y solo expone prácticas activas."""
    ctx = await _contexto(db_session, duracion_min=45)
    inactiva = TipoPractica(
        clinic_id=ctx.clinic.id,
        nombre="Práctica Inactiva",
        duracion_min=30,
        precio_base=Decimal("10000.00"),
        sena_pct=10,
        activa=False,
    )
    otra = Clinic(
        nombre="Otra clínica",
        timezone="America/Argentina/Buenos_Aires",
        created_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    db_session.add_all([inactiva, otra])
    await db_session.flush()
    practica_ajena = TipoPractica(
        clinic_id=otra.id,
        nombre="Práctica Ajena",
        duracion_min=30,
        precio_base=Decimal("9999.00"),
        sena_pct=30,
        activa=True,
    )
    db_session.add(practica_ajena)
    await db_session.flush()
    await db_session.commit()

    response = await client.get("/api/public/tipos-practica")

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [str(ctx.practica.id)]
    assert data[0]["duracion_min"] == 45
    assert str(inactiva.id) not in {item["id"] for item in data}
    assert str(practica_ajena.id) not in {item["id"] for item in data}


async def test_tipos_practica_publico_sin_practicas_200_vacio(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sin prácticas activas el catálogo público responde 200 con lista vacía."""
    await _contexto(db_session, activa=False)

    response = await client.get("/api/public/tipos-practica")

    assert response.status_code == 200
    assert response.json() == []


async def test_cancelar_publico_token_invalido_404_y_repetido_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Token inválido responde 404 y cancelar dos veces responde 409."""
    ctx = await _contexto(db_session)
    await db_session.commit()
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime.now(UTC) + timedelta(days=3),
    )
    await db_session.commit()
    turno_id, token = turno.id, turno.manage_token

    con_token_incorrecto = await client.post(
        f"/api/public/reservas/{turno_id}/cancelar",
        params={"token": "token-invalido"},
    )
    primera = await client.post(
        f"/api/public/reservas/{turno_id}/cancelar", params={"token": token}
    )
    segunda = await client.post(
        f"/api/public/reservas/{turno_id}/cancelar", params={"token": token}
    )

    assert con_token_incorrecto.status_code == 404
    assert primera.status_code == 200
    assert segunda.status_code == 409


async def _agregar_bloqueo(
    db_session: AsyncSession,
    ctx: Contexto,
    *,
    desde: datetime,
    hasta: datetime,
    is_active: bool = True,
) -> Bloqueo:
    """Crear un bloqueo para el paciente del contexto."""
    bloqueo = Bloqueo(
        clinic_id=ctx.clinic.id,
        paciente_id=ctx.paciente.id,
        desde=desde,
        hasta=hasta,
        motivo="Ausentismo",
        is_active=is_active,
    )
    db_session.add(bloqueo)
    await db_session.flush()
    await db_session.commit()
    return bloqueo


async def test_reserva_publica_paciente_bloqueado_403_con_bloqueado_hasta(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un paciente bloqueado recibe 403 con la fecha de fin del bloqueo."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    hasta = ahora + timedelta(days=30)
    await _agregar_bloqueo(db_session, ctx, desde=ahora - timedelta(days=1), hasta=hasta)

    response = await client.post(
        "/api/public/reservas",
        json=_payload(ctx, telefono=ctx.paciente.telefono),
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert "bloqueado_hasta" in detail
    devuelto = datetime.fromisoformat(detail["bloqueado_hasta"])
    assert devuelto.replace(tzinfo=None) == hasta.replace(tzinfo=None)
    total = await db_session.scalar(select(func.count()).select_from(Turno))
    assert total == 0


async def test_bloqueo_vencido_permite_reserva_publica(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un bloqueo terminado no impide la reserva pública."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    await _agregar_bloqueo(
        db_session,
        ctx,
        desde=ahora - timedelta(days=30),
        hasta=ahora - timedelta(minutes=1),
    )

    response = await client.post(
        "/api/public/reservas",
        json=_payload(ctx, telefono=ctx.paciente.telefono),
    )

    assert response.status_code == 201


async def test_slots_acepta_alias_practica(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """El alias practica devuelve los mismos slots que tipo_practica_id."""
    ctx = await _contexto(db_session)

    con_id = await client.get(_slots_url(ctx))
    con_alias = await client.get(
        f"/api/public/slots?fecha=2026-11-06&practica={ctx.practica.id}"
    )
    con_ambos_iguales = await client.get(
        f"/api/public/slots?fecha=2026-11-06"
        f"&practica={ctx.practica.id}&tipo_practica_id={ctx.practica.id}"
    )

    assert con_alias.status_code == 200
    assert con_alias.json() == con_id.json()
    assert con_ambos_iguales.status_code == 200
    assert con_ambos_iguales.json() == con_id.json()


async def test_slots_parametros_ambiguos_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """practica y tipo_practica_id distintos responden 422."""
    ctx = await _contexto(db_session)

    response = await client.get(
        f"/api/public/slots?fecha=2026-11-06"
        f"&practica={ctx.practica.id}&tipo_practica_id={uuid4()}"
    )

    assert response.status_code == 422


async def test_slots_sin_practica_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sin practica ni tipo_practica_id responde 422."""
    response = await client.get("/api/public/slots?fecha=2026-11-06")

    assert response.status_code == 422


async def test_schema_turno_publico_out_expone_reprogramaciones_count(
    db_session: AsyncSession,
) -> None:
    """La vista pública incluye el contador persistido de reprogramaciones."""
    ctx = await _contexto(db_session)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime.now(UTC) + timedelta(hours=48),
    )

    out = TurnoPublicoOut.model_validate(turno)

    assert out.reprogramaciones_count == 0


async def test_schema_turno_gestion_out_expone_los_tres_flags(
    db_session: AsyncSession,
) -> None:
    """La vista de gestión agrega los indicadores calculados por el servicio."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=48),
    )
    indicadores = TurnoService(db_session).indicadores_gestion(turno, now=ahora)

    out = TurnoGestionOut(
        **TurnoPublicoOut.model_validate(turno).model_dump(),
        **asdict(indicadores),
    )

    assert out.puede_reprogramar is True
    assert out.puede_reprogramar_sin_sena is True
    assert out.cancelacion_retiene_sena is False
    assert out.reprogramaciones_count == 0


async def test_gestion_por_token_200_con_flags_y_sin_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /reservas/gestion/{token} resuelve la reserva sin conocer el id."""
    ctx = await _contexto(db_session)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime.now(UTC) + timedelta(hours=48),
    )
    await db_session.commit()

    response = await client.get(f"/api/public/reservas/gestion/{turno.manage_token}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(turno.id)
    assert data["estado"] == "pendiente_sena"
    assert data["reprogramaciones_count"] == 0
    assert data["puede_reprogramar"] is True
    assert data["puede_reprogramar_sin_sena"] is True
    assert data["cancelacion_retiene_sena"] is False
    assert "manage_token" not in data
    assert "paciente_id" not in data
    assert "telefono" not in data
    assert "dni" not in data


async def test_gestion_por_token_inexistente_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un token desconocido responde 404 sin datos del turno."""
    await _contexto(db_session)

    response = await client.get("/api/public/reservas/gestion/token-inexistente")

    assert response.status_code == 404


async def test_gestion_por_token_cancelado_200_con_flags_falsos(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un turno cancelado se consulta pero no ofrece acciones de gestión."""
    ctx = await _contexto(db_session)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime.now(UTC) + timedelta(hours=6),
    )
    turno.estado = "cancelado"
    await db_session.commit()

    response = await client.get(f"/api/public/reservas/gestion/{turno.manage_token}")

    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "cancelado"
    assert data["puede_reprogramar"] is False
    assert data["puede_reprogramar_sin_sena"] is False
    assert data["cancelacion_retiene_sena"] is False


async def test_gestion_literal_no_se_interpreta_como_uuid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La ruta literal gestion/abc responde 404 y no 422 por parseo de UUID."""
    await _contexto(db_session)

    response = await client.get("/api/public/reservas/gestion/abc")

    assert response.status_code == 404


@asynccontextmanager
async def _client_con_reloj(db_session: AsyncSession, ahora: datetime):
    """Cliente ASGI que comparte sesión y fija el reloj del TurnoService."""
    app = create_app()
    service = TurnoService(db_session, now=lambda: ahora)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_turno_service] = lambda: service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_cancelacion_publica_devuelve_gestion_con_flags(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La respuesta de cancelación incluye contador y flags terminales."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=13),
    )
    await db_session.commit()

    response = await client.post(
        f"/api/public/reservas/{turno.id}/cancelar",
        params={"token": turno.manage_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sena_retenida"] is False
    assert data["turno"]["estado"] == "cancelado"
    assert data["turno"]["reprogramaciones_count"] == 0
    assert data["turno"]["puede_reprogramar"] is False
    assert data["turno"]["puede_reprogramar_sin_sena"] is False
    assert data["turno"]["cancelacion_retiene_sena"] is False
    assert "manage_token" not in data["turno"]


async def test_cancelacion_publica_tardia_retiene_sena_y_flags_terminales(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Con 6 h de anticipación retiene la seña y deshabilita la gestión."""
    ctx = await _contexto(db_session)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime.now(UTC) + timedelta(hours=6),
    )
    await db_session.commit()

    response = await client.post(
        f"/api/public/reservas/{turno.id}/cancelar",
        params={"token": turno.manage_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sena_retenida"] is True
    assert data["turno"]["cancelacion_retiene_sena"] is False


async def test_cancelacion_publica_exactamente_12h_no_retiene(
    db_session: AsyncSession,
) -> None:
    """Exactamente 12 h de anticipación no retiene la seña (umbral inclusivo)."""
    ctx = await _contexto(db_session)
    ahora = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
    service = TurnoService(db_session, now=lambda: ahora)
    turno = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=12),
    )
    await db_session.commit()

    async with _client_con_reloj(db_session, ahora) as client:
        response = await client.post(
            f"/api/public/reservas/{turno.id}/cancelar",
            params={"token": turno.manage_token},
        )

    assert response.status_code == 200
    assert response.json()["sena_retenida"] is False


async def test_slot_cancelado_reaparece_y_se_re_reserva(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Cancelar libera el horario y permite una nueva reserva en el mismo slot."""
    ctx = await _contexto(db_session)
    inicio_local = datetime(2026, 11, 20, 10, 0, tzinfo=TZ_CLINICA)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        inicio_local,
    )
    await db_session.commit()
    url_slots = (
        f"/api/public/slots?fecha=2026-11-20&tipo_practica_id={ctx.practica.id}"
    )
    slots_ocupado = await client.get(url_slots)
    inicios_ocupado = {
        datetime.fromisoformat(item["inicio"]).replace(tzinfo=None)
        for item in slots_ocupado.json()
    }
    assert datetime(2026, 11, 20, 10, 0) not in inicios_ocupado

    cancelada = await client.post(
        f"/api/public/reservas/{turno.id}/cancelar",
        params={"token": turno.manage_token},
    )
    slots_libre = await client.get(url_slots)
    inicios_libre = {
        datetime.fromisoformat(item["inicio"]).replace(tzinfo=None)
        for item in slots_libre.json()
    }

    assert cancelada.status_code == 200
    assert datetime(2026, 11, 20, 10, 0) in inicios_libre

    re_reserva = await client.post(
        "/api/public/reservas",
        json=_payload(ctx, inicio=inicio_local, telefono="+5491177788899"),
    )

    assert re_reserva.status_code == 201
    assert re_reserva.json()["turno"]["id"] != str(turno.id)


def _url_reprogramar(turno_id: UUID, token: str) -> str:
    """Construir la URL pública de reprogramación con el token como query."""
    return f"/api/public/reservas/{turno_id}/reprogramar?token={token}"


async def test_reprogramar_publico_primera_vez_200_sin_token_nuevo(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La primera reprogramación conserva id, token y seña; no devuelve token."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=48),
    )
    await db_session.commit()
    turno_id = turno.id
    token = turno.manage_token

    response = await client.post(
        _url_reprogramar(turno_id, token),
        json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["turno"]["id"] == str(turno_id)
    assert data["turno"]["estado"] == "pendiente_sena"
    assert data["turno"]["reprogramaciones_count"] == 1
    assert data["turno"]["monto_sena"] == 7500.0
    assert data["turno"]["puede_reprogramar"] is True
    assert data["turno"]["puede_reprogramar_sin_sena"] is False
    assert data["sena_migrada"] is True
    assert data["requiere_nueva_sena"] is False
    assert data.get("manage_token") is None
    assert "manage_token" not in data["turno"]


async def test_reprogramar_publico_segunda_vez_devuelve_token_nuevo(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La segunda reprogramación crea un turno y devuelve su manage_token."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=48),
    )
    turno.reprogramaciones_count = 1
    await db_session.commit()
    turno_id = turno.id
    token_viejo = turno.manage_token

    response = await client.post(
        _url_reprogramar(turno_id, token_viejo),
        json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["turno"]["id"] != str(turno_id)
    assert data["turno"]["reprogramaciones_count"] == 2
    assert data["sena_migrada"] is False
    assert data["requiere_nueva_sena"] is True
    token_nuevo = data["manage_token"]
    assert token_nuevo is not None
    assert token_nuevo != token_viejo

    viejo = await client.get(f"/api/public/reservas/gestion/{token_viejo}")
    nuevo = await client.get(f"/api/public/reservas/gestion/{token_nuevo}")

    assert viejo.status_code == 200
    assert viejo.json()["estado"] == "cancelado"
    assert viejo.json()["id"] == str(turno_id)
    assert nuevo.status_code == 200
    assert nuevo.json()["id"] == data["turno"]["id"]
    assert nuevo.json()["estado"] == "pendiente_sena"


async def test_reprogramar_publico_token_invalido_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un token que no corresponde al turno responde 404 sin modificarlo."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=48),
    )
    turno_id = turno.id
    await db_session.commit()

    response = await client.post(
        _url_reprogramar(turno_id, "token-invalido"),
        json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
    )

    assert response.status_code == 404
    recargado = await db_session.get(Turno, turno_id)
    assert recargado is not None
    assert recargado.reprogramaciones_count == 0


async def test_reprogramar_publico_solape_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un nuevo horario ocupado responde 409 y no muta el turno original."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    service = TurnoService(db_session)
    turno = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=48),
    )
    await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=72),
    )
    turno_id = turno.id
    token = turno.manage_token
    await db_session.commit()

    response = await client.post(
        _url_reprogramar(turno_id, token),
        json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
    )

    assert response.status_code == 409
    recargado = await db_session.get(Turno, turno_id)
    assert recargado is not None
    assert recargado.reprogramaciones_count == 0
    assert recargado.estado == "pendiente_sena"


async def test_reprogramar_publico_nuevo_horario_11h_409(
    db_session: AsyncSession,
) -> None:
    """Un nuevo inicio a 11 h responde 409 por la ventana mínima."""
    ctx = await _contexto(db_session)
    ahora = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
    service = TurnoService(db_session, now=lambda: ahora)
    turno = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=48),
    )
    await db_session.commit()

    async with _client_con_reloj(db_session, ahora) as client:
        response = await client.post(
            _url_reprogramar(turno.id, turno.manage_token),
            json={"inicio": (ahora + timedelta(hours=11)).isoformat()},
        )

    assert response.status_code == 409
    assert "12" in response.json()["detail"]


async def test_reprogramar_publico_nuevo_horario_exactamente_12h_200(
    db_session: AsyncSession,
) -> None:
    """Un nuevo inicio exactamente a 12 h se acepta."""
    ctx = await _contexto(db_session)
    ahora = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
    service = TurnoService(db_session, now=lambda: ahora)
    turno = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=48),
    )
    await db_session.commit()

    async with _client_con_reloj(db_session, ahora) as client:
        response = await client.post(
            _url_reprogramar(turno.id, turno.manage_token),
            json={"inicio": (ahora + timedelta(hours=12)).isoformat()},
        )

    assert response.status_code == 200
    assert response.json()["sena_migrada"] is True


async def test_reprogramar_publico_turno_terminal_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Reprogramar un turno cancelado responde 409."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=48),
    )
    turno.estado = "cancelado"
    turno_id = turno.id
    token = turno.manage_token
    await db_session.commit()

    response = await client.post(
        _url_reprogramar(turno_id, token),
        json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
    )

    assert response.status_code == 409
    recargado = await db_session.get(Turno, turno_id)
    assert recargado is not None
    assert recargado.estado == "cancelado"


async def test_reprogramar_publico_falla_creacion_hace_rollback(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si crear_turno falla, el router revierte y el turno viejo sigue vigente."""
    from app.api.public import turnos as public_turnos
    from app.domain.turnos.service import TurnoConflicto

    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        ahora + timedelta(hours=48),
    )
    turno.reprogramaciones_count = 1
    await db_session.commit()
    turno_id = turno.id
    token = turno.manage_token
    service = TurnoService(db_session)

    async def _fallar_creacion(*args: object, **kwargs: object) -> Turno:
        raise TurnoConflicto(
            "sillon_id",
            ahora + timedelta(hours=72),
            ahora + timedelta(hours=72, minutes=30),
        )

    monkeypatch.setattr(service, "crear_turno", _fallar_creacion)
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[public_turnos.get_turno_service] = lambda: service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            _url_reprogramar(turno_id, token),
            json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
        )

    assert response.status_code == 409
    recargado = await db_session.get(Turno, turno_id)
    assert recargado is not None
    assert recargado.estado == "pendiente_sena"
    assert recargado.manage_token == token
    assert recargado.reprogramaciones_count == 1


async def test_e2e_reserva_gestion_reprograma_y_libera_slot(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Reservar, gestionar, reprogramar con turno nuevo y re-reservar el slot viejo."""
    ctx = await _contexto(db_session)
    inicio_viejo = datetime(2026, 11, 20, 10, 0, tzinfo=TZ_CLINICA)
    inicio_nuevo = datetime(2026, 11, 20, 11, 0, tzinfo=TZ_CLINICA)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        inicio_viejo,
    )
    turno.reprogramaciones_count = 1
    await db_session.commit()
    token_viejo = turno.manage_token

    consulta = await client.get(f"/api/public/reservas/gestion/{token_viejo}")
    assert consulta.status_code == 200
    assert consulta.json()["id"] == str(turno.id)

    reprogramada = await client.post(
        _url_reprogramar(turno.id, token_viejo),
        json={"inicio": inicio_nuevo.isoformat()},
    )
    assert reprogramada.status_code == 200
    token_nuevo = reprogramada.json()["manage_token"]
    assert token_nuevo is not None

    viejo = await client.get(f"/api/public/reservas/gestion/{token_viejo}")
    assert viejo.status_code == 200
    assert viejo.json()["estado"] == "cancelado"

    slots = await client.get(
        f"/api/public/slots?fecha=2026-11-20&tipo_practica_id={ctx.practica.id}"
    )
    inicios = {
        datetime.fromisoformat(item["inicio"]).replace(tzinfo=None)
        for item in slots.json()
    }
    assert datetime(2026, 11, 20, 10, 0) in inicios
    assert datetime(2026, 11, 20, 11, 0) not in inicios

    re_reserva = await client.post(
        "/api/public/reservas",
        json=_payload(ctx, inicio=inicio_viejo, telefono="+5491155566677"),
    )
    assert re_reserva.status_code == 201
