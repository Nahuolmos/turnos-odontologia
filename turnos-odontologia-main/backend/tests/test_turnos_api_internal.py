"""Tests de integración de la API interna de turnos (Fase 3)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.clinica.models import Bloqueo, Clinic, Sillon
from app.domain.personas.models import Paciente, User
from app.domain.turnos.models import TipoPractica, Turno
from app.domain.turnos.service import TurnoService
from app.infrastructure.db.base import get_db
from app.main import create_app

INICIO = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """Cliente HTTP ASGI que comparte la sesión de la fixture db_session."""
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@dataclass
class Contexto:
    """Entidades mínimas para ejercitar la API interna."""

    clinic: Clinic
    paciente: Paciente
    sillon: Sillon
    odontologo: User
    admin: User
    recepcion: User
    practica: TipoPractica


async def _clinica(db_session: AsyncSession, nombre: str | None = None) -> Clinic:
    clinic = Clinic(
        nombre=nombre or f"Clínica {uuid4().hex[:8]}",
        timezone="America/Argentina/Buenos_Aires",
    )
    db_session.add(clinic)
    await db_session.flush()
    return clinic


async def _contexto(
    db_session: AsyncSession,
    *,
    clinic: Clinic | None = None,
    duracion_min: int = 30,
    sena_pct: int = 30,
    activa: bool = True,
) -> Contexto:
    clinic = clinic or await _clinica(db_session)
    paciente = Paciente(
        clinic_id=clinic.id,
        nombre="Paciente Test",
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
    admin = User(
        clinic_id=clinic.id,
        email=f"admin-{uuid4().hex[:8]}@clinica.com",
        password_hash="hash",
        rol="admin",
        activo=True,
    )
    recepcion = User(
        clinic_id=clinic.id,
        email=f"recepcion-{uuid4().hex[:8]}@clinica.com",
        password_hash="hash",
        rol="recepcion",
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
    db_session.add_all([paciente, sillon, odontologo, admin, recepcion, practica])
    await db_session.flush()
    await db_session.commit()
    return Contexto(clinic, paciente, sillon, odontologo, admin, recepcion, practica)


async def _agregar_sillon(db_session: AsyncSession, ctx: Contexto, nombre: str) -> Sillon:
    sillon = Sillon(clinic_id=ctx.clinic.id, nombre=nombre, activo=True)
    db_session.add(sillon)
    await db_session.flush()
    return sillon


async def _agregar_odontologo(db_session: AsyncSession, ctx: Contexto) -> User:
    odontologo = User(
        clinic_id=ctx.clinic.id,
        email=f"odonto-{uuid4().hex[:8]}@clinica.com",
        password_hash="hash",
        rol="odonto",
        activo=True,
    )
    db_session.add(odontologo)
    await db_session.flush()
    return odontologo


def _token(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "clinic_id": str(user.clinic_id),
        "rol": user.rol,
        "email": user.email,
        "jti": str(uuid4()),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user)}"}


def _payload(ctx: Contexto, inicio: datetime = INICIO) -> dict[str, str]:
    return {
        "paciente_id": str(ctx.paciente.id),
        "sillon_id": str(ctx.sillon.id),
        "odontologo_id": str(ctx.odontologo.id),
        "tipo_practica_id": str(ctx.practica.id),
        "inicio": inicio.isoformat(),
    }


async def test_internal_sin_token_401(client: AsyncClient) -> None:
    """Sin Authorization la agenda interna responde 401."""
    response = await client.get("/api/internal/turnos")

    assert response.status_code == 401


async def test_odonto_no_puede_crear_turno_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """El rol odonto no puede crear turnos internos."""
    ctx = await _contexto(db_session)

    response = await client.post(
        "/api/internal/turnos",
        json=_payload(ctx),
        headers=_headers(ctx.odontologo),
    )

    assert response.status_code == 403
    total = await db_session.scalar(select(func.count()).select_from(Turno))
    assert total == 0


async def test_recepcion_puede_crear_turno_y_admin_tambien(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Recepción y admin pueden crear turnos internos."""
    ctx = await _contexto(db_session)

    respuesta_recepcion = await client.post(
        "/api/internal/turnos",
        json=_payload(ctx),
        headers=_headers(ctx.recepcion),
    )
    assert respuesta_recepcion.status_code == 201

    respuesta_admin = await client.post(
        "/api/internal/turnos",
        json=_payload(ctx, INICIO + timedelta(hours=1)),
        headers=_headers(ctx.admin),
    )
    assert respuesta_admin.status_code == 201


async def test_admin_puede_listar_turnos(client: AsyncClient, db_session: AsyncSession) -> None:
    """Admin puede consultar la agenda interna."""
    ctx = await _contexto(db_session)

    response = await client.get("/api/internal/turnos", headers=_headers(ctx.admin))

    assert response.status_code == 200
    assert response.json() == []


async def test_listar_tipos_practica_solo_activos_y_de_la_clinica(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Solo se listan prácticas activas y de la clínica del JWT."""
    ctx = await _contexto(db_session)
    otra = await _clinica(db_session, "Otra clínica")
    await db_session.flush()
    ctx.practica.activa = False
    practica_inactiva_flag = TipoPractica(
        clinic_id=ctx.clinic.id,
        nombre="Inactiva is_active",
        duracion_min=30,
        precio_base=Decimal("10000.00"),
        sena_pct=10,
        activa=True,
        is_active=False,
    )
    practica_propia = TipoPractica(
        clinic_id=ctx.clinic.id,
        nombre="Limpieza",
        duracion_min=45,
        precio_base=Decimal("15000.00"),
        sena_pct=20,
        activa=True,
    )
    practica_ajena = TipoPractica(
        clinic_id=otra.id,
        nombre="Limpieza ajena",
        duracion_min=30,
        precio_base=Decimal("9999.00"),
        sena_pct=30,
        activa=True,
    )
    db_session.add_all([practica_inactiva_flag, practica_propia, practica_ajena])
    await db_session.flush()
    await db_session.commit()

    response = await client.get(
        "/api/internal/tipos-practica", headers=_headers(ctx.recepcion)
    )

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [str(practica_propia.id)]
    assert data[0]["duracion_min"] == 45
    assert data[0]["sena_pct"] == 20


async def test_listar_sillones_solo_de_la_clinica(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Los sillones listados pertenecen solo a la clínica del JWT."""
    ctx = await _contexto(db_session)
    otra = await _clinica(db_session, "Otra clínica")
    sillon_ajeno = Sillon(clinic_id=otra.id, nombre="Sillón ajeno", activo=True)
    inactivo = Sillon(clinic_id=ctx.clinic.id, nombre="Sillón apagado", activo=False)
    db_session.add_all([sillon_ajeno, inactivo])
    await db_session.flush()
    await db_session.commit()

    response = await client.get("/api/internal/sillones", headers=_headers(ctx.odontologo))

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [str(ctx.sillon.id)]
    assert all(item["clinic_id"] == str(ctx.clinic.id) for item in data)


async def test_crear_turno_interno_ok_sin_manage_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """El alta interna deriva el fin y no expone manage_token."""
    ctx = await _contexto(db_session, duracion_min=45, sena_pct=30)

    response = await client.post(
        "/api/internal/turnos",
        json=_payload(ctx),
        headers=_headers(ctx.recepcion),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["estado"] == "pendiente_sena"
    assert data["monto_sena"] == 7500.0
    assert "manage_token" not in data
    inicio = datetime.fromisoformat(data["inicio"])
    fin = datetime.fromisoformat(data["fin"])
    assert fin.replace(tzinfo=None) - inicio.replace(tzinfo=None) == timedelta(minutes=45)


async def test_crear_turno_interno_solape_sillon_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Solape de sillón responde 409 con el campo en el detalle."""
    ctx = await _contexto(db_session, duracion_min=30)
    primero = await client.post(
        "/api/internal/turnos",
        json=_payload(ctx),
        headers=_headers(ctx.recepcion),
    )
    assert primero.status_code == 201

    response = await client.post(
        "/api/internal/turnos",
        json=_payload(ctx, INICIO + timedelta(minutes=15)),
        headers=_headers(ctx.recepcion),
    )

    assert response.status_code == 409
    assert "sillon_id" in response.json()["detail"]


async def test_crear_turno_interno_solape_odontologo_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Solape de odontólogo en otro sillón responde 409."""
    ctx = await _contexto(db_session, duracion_min=30)
    sillon_b = await _agregar_sillon(db_session, ctx, "Sillón B")
    await db_session.commit()
    primero = await client.post(
        "/api/internal/turnos",
        json=_payload(ctx),
        headers=_headers(ctx.recepcion),
    )
    assert primero.status_code == 201

    payload = _payload(ctx, INICIO + timedelta(minutes=15))
    payload["sillon_id"] = str(sillon_b.id)
    response = await client.post(
        "/api/internal/turnos",
        json=payload,
        headers=_headers(ctx.recepcion),
    )

    assert response.status_code == 409
    assert "odontologo_id" in response.json()["detail"]


async def test_agenda_interna_filtros_y_orden(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La agenda filtra por fecha, sillón y estado, y ordena por inicio."""
    ctx = await _contexto(db_session, duracion_min=30)
    sillon_b = await _agregar_sillon(db_session, ctx, "Sillón B")
    odonto_b = await _agregar_odontologo(db_session, ctx)
    await db_session.commit()
    service = TurnoService(db_session)
    t1 = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime(2026, 11, 5, 12, 0, tzinfo=UTC),
    )
    t2 = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime(2026, 11, 5, 10, 0, tzinfo=UTC),
    )
    await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        sillon_b.id,
        odonto_b.id,
        ctx.practica.id,
        datetime(2026, 11, 5, 11, 0, tzinfo=UTC),
    )
    await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime(2026, 11, 6, 10, 0, tzinfo=UTC),
    )
    t2.estado = "confirmado"
    await db_session.commit()

    response = await client.get(
        "/api/internal/turnos",
        params={"fecha": "2026-11-05", "sillon_id": str(ctx.sillon.id)},
        headers=_headers(ctx.admin),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(t2.id), str(t1.id)]

    filtrado = await client.get(
        "/api/internal/turnos",
        params={"fecha": "2026-11-05", "estado": "confirmado"},
        headers=_headers(ctx.admin),
    )
    assert filtrado.status_code == 200
    assert [item["id"] for item in filtrado.json()] == [str(t2.id)]


async def test_agenda_interna_estado_invalido_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un estado fuera del catálogo responde 422."""
    ctx = await _contexto(db_session)

    response = await client.get(
        "/api/internal/turnos",
        params={"estado": "inexistente"},
        headers=_headers(ctx.admin),
    )

    assert response.status_code == 422


async def test_agenda_interna_desde_mayor_hasta_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un rango invertido responde 422."""
    ctx = await _contexto(db_session)

    response = await client.get(
        "/api/internal/turnos",
        params={
            "desde": "2026-11-06T10:00:00Z",
            "hasta": "2026-11-05T10:00:00Z",
        },
        headers=_headers(ctx.admin),
    )

    assert response.status_code == 422


async def test_agenda_odonto_solo_su_agenda(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """El odontólogo ve solo su agenda aunque pida otro profesional."""
    ctx = await _contexto(db_session, duracion_min=30)
    sillon_b = await _agregar_sillon(db_session, ctx, "Sillón B")
    odonto_b = await _agregar_odontologo(db_session, ctx)
    await db_session.commit()
    service = TurnoService(db_session)
    propio = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime(2026, 11, 5, 10, 0, tzinfo=UTC),
    )
    ajeno = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        sillon_b.id,
        odonto_b.id,
        ctx.practica.id,
        datetime(2026, 11, 5, 11, 0, tzinfo=UTC),
    )
    await db_session.commit()

    sin_filtro = await client.get(
        "/api/internal/turnos",
        params={"fecha": "2026-11-05"},
        headers=_headers(ctx.odontologo),
    )
    con_otro = await client.get(
        "/api/internal/turnos",
        params={"fecha": "2026-11-05", "odontologo_id": str(odonto_b.id)},
        headers=_headers(ctx.odontologo),
    )

    assert sin_filtro.status_code == 200
    assert [item["id"] for item in sin_filtro.json()] == [str(propio.id)]
    assert [item["id"] for item in con_otro.json()] == [str(propio.id)]
    assert str(ajeno.id) not in {item["id"] for item in con_otro.json()}


async def test_odonto_no_puede_cancelar_turno_ajeno_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """El odontólogo solo puede cancelar sus propios turnos."""
    ctx = await _contexto(db_session, duracion_min=30)
    sillon_b = await _agregar_sillon(db_session, ctx, "Sillón B")
    odonto_b = await _agregar_odontologo(db_session, ctx)
    await db_session.commit()
    service = TurnoService(db_session)
    ajeno = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        sillon_b.id,
        odonto_b.id,
        ctx.practica.id,
        datetime.now(UTC) + timedelta(days=3),
    )
    propio = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        datetime.now(UTC) + timedelta(days=4),
    )
    await db_session.commit()

    response_ajeno = await client.post(
        f"/api/internal/turnos/{ajeno.id}/cancelar",
        headers=_headers(ctx.odontologo),
    )
    response_propio = await client.post(
        f"/api/internal/turnos/{propio.id}/cancelar",
        headers=_headers(ctx.odontologo),
    )

    assert response_ajeno.status_code == 403
    assert response_propio.status_code == 200


async def test_cancelar_turno_interno_a_tiempo_y_tarde(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La cancelación interna distingue a tiempo (<12h retiene)."""
    ctx = await _contexto(db_session, duracion_min=30)
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

    response_a_tiempo = await client.post(
        f"/api/internal/turnos/{a_tiempo.id}/cancelar",
        headers=_headers(ctx.admin),
    )
    response_tardio = await client.post(
        f"/api/internal/turnos/{tardio.id}/cancelar",
        headers=_headers(ctx.admin),
    )

    assert response_a_tiempo.status_code == 200
    assert response_a_tiempo.json()["sena_retenida"] is False
    assert response_a_tiempo.json()["turno"]["estado"] == "cancelado"
    assert response_tardio.status_code == 200
    assert response_tardio.json()["sena_retenida"] is True


async def test_cancelar_turno_interno_inexistente_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Cancelar un turno inexistente responde 404."""
    ctx = await _contexto(db_session)

    response = await client.post(
        f"/api/internal/turnos/{uuid4()}/cancelar",
        headers=_headers(ctx.admin),
    )

    assert response.status_code == 404


async def test_cancelar_turno_interno_repetido_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Cancelar dos veces responde 409."""
    ctx = await _contexto(db_session, duracion_min=30)
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
    turno_id = turno.id

    primera = await client.post(
        f"/api/internal/turnos/{turno_id}/cancelar", headers=_headers(ctx.admin)
    )
    segunda = await client.post(
        f"/api/internal/turnos/{turno_id}/cancelar", headers=_headers(ctx.admin)
    )

    assert primera.status_code == 200
    assert segunda.status_code == 409


async def test_crear_turno_practica_inactiva_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Una práctica inactiva no permite crear turnos internos."""
    ctx = await _contexto(db_session, activa=False)

    response = await client.post(
        "/api/internal/turnos",
        json=_payload(ctx),
        headers=_headers(ctx.recepcion),
    )

    assert response.status_code == 404


async def test_pacientes_internal_sin_token_401(client: AsyncClient) -> None:
    """El catálogo de pacientes exige JWT."""
    response = await client.get("/api/internal/pacientes")

    assert response.status_code == 401


async def test_odontologos_internal_sin_token_401(client: AsyncClient) -> None:
    """El catálogo de odontólogos exige JWT."""
    response = await client.get("/api/internal/odontologos")

    assert response.status_code == 401


async def test_pacientes_clinic_scoped_y_ordenados_por_nombre(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Solo se listan pacientes activos de la clínica del JWT, por nombre."""
    ctx = await _contexto(db_session)
    otra = await _clinica(db_session, "Otra clínica")
    propio = Paciente(
        clinic_id=ctx.clinic.id,
        nombre="Ana Gómez",
        telefono="+5491100000099",
        dni="30111222",
    )
    inactivo = Paciente(
        clinic_id=ctx.clinic.id,
        nombre="Ana Inactiva",
        telefono="+5491100000088",
        dni="30111223",
        is_active=False,
    )
    ajeno = Paciente(
        clinic_id=otra.id,
        nombre="Paciente Ajeno",
        telefono="+5491100000077",
        dni="30111224",
    )
    db_session.add_all([propio, inactivo, ajeno])
    await db_session.flush()
    await db_session.commit()

    response = await client.get(
        "/api/internal/pacientes", headers=_headers(ctx.recepcion)
    )

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [str(propio.id), str(ctx.paciente.id)]
    assert all(item["clinic_id"] == str(ctx.clinic.id) for item in data)
    assert str(inactivo.id) not in {item["id"] for item in data}
    assert str(ajeno.id) not in {item["id"] for item in data}


async def test_pacientes_filtro_q_por_nombre_y_telefono(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """El filtro q busca substring case-insensitive en nombre o teléfono."""
    ctx = await _contexto(db_session)
    por_nombre = Paciente(
        clinic_id=ctx.clinic.id,
        nombre="Ana Gómez",
        telefono="+5491100000099",
        dni="30111222",
    )
    db_session.add(por_nombre)
    await db_session.flush()
    await db_session.commit()

    response_nombre = await client.get(
        "/api/internal/pacientes",
        params={"q": "ana"},
        headers=_headers(ctx.admin),
    )
    response_telefono = await client.get(
        "/api/internal/pacientes",
        params={"q": "0000099"},
        headers=_headers(ctx.admin),
    )

    assert response_nombre.status_code == 200
    assert [item["id"] for item in response_nombre.json()] == [str(por_nombre.id)]
    assert response_telefono.status_code == 200
    assert [item["id"] for item in response_telefono.json()] == [str(por_nombre.id)]


async def test_odontologos_solo_activos_rol_odonto_de_la_clinica(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Solo odontólogos activos de la clínica del JWT, ordenados por email."""
    ctx = await _contexto(db_session)
    otra = await _clinica(db_session, "Otra clínica")
    activo = User(
        clinic_id=ctx.clinic.id,
        email="aaa-odonto@clinica.com",
        password_hash="hash",
        rol="odonto",
        activo=True,
    )
    inactivo = User(
        clinic_id=ctx.clinic.id,
        email="bbb-odonto@clinica.com",
        password_hash="hash",
        rol="odonto",
        activo=False,
    )
    soft_deleted = User(
        clinic_id=ctx.clinic.id,
        email="ccc-odonto@clinica.com",
        password_hash="hash",
        rol="odonto",
        activo=True,
        is_active=False,
    )
    ajeno = User(
        clinic_id=otra.id,
        email="ddd-odonto@clinica.com",
        password_hash="hash",
        rol="odonto",
        activo=True,
    )
    db_session.add_all([activo, inactivo, soft_deleted, ajeno])
    await db_session.flush()
    await db_session.commit()

    response = await client.get(
        "/api/internal/odontologos", headers=_headers(ctx.recepcion)
    )

    assert response.status_code == 200
    data = response.json()
    esperados = sorted([ctx.odontologo.email, activo.email])
    assert [item["email"] for item in data] == esperados
    assert {item["id"] for item in data} == {
        str(ctx.odontologo.id),
        str(activo.id),
    }
    assert all(set(item) == {"id", "email"} for item in data)


async def _agregar_bloqueo(
    db_session: AsyncSession,
    ctx: Contexto,
    *,
    desde: datetime,
    hasta: datetime,
) -> Bloqueo:
    """Crear un bloqueo vigente para el paciente del contexto."""
    bloqueo = Bloqueo(
        clinic_id=ctx.clinic.id,
        paciente_id=ctx.paciente.id,
        desde=desde,
        hasta=hasta,
        motivo="Ausentismo",
    )
    db_session.add(bloqueo)
    await db_session.flush()
    await db_session.commit()
    return bloqueo


async def test_crear_turno_interno_paciente_bloqueado_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """El alta interna rechaza con 403 a un paciente bloqueado."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    hasta = ahora + timedelta(days=30)
    await _agregar_bloqueo(db_session, ctx, desde=ahora - timedelta(days=1), hasta=hasta)

    response = await client.post(
        "/api/internal/turnos",
        json=_payload(ctx),
        headers=_headers(ctx.recepcion),
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert "bloqueado_hasta" in detail
    devuelto = datetime.fromisoformat(detail["bloqueado_hasta"])
    assert devuelto.replace(tzinfo=None) == hasta.replace(tzinfo=None)
    total = await db_session.scalar(select(func.count()).select_from(Turno))
    assert total == 0


async def test_bloqueo_vencido_permite_crear_turno_interno(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un bloqueo terminado no impide el alta interna."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    await _agregar_bloqueo(
        db_session,
        ctx,
        desde=ahora - timedelta(days=30),
        hasta=ahora - timedelta(minutes=1),
    )

    response = await client.post(
        "/api/internal/turnos",
        json=_payload(ctx),
        headers=_headers(ctx.recepcion),
    )

    assert response.status_code == 201


async def test_reprogramar_interno_recepcion_200_sin_manage_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Recepción reprograma un turno vigente sin token y no recibe uno nuevo."""
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

    response = await client.post(
        f"/api/internal/turnos/{turno.id}/reprogramar",
        json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
        headers=_headers(ctx.recepcion),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["turno"]["id"] == str(turno.id)
    assert data["turno"]["reprogramaciones_count"] == 1
    assert data["sena_migrada"] is True
    assert data["requiere_nueva_sena"] is False
    assert data.get("manage_token") is None


async def test_reprogramar_interno_sin_jwt_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """El endpoint interno de reprogramación exige JWT."""
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

    response = await client.post(
        f"/api/internal/turnos/{turno.id}/reprogramar",
        json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
    )

    assert response.status_code == 401


async def test_reprogramar_interno_odonto_turno_ajeno_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un odontólogo no puede reprogramar el turno de otro profesional."""
    ctx = await _contexto(db_session)
    ahora = datetime.now(UTC)
    otro = await _agregar_odontologo(db_session, ctx)
    turno = await TurnoService(db_session).crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        otro.id,
        ctx.practica.id,
        ahora + timedelta(hours=48),
    )
    await db_session.commit()

    response = await client.post(
        f"/api/internal/turnos/{turno.id}/reprogramar",
        json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
        headers=_headers(ctx.odontologo),
    )

    assert response.status_code == 403
    recargado = await db_session.get(Turno, turno.id)
    assert recargado is not None
    assert recargado.reprogramaciones_count == 0


async def test_reprogramar_interno_odonto_turno_propio_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un odontólogo sí puede reprogramar un turno propio."""
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

    response = await client.post(
        f"/api/internal/turnos/{turno.id}/reprogramar",
        json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
        headers=_headers(ctx.odontologo),
    )

    assert response.status_code == 200
    assert response.json()["turno"]["id"] == str(turno.id)


async def test_reprogramar_interno_segunda_vez_devuelve_token_nuevo(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Cuando se crea un turno nuevo, el personal recibe el manage_token."""
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
    token_viejo = turno.manage_token

    response = await client.post(
        f"/api/internal/turnos/{turno.id}/reprogramar",
        json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
        headers=_headers(ctx.admin),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["turno"]["id"] != str(turno.id)
    assert data["turno"]["reprogramaciones_count"] == 2
    assert data["sena_migrada"] is False
    assert data["requiere_nueva_sena"] is True
    assert data["manage_token"] is not None
    assert data["manage_token"] != token_viejo


async def test_reprogramar_interno_turno_cancelado_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Reprogramar un turno terminal responde 409, no 400."""
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
    turno.estado = "ausente"
    await db_session.commit()

    response = await client.post(
        f"/api/internal/turnos/{turno.id}/reprogramar",
        json={"inicio": (ahora + timedelta(hours=72)).isoformat()},
        headers=_headers(ctx.admin),
    )

    assert response.status_code == 409
