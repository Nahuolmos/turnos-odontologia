"""Tests del motor de reglas TurnoService (duración, solape, seña, cancelación)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.clinica.models import Bloqueo, Clinic, Sillon
from app.domain.personas.models import Paciente, User
from app.domain.turnos.models import TipoPractica, Turno
from app.domain.turnos.repository import TurnoRepository
from app.domain.turnos.service import (
    PacienteBloqueado,
    PacienteNoEncontrado,
    PracticaNoEncontrada,
    TurnoConflicto,
    TurnoNoEncontrado,
    TurnoNoReprogramable,
    TurnoService,
    TurnoVentanaInsuficiente,
    TurnoYaCancelado,
)

NOW = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)
INICIO = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)


@dataclass
class Contexto:
    """Entidades mínimas para operar con TurnoService."""

    clinic: Clinic
    paciente: Paciente
    sillon: Sillon
    odontologo: User
    practica: TipoPractica


async def _contexto(
    db_session: AsyncSession,
    *,
    duracion_min: int = 45,
    precio_base: Decimal = Decimal("25000.00"),
    sena_pct: int = 30,
    activa: bool = True,
) -> Contexto:
    clinic = Clinic(nombre=f"Clínica {uuid4()}", timezone="America/Argentina/Buenos_Aires")
    db_session.add(clinic)
    await db_session.flush()

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
    practica = TipoPractica(
        clinic_id=clinic.id,
        nombre="Práctica Test",
        duracion_min=duracion_min,
        precio_base=precio_base,
        sena_pct=sena_pct,
        activa=activa,
    )
    db_session.add_all([paciente, sillon, odontologo, practica])
    await db_session.flush()
    return Contexto(clinic, paciente, sillon, odontologo, practica)


async def _crear_turno(
    db_session: AsyncSession,
    ctx: Contexto,
    *,
    inicio: datetime = INICIO,
    sillon: Sillon | None = None,
    odontologo: User | None = None,
    now: datetime = NOW,
) -> Turno:
    service = TurnoService(db_session)
    return await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        (sillon or ctx.sillon).id,
        (odontologo or ctx.odontologo).id,
        ctx.practica.id,
        inicio,
        now=now,
    )


@pytest.mark.asyncio
async def test_crear_turno_deriva_fin_desde_duracion(db_session: AsyncSession) -> None:
    """inicio 10:00 + práctica de 45 min => fin 10:45."""
    ctx = await _contexto(db_session, duracion_min=45)

    turno = await _crear_turno(db_session, ctx)

    assert turno.fin == datetime(2026, 11, 5, 10, 45)
    assert turno.inicio == datetime(2026, 11, 5, 10, 0)


@pytest.mark.asyncio
async def test_crear_turno_practica_inactiva_404(db_session: AsyncSession) -> None:
    """Una práctica inactiva no permite crear turno."""
    ctx = await _contexto(db_session, activa=False)

    with pytest.raises(PracticaNoEncontrada):
        await _crear_turno(db_session, ctx)


@pytest.mark.asyncio
async def test_crear_turno_paciente_de_otra_clinica_404(db_session: AsyncSession) -> None:
    """No se puede usar un paciente de otra clínica."""
    ctx = await _contexto(db_session)
    otra = Clinic(nombre="Otra clínica", timezone="America/Argentina/Buenos_Aires")
    db_session.add(otra)
    await db_session.flush()
    ajeno = Paciente(
        clinic_id=otra.id,
        nombre="Ajeno",
        telefono="+5491100000999",
        dni="99999999",
    )
    db_session.add(ajeno)
    await db_session.flush()

    service = TurnoService(db_session)
    with pytest.raises(PacienteNoEncontrado):
        await service.crear_turno(
            ctx.clinic.id,
            ajeno.id,
            ctx.sillon.id,
            ctx.odontologo.id,
            ctx.practica.id,
            INICIO,
            now=NOW,
        )


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


@pytest.mark.asyncio
async def test_solape_sillon_devuelve_conflicto(db_session: AsyncSession) -> None:
    """Un rango que se cruza con otro turno del mismo sillón da conflicto."""
    ctx = await _contexto(db_session, duracion_min=45)
    await _crear_turno(db_session, ctx)
    otro_odonto = await _agregar_odontologo(db_session, ctx)

    with pytest.raises(TurnoConflicto) as exc:
        await _crear_turno(
            db_session,
            ctx,
            inicio=INICIO + timedelta(minutes=30),
            odontologo=otro_odonto,
        )

    assert exc.value.field == "sillon_id"


@pytest.mark.asyncio
async def test_turnos_contiguos_permitidos(db_session: AsyncSession) -> None:
    """fin == inicio del siguiente turno no es solape."""
    ctx = await _contexto(db_session, duracion_min=45)
    await _crear_turno(db_session, ctx)

    turno = await _crear_turno(db_session, ctx, inicio=INICIO + timedelta(minutes=45))

    assert turno.inicio == datetime(2026, 11, 5, 10, 45)


@pytest.mark.asyncio
async def test_turno_cancelado_no_bloquea(db_session: AsyncSession) -> None:
    """Un turno cancelado no participa del anti-solape."""
    ctx = await _contexto(db_session, duracion_min=45)
    turno = await _crear_turno(db_session, ctx)
    turno.estado = "cancelado"
    await db_session.flush()

    nuevo = await _crear_turno(db_session, ctx)

    assert nuevo.id != turno.id


@pytest.mark.asyncio
async def test_solape_odontologo_mismo_horario_otro_sillon(db_session: AsyncSession) -> None:
    """El mismo odontólogo no puede atender dos sillones en el mismo rango."""
    ctx = await _contexto(db_session, duracion_min=30)
    await _crear_turno(db_session, ctx)
    sillon_b = await _agregar_sillon(db_session, ctx, "Sillón B")

    with pytest.raises(TurnoConflicto) as exc:
        await _crear_turno(
            db_session,
            ctx,
            inicio=INICIO + timedelta(minutes=15),
            sillon=sillon_b,
        )

    assert exc.value.field == "odontologo_id"


@pytest.mark.asyncio
async def test_mismo_horario_otro_odontologo_permitido(db_session: AsyncSession) -> None:
    """Otro odontólogo en un sillón libre puede tomar el mismo horario."""
    ctx = await _contexto(db_session, duracion_min=30)
    sillon_b = await _agregar_sillon(db_session, ctx, "Sillón B")
    await _crear_turno(db_session, ctx, sillon=sillon_b)
    otro_odonto = await _agregar_odontologo(db_session, ctx)

    turno = await _crear_turno(db_session, ctx, odontologo=otro_odonto)

    assert turno.odontologo_id == otro_odonto.id
    assert turno.sillon_id == ctx.sillon.id


@pytest.mark.asyncio
async def test_monto_sena_snapshot(db_session: AsyncSession) -> None:
    """25000 al 30% deja un snapshot de 7500."""
    ctx = await _contexto(db_session, precio_base=Decimal("25000.00"), sena_pct=30)

    turno = await _crear_turno(db_session, ctx)

    assert turno.monto_sena == Decimal("7500.00")


@pytest.mark.asyncio
async def test_monto_sena_no_cambia_al_actualizar_practica(db_session: AsyncSession) -> None:
    """Cambiar el arancel de la práctica no altera turnos ya creados."""
    ctx = await _contexto(db_session, precio_base=Decimal("25000.00"), sena_pct=30)
    turno = await _crear_turno(db_session, ctx)
    turno_id = turno.id

    ctx.practica.precio_base = Decimal("40000.00")
    ctx.practica.sena_pct = 50
    await db_session.flush()
    db_session.expire_all()

    result = await db_session.execute(select(Turno).where(Turno.id == turno_id))
    recargado = result.scalar_one()
    assert recargado.monto_sena == Decimal("7500.00")


@pytest.mark.asyncio
async def test_monto_sena_cero(db_session: AsyncSession) -> None:
    """Una práctica sin seña crea el turno con monto 0."""
    ctx = await _contexto(db_session, sena_pct=0)

    turno = await _crear_turno(db_session, ctx)

    assert turno.monto_sena == Decimal("0.00")


def test_calcular_sena_redondeo_half_up() -> None:
    """El redondeo de centavos usa ROUND_HALF_UP."""
    assert TurnoService._calcular_sena(Decimal("0.05"), 50) == Decimal("0.03")
    assert TurnoService._calcular_sena(Decimal("25000.00"), 30) == Decimal("7500.00")


@pytest.mark.asyncio
async def test_manage_token_es_unico_y_largo(db_session: AsyncSession) -> None:
    """Cada turno recibe un token URL-safe distinto de al menos 40 caracteres."""
    ctx = await _contexto(db_session, duracion_min=30)
    primero = await _crear_turno(db_session, ctx)
    segundo = await _crear_turno(db_session, ctx, inicio=INICIO + timedelta(minutes=30))

    assert primero.manage_token != segundo.manage_token
    assert len(primero.manage_token) >= 40
    assert len(segundo.manage_token) >= 40
    for token in (primero.manage_token, segundo.manage_token):
        assert token.replace("-", "").replace("_", "").isalnum()


def test_generar_manage_token_no_colisiona() -> None:
    """100 tokens generados son todos distintos y no contienen el id."""
    tokens = {TurnoService._generar_manage_token() for _ in range(100)}
    assert len(tokens) == 100


@pytest.mark.asyncio
async def test_get_por_token_valido(db_session: AsyncSession) -> None:
    """El token correcto recupera el turno."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx)

    encontrado = await TurnoService(db_session).get_por_token(
        ctx.clinic.id, turno.id, turno.manage_token
    )

    assert encontrado.id == turno.id


@pytest.mark.asyncio
async def test_get_por_token_invalido_404(db_session: AsyncSession) -> None:
    """Un token que no coincide responde como no encontrado."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx)

    with pytest.raises(TurnoNoEncontrado):
        await TurnoService(db_session).get_por_token(ctx.clinic.id, turno.id, "token-invalido")


@pytest.mark.asyncio
async def test_cancelar_con_mas_de_12h_libera_slot(db_session: AsyncSession) -> None:
    """Cancelar con 13h de anticipación no retiene seña y libera el slot."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx)
    service = TurnoService(db_session)

    resultado = await service.cancelar(
        ctx.clinic.id,
        turno.id,
        now=INICIO - timedelta(hours=13),
    )

    assert resultado.sena_retenida is False
    assert resultado.turno.estado == "cancelado"

    reutilizado = await service.crear_turno(
        ctx.clinic.id,
        ctx.paciente.id,
        ctx.sillon.id,
        ctx.odontologo.id,
        ctx.practica.id,
        INICIO,
        now=INICIO - timedelta(hours=13),
    )
    assert reutilizado.id != turno.id


@pytest.mark.asyncio
async def test_cancelar_con_menos_de_12h_retiene_sena(db_session: AsyncSession) -> None:
    """Cancelar con 11h de anticipación retiene la seña pero libera el slot."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx)

    resultado = await TurnoService(db_session).cancelar(
        ctx.clinic.id,
        turno.id,
        now=INICIO - timedelta(hours=11),
    )

    assert resultado.sena_retenida is True
    assert resultado.turno.estado == "cancelado"


@pytest.mark.asyncio
async def test_cancelar_exactamente_12h_es_a_tiempo(db_session: AsyncSession) -> None:
    """Exactamente 12h de anticipación se considera a tiempo."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx)

    resultado = await TurnoService(db_session).cancelar(
        ctx.clinic.id,
        turno.id,
        now=INICIO - timedelta(hours=12),
    )

    assert resultado.sena_retenida is False


@pytest.mark.asyncio
async def test_cancelar_turno_ya_cancelado_409(db_session: AsyncSession) -> None:
    """Cancelar dos veces levanta TurnoYaCancelado."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx)
    service = TurnoService(db_session)
    await service.cancelar(ctx.clinic.id, turno.id, now=INICIO - timedelta(hours=13))

    with pytest.raises(TurnoYaCancelado):
        await service.cancelar(ctx.clinic.id, turno.id, now=INICIO - timedelta(hours=13))


@pytest.mark.asyncio
async def test_cancelar_turno_inexistente_404(db_session: AsyncSession) -> None:
    """Un turno inexistente levanta TurnoNoEncontrado."""
    ctx = await _contexto(db_session)

    with pytest.raises(TurnoNoEncontrado):
        await TurnoService(db_session).cancelar(ctx.clinic.id, uuid4())


@pytest.mark.asyncio
async def test_agenda_filtra_por_fecha_sillon_y_estado(db_session: AsyncSession) -> None:
    """La agenda combina fecha, sillón y estado, y ordena por inicio."""
    ctx = await _contexto(db_session, duracion_min=30)
    sillon_b = await _agregar_sillon(db_session, ctx, "Sillón B")
    odonto_b = await _agregar_odontologo(db_session, ctx)
    t1 = await _crear_turno(db_session, ctx, inicio=datetime(2026, 11, 5, 10, 0, tzinfo=UTC))
    t2 = await _crear_turno(
        db_session,
        ctx,
        inicio=datetime(2026, 11, 5, 12, 0, tzinfo=UTC),
        sillon=sillon_b,
        odontologo=odonto_b,
    )
    await _crear_turno(db_session, ctx, inicio=datetime(2026, 11, 6, 10, 0, tzinfo=UTC))
    service = TurnoService(db_session)

    del_dia = await service.listar_agenda(ctx.clinic.id, fecha=date(2026, 11, 5))
    assert [t.id for t in del_dia] == [t1.id, t2.id]

    filtrado = await service.listar_agenda(
        ctx.clinic.id,
        fecha=date(2026, 11, 5),
        sillon_id=ctx.sillon.id,
        estado="pendiente_sena",
    )
    assert [t.id for t in filtrado] == [t1.id]


@pytest.mark.asyncio
async def test_agenda_fecha_usa_timezone_clinica(db_session: AsyncSession) -> None:
    """Un turno 23:30 local pertenece al día local, no al siguiente UTC."""
    ctx = await _contexto(db_session, duracion_min=30)
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    turno = await _crear_turno(
        db_session,
        ctx,
        inicio=datetime(2026, 11, 5, 23, 30, tzinfo=tz),
    )
    service = TurnoService(db_session)

    del_5 = await service.listar_agenda(ctx.clinic.id, fecha=date(2026, 11, 5))
    del_6 = await service.listar_agenda(ctx.clinic.id, fecha=date(2026, 11, 6))

    assert [t.id for t in del_5] == [turno.id]
    assert del_6 == []


@pytest.mark.asyncio
async def test_agenda_filtra_por_odontologo(db_session: AsyncSession) -> None:
    """El filtro odontologo_id acota la agenda a ese profesional."""
    ctx = await _contexto(db_session, duracion_min=30)
    sillon_b = await _agregar_sillon(db_session, ctx, "Sillón B")
    odonto_b = await _agregar_odontologo(db_session, ctx)
    t1 = await _crear_turno(db_session, ctx, inicio=datetime(2026, 11, 5, 10, 0, tzinfo=UTC))
    await _crear_turno(
        db_session,
        ctx,
        inicio=datetime(2026, 11, 5, 10, 0, tzinfo=UTC),
        sillon=sillon_b,
        odontologo=odonto_b,
    )

    agenda = await TurnoService(db_session).listar_agenda(
        ctx.clinic.id,
        fecha=date(2026, 11, 5),
        odontologo_id=ctx.odontologo.id,
    )

    assert [t.id for t in agenda] == [t1.id]


@pytest.mark.asyncio
async def test_disponibilidad_excluye_ocupados_y_devuelve_par(db_session: AsyncSession) -> None:
    """Los huecos ocupados no se listan y cada slot trae sillón y odontólogo."""
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    ctx = await _contexto(db_session, duracion_min=30)
    ocupado = await _crear_turno(
        db_session,
        ctx,
        inicio=datetime(2026, 11, 5, 10, 0, tzinfo=tz),
    )

    slots = await TurnoService(db_session).disponibilidad(
        ctx.clinic.id,
        date(2026, 11, 5),
        ctx.practica.id,
    )

    inicios = {slot.inicio for slot in slots}
    assert datetime(2026, 11, 5, 10, 0, tzinfo=tz) not in inicios
    assert datetime(2026, 11, 5, 10, 30, tzinfo=tz) in inicios
    assert all(slot.sillon_id == ctx.sillon.id for slot in slots)
    assert all(slot.odontologo_id == ctx.odontologo.id for slot in slots)
    assert ocupado.id is not None


@pytest.mark.asyncio
async def test_disponibilidad_vacia_si_dia_completo(db_session: AsyncSession) -> None:
    """Si el día completo está ocupado, la lista de slots es vacía."""
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    ctx = await _contexto(db_session, duracion_min=600)
    await _crear_turno(
        db_session,
        ctx,
        inicio=datetime(2026, 11, 5, 9, 0, tzinfo=tz),
    )

    slots = await TurnoService(db_session).disponibilidad(
        ctx.clinic.id,
        date(2026, 11, 5),
        ctx.practica.id,
    )

    assert slots == []


@pytest.mark.asyncio
async def test_disponibilidad_sin_sillones_activos(db_session: AsyncSession) -> None:
    """Sin sillones activos no hay disponibilidad."""
    ctx = await _contexto(db_session, duracion_min=30)
    ctx.sillon.activo = False
    await db_session.flush()

    slots = await TurnoService(db_session).disponibilidad(
        ctx.clinic.id,
        date(2026, 11, 5),
        ctx.practica.id,
    )

    assert slots == []


async def _agregar_bloqueo(
    db_session: AsyncSession,
    ctx: Contexto,
    *,
    desde: datetime,
    hasta: datetime,
    clinic: Clinic | None = None,
    is_active: bool = True,
) -> Bloqueo:
    """Crear un bloqueo de paciente para ejercitar la regla RN-AUS-02."""
    bloqueo = Bloqueo(
        clinic_id=(clinic or ctx.clinic).id,
        paciente_id=ctx.paciente.id,
        desde=desde,
        hasta=hasta,
        motivo="Ausentismo",
        is_active=is_active,
    )
    db_session.add(bloqueo)
    await db_session.flush()
    return bloqueo


@pytest.mark.asyncio
async def test_bloqueo_vigente_impide_crear_turno(db_session: AsyncSession) -> None:
    """Un bloqueo con desde <= now < hasta levanta PacienteBloqueado."""
    ctx = await _contexto(db_session)
    hasta = NOW + timedelta(days=30)
    await _agregar_bloqueo(
        db_session,
        ctx,
        desde=NOW - timedelta(days=1),
        hasta=hasta,
    )

    with pytest.raises(PacienteBloqueado) as exc:
        await _crear_turno(db_session, ctx)

    assert exc.value.bloqueado_hasta == hasta


@pytest.mark.asyncio
async def test_bloqueo_vigente_no_persiste_turno(db_session: AsyncSession) -> None:
    """La validación de bloqueo ocurre antes de insertar el turno."""
    ctx = await _contexto(db_session)
    await _agregar_bloqueo(
        db_session,
        ctx,
        desde=NOW - timedelta(days=1),
        hasta=NOW + timedelta(days=30),
    )

    with pytest.raises(PacienteBloqueado):
        await _crear_turno(db_session, ctx)

    total = await db_session.scalar(select(func.count()).select_from(Turno))
    assert total == 0


@pytest.mark.asyncio
async def test_bloqueo_vencido_permite_crear_turno(db_session: AsyncSession) -> None:
    """Un bloqueo terminado no impide reservar."""
    ctx = await _contexto(db_session)
    await _agregar_bloqueo(
        db_session,
        ctx,
        desde=NOW - timedelta(days=30),
        hasta=NOW - timedelta(minutes=1),
    )

    turno = await _crear_turno(db_session, ctx)

    assert turno.estado == "pendiente_sena"


@pytest.mark.asyncio
async def test_bloqueo_de_otra_clinica_no_aplica(db_session: AsyncSession) -> None:
    """Un bloqueo vigente en otra clínica no bloquea la reserva local."""
    ctx = await _contexto(db_session)
    otra = Clinic(nombre="Otra clínica", timezone="America/Argentina/Buenos_Aires")
    db_session.add(otra)
    await db_session.flush()
    await _agregar_bloqueo(
        db_session,
        ctx,
        desde=NOW - timedelta(days=1),
        hasta=NOW + timedelta(days=30),
        clinic=otra,
    )

    turno = await _crear_turno(db_session, ctx)

    assert turno.estado == "pendiente_sena"


@pytest.mark.asyncio
async def test_bloqueo_justo_en_el_limite_hasta_permite(db_session: AsyncSession) -> None:
    """El rango de bloqueo es semiabierto: hasta == now ya no bloquea."""
    ctx = await _contexto(db_session)
    await _agregar_bloqueo(
        db_session,
        ctx,
        desde=NOW - timedelta(days=30),
        hasta=NOW,
    )

    turno = await _crear_turno(db_session, ctx)

    assert turno.estado == "pendiente_sena"


@pytest.mark.asyncio
async def test_bloqueo_inactivo_no_impide_reservar(db_session: AsyncSession) -> None:
    """Un bloqueo dado de baja lógicamente no se considera vigente."""
    ctx = await _contexto(db_session)
    await _agregar_bloqueo(
        db_session,
        ctx,
        desde=NOW - timedelta(days=1),
        hasta=NOW + timedelta(days=30),
        is_active=False,
    )

    turno = await _crear_turno(db_session, ctx)

    assert turno.estado == "pendiente_sena"


@pytest.mark.asyncio
async def test_expirar_pendientes_cancela_vencidos(db_session: AsyncSession) -> None:
    """Un pendiente_sena creado hace 31 min se cancela con TTL 30."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx)
    turno.created_at = NOW - timedelta(minutes=31)
    await db_session.flush()

    expirados = await TurnoService(db_session).expirar_pendientes(now=NOW, ttl_min=30)

    assert [t.id for t in expirados] == [turno.id]
    assert turno.estado == "cancelado"


@pytest.mark.asyncio
async def test_expirar_pendientes_respeta_ttl(db_session: AsyncSession) -> None:
    """Un pendiente_sena de 29 min sigue vigente con TTL 30."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx)
    turno.created_at = NOW - timedelta(minutes=29)
    await db_session.flush()

    expirados = await TurnoService(db_session).expirar_pendientes(now=NOW, ttl_min=30)

    assert expirados == []
    assert turno.estado == "pendiente_sena"


@pytest.mark.asyncio
async def test_expirar_pendientes_no_toca_confirmados(db_session: AsyncSession) -> None:
    """Los turnos confirmados no expiran aunque superen el TTL."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx)
    turno.estado = "confirmado"
    turno.created_at = NOW - timedelta(minutes=120)
    await db_session.flush()

    expirados = await TurnoService(db_session).expirar_pendientes(now=NOW, ttl_min=30)

    assert expirados == []
    assert turno.estado == "confirmado"


@pytest.mark.asyncio
async def test_expirar_pendientes_es_idempotente(db_session: AsyncSession) -> None:
    """Un segundo barrido no vuelve a cancelar los mismos turnos."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx)
    turno.created_at = NOW - timedelta(minutes=31)
    await db_session.flush()
    service = TurnoService(db_session)

    primera = await service.expirar_pendientes(now=NOW, ttl_min=30)
    segunda = await service.expirar_pendientes(now=NOW, ttl_min=30)

    assert len(primera) == 1
    assert segunda == []
    assert turno.estado == "cancelado"


@pytest.mark.asyncio
async def test_expirar_pendientes_usa_settings_por_defecto(db_session: AsyncSession) -> None:
    """Sin ttl_min explícito se usa Settings.mp_ttl_min (30)."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx)
    turno.created_at = NOW - timedelta(minutes=31)
    await db_session.flush()

    expirados = await TurnoService(db_session).expirar_pendientes(now=NOW)

    assert [t.id for t in expirados] == [turno.id]


@pytest.mark.asyncio
async def test_expirar_pendientes_filtra_por_clinica(db_session: AsyncSession) -> None:
    """El barrido con clinic_id solo afecta a esa clínica."""
    ctx = await _contexto(db_session, duracion_min=30)
    propio = await _crear_turno(db_session, ctx)
    propio.created_at = NOW - timedelta(minutes=31)
    await db_session.flush()

    otra = await _contexto(db_session, duracion_min=30)
    ajeno = await _crear_turno(db_session, otra)
    ajeno.created_at = NOW - timedelta(minutes=31)
    await db_session.flush()

    expirados = await TurnoService(db_session).expirar_pendientes(
        clinic_id=ctx.clinic.id,
        now=NOW,
        ttl_min=30,
    )

    assert [t.id for t in expirados] == [propio.id]
    assert ajeno.estado == "pendiente_sena"


@pytest.mark.asyncio
async def test_turno_expirado_libera_slot_en_disponibilidad(db_session: AsyncSession) -> None:
    """Al expirar, el horario vuelve a estar disponible."""
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    ctx = await _contexto(db_session, duracion_min=30)
    inicio_local = datetime(2026, 11, 5, 10, 0, tzinfo=tz)
    turno = await _crear_turno(db_session, ctx, inicio=inicio_local)
    turno.created_at = NOW - timedelta(minutes=31)
    await db_session.flush()
    service = TurnoService(db_session)

    slots_antes = await service.disponibilidad(ctx.clinic.id, date(2026, 11, 5), ctx.practica.id)
    await service.expirar_pendientes(now=NOW, ttl_min=30)
    slots_despues = await service.disponibilidad(
        ctx.clinic.id, date(2026, 11, 5), ctx.practica.id
    )

    assert inicio_local not in {slot.inicio for slot in slots_antes}
    assert inicio_local in {slot.inicio for slot in slots_despues}


@pytest.mark.asyncio
async def test_repositorio_get_by_manage_token_solo(db_session: AsyncSession) -> None:
    """El repositorio resuelve un turno solo con clínica + manage_token."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx)
    repo = TurnoRepository(db_session)

    encontrado = await repo.get_by_manage_token_solo(ctx.clinic.id, turno.manage_token)
    inexistente = await repo.get_by_manage_token_solo(ctx.clinic.id, "token-invalido")

    assert encontrado is not None
    assert encontrado.id == turno.id
    assert inexistente is None


@pytest.mark.asyncio
async def test_repositorio_get_by_manage_token_solo_restringe_clinica(
    db_session: AsyncSession,
) -> None:
    """Un token de otra clínica no se devuelve desde la clínica consultada."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx)
    otra = await _contexto(db_session, duracion_min=30)
    ajeno = await _crear_turno(db_session, otra, inicio=INICIO + timedelta(days=1))
    repo = TurnoRepository(db_session)

    propio = await repo.get_by_manage_token_solo(ctx.clinic.id, turno.manage_token)
    cruzado = await repo.get_by_manage_token_solo(ctx.clinic.id, ajeno.manage_token)

    assert propio is not None
    assert propio.id == turno.id
    assert cruzado is None


@pytest.mark.asyncio
async def test_get_por_token_solo_valido(db_session: AsyncSession) -> None:
    """El servicio recupera el turno solo con su manage_token."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx)

    encontrado = await TurnoService(db_session).get_por_token_solo(
        ctx.clinic.id, turno.manage_token
    )

    assert encontrado.id == turno.id


@pytest.mark.asyncio
async def test_get_por_token_solo_inexistente_404(db_session: AsyncSession) -> None:
    """Un token desconocido levanta TurnoNoEncontrado."""
    ctx = await _contexto(db_session)

    with pytest.raises(TurnoNoEncontrado):
        await TurnoService(db_session).get_por_token_solo(ctx.clinic.id, "token-invalido")


@pytest.mark.asyncio
async def test_indicadores_gestion_primera_reprogramacion_sin_sena(
    db_session: AsyncSession,
) -> None:
    """Vigente, count 0 y 48 h: habilita reprogramar sin seña."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))

    indicadores = TurnoService(db_session).indicadores_gestion(turno, now=NOW)

    assert indicadores.puede_reprogramar is True
    assert indicadores.puede_reprogramar_sin_sena is True
    assert indicadores.cancelacion_retiene_sena is False


@pytest.mark.asyncio
async def test_indicadores_gestion_con_una_reprogramacion_previa(
    db_session: AsyncSession,
) -> None:
    """Vigente con count 1 exige nueva seña aunque falten 48 h."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))
    turno.reprogramaciones_count = 1
    await db_session.flush()

    indicadores = TurnoService(db_session).indicadores_gestion(turno, now=NOW)

    assert indicadores.puede_reprogramar is True
    assert indicadores.puede_reprogramar_sin_sena is False
    assert indicadores.cancelacion_retiene_sena is False


@pytest.mark.asyncio
async def test_indicadores_gestion_dentro_de_12h(db_session: AsyncSession) -> None:
    """Con 6 h de anticipación reprogramar exige seña y cancelar la retiene."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=6))

    indicadores = TurnoService(db_session).indicadores_gestion(turno, now=NOW)

    assert indicadores.puede_reprogramar is True
    assert indicadores.puede_reprogramar_sin_sena is False
    assert indicadores.cancelacion_retiene_sena is True


@pytest.mark.asyncio
async def test_indicadores_gestion_exactamente_12h_es_a_tiempo(
    db_session: AsyncSession,
) -> None:
    """Exactamente 12 h se considera dentro de la ventana."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=12))

    indicadores = TurnoService(db_session).indicadores_gestion(turno, now=NOW)

    assert indicadores.puede_reprogramar_sin_sena is True
    assert indicadores.cancelacion_retiene_sena is False


@pytest.mark.asyncio
async def test_indicadores_gestion_11h59_retiene_sena(db_session: AsyncSession) -> None:
    """Un minuto menos que 12 h cae en la ventana de retención."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(
        db_session,
        ctx,
        inicio=NOW + timedelta(hours=11, minutes=59),
    )

    indicadores = TurnoService(db_session).indicadores_gestion(turno, now=NOW)

    assert indicadores.puede_reprogramar_sin_sena is False
    assert indicadores.cancelacion_retiene_sena is True


@pytest.mark.asyncio
async def test_indicadores_gestion_estado_terminal_todo_false(
    db_session: AsyncSession,
) -> None:
    """Un turno cancelado deshabilita los tres indicadores."""
    ctx = await _contexto(db_session)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=6))
    turno.estado = "cancelado"
    await db_session.flush()

    indicadores = TurnoService(db_session).indicadores_gestion(turno, now=NOW)

    assert indicadores.puede_reprogramar is False
    assert indicadores.puede_reprogramar_sin_sena is False
    assert indicadores.cancelacion_retiene_sena is False


def _naive(value: datetime) -> datetime:
    """Normalizar datetimes para comparar SQLite (naive) y Postgres (aware)."""
    return value.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_reprogramar_primera_vez_conserva_fila_token_y_sena(
    db_session: AsyncSession,
) -> None:
    """Count 0 con 48 h mueve la misma fila y migra la seña."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))
    turno_id = turno.id
    token_original = turno.manage_token
    nuevo_inicio = NOW + timedelta(hours=72)

    resultado = await TurnoService(db_session).reprogramar(
        ctx.clinic.id,
        turno_id,
        nuevo_inicio,
        now=NOW,
    )

    assert resultado.turno.id == turno_id
    assert resultado.turno.manage_token == token_original
    assert resultado.turno.monto_sena == Decimal("7500.00")
    assert resultado.turno.estado == "pendiente_sena"
    assert resultado.turno.reprogramaciones_count == 1
    assert _naive(resultado.turno.inicio) == _naive(nuevo_inicio)
    assert _naive(resultado.turno.fin) == _naive(nuevo_inicio + timedelta(minutes=30))
    assert _naive(resultado.inicio_anterior) == _naive(NOW + timedelta(hours=48))
    assert resultado.turno_anterior is None
    assert resultado.sena_migrada is True
    assert resultado.requiere_nueva_sena is False


@pytest.mark.parametrize("estado", ["cancelado", "completado", "ausente"])
@pytest.mark.asyncio
async def test_reprogramar_estado_terminal_409(
    db_session: AsyncSession, estado: str
) -> None:
    """Un turno fuera de ESTADOS_VIGENTES no se puede reprogramar."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))
    turno.estado = estado
    await db_session.flush()

    with pytest.raises(TurnoNoReprogramable):
        await TurnoService(db_session).reprogramar(
            ctx.clinic.id,
            turno.id,
            NOW + timedelta(hours=72),
            now=NOW,
        )


@pytest.mark.asyncio
async def test_reprogramar_turno_inexistente_404(db_session: AsyncSession) -> None:
    """Un turno inexistente levanta TurnoNoEncontrado."""
    ctx = await _contexto(db_session)

    with pytest.raises(TurnoNoEncontrado):
        await TurnoService(db_session).reprogramar(
            ctx.clinic.id,
            uuid4(),
            NOW + timedelta(hours=72),
            now=NOW,
        )


@pytest.mark.asyncio
async def test_reprogramar_nuevo_horario_11h_409_sin_mutar(
    db_session: AsyncSession,
) -> None:
    """Un nuevo inicio a 11 h viola la ventana y no modifica el turno."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))

    with pytest.raises(TurnoVentanaInsuficiente):
        await TurnoService(db_session).reprogramar(
            ctx.clinic.id,
            turno.id,
            NOW + timedelta(hours=11),
            now=NOW,
        )

    assert turno.reprogramaciones_count == 0
    assert _naive(turno.inicio) == _naive(NOW + timedelta(hours=48))


@pytest.mark.asyncio
async def test_reprogramar_nuevo_horario_exactamente_12h_permite(
    db_session: AsyncSession,
) -> None:
    """Exactamente 12 h de anticipación del nuevo horario se acepta."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))

    resultado = await TurnoService(db_session).reprogramar(
        ctx.clinic.id,
        turno.id,
        NOW + timedelta(hours=12),
        now=NOW,
    )

    assert resultado.turno.reprogramaciones_count == 1


@pytest.mark.asyncio
async def test_reprogramar_practica_inactiva_404(db_session: AsyncSession) -> None:
    """Si la práctica del turno quedó inactiva no se reprograma."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))
    ctx.practica.activa = False
    await db_session.flush()

    with pytest.raises(PracticaNoEncontrada):
        await TurnoService(db_session).reprogramar(
            ctx.clinic.id,
            turno.id,
            NOW + timedelta(hours=72),
            now=NOW,
        )


@pytest.mark.asyncio
async def test_reprogramar_sillon_de_otra_clinica_404(db_session: AsyncSession) -> None:
    """Un sillón ajeno a la clínica no puede usarse para reprogramar."""
    ctx = await _contexto(db_session, duracion_min=30)
    otra = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))

    with pytest.raises(TurnoNoEncontrado):
        await TurnoService(db_session).reprogramar(
            ctx.clinic.id,
            turno.id,
            NOW + timedelta(hours=72),
            sillon_id=otra.sillon.id,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_reprogramar_odontologo_de_otra_clinica_404(
    db_session: AsyncSession,
) -> None:
    """Un odontólogo ajeno a la clínica no puede usarse para reprogramar."""
    ctx = await _contexto(db_session, duracion_min=30)
    otra = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))

    with pytest.raises(TurnoNoEncontrado):
        await TurnoService(db_session).reprogramar(
            ctx.clinic.id,
            turno.id,
            NOW + timedelta(hours=72),
            odontologo_id=otra.odontologo.id,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_reprogramar_al_mismo_horario_y_recurso_no_es_solape(
    db_session: AsyncSession,
) -> None:
    """Mover el turno a su propio horario excluye la fila actual del anti-solape."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))

    resultado = await TurnoService(db_session).reprogramar(
        ctx.clinic.id,
        turno.id,
        NOW + timedelta(hours=48),
        sillon_id=ctx.sillon.id,
        odontologo_id=ctx.odontologo.id,
        now=NOW,
    )

    assert resultado.turno.id == turno.id
    assert resultado.turno.reprogramaciones_count == 1


@pytest.mark.asyncio
async def test_reprogramar_solape_de_sillon_409(db_session: AsyncSession) -> None:
    """El nuevo horario no puede pisar otro turno vigente del sillón."""
    ctx = await _contexto(db_session, duracion_min=30)
    odonto_b = await _agregar_odontologo(db_session, ctx)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))
    await _crear_turno(
        db_session,
        ctx,
        inicio=NOW + timedelta(hours=72),
        odontologo=odonto_b,
    )

    with pytest.raises(TurnoConflicto) as exc:
        await TurnoService(db_session).reprogramar(
            ctx.clinic.id,
            turno.id,
            NOW + timedelta(hours=72),
            now=NOW,
        )

    assert exc.value.field == "sillon_id"


@pytest.mark.asyncio
async def test_reprogramar_solape_de_odontologo_en_otro_sillon_409(
    db_session: AsyncSession,
) -> None:
    """El odontólogo no puede quedar con dos turnos en el mismo rango."""
    ctx = await _contexto(db_session, duracion_min=30)
    sillon_b = await _agregar_sillon(db_session, ctx, "Sillón B")
    sillon_c = await _agregar_sillon(db_session, ctx, "Sillón C")
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))
    await _crear_turno(
        db_session,
        ctx,
        inicio=NOW + timedelta(hours=72),
        sillon=sillon_b,
    )

    with pytest.raises(TurnoConflicto) as exc:
        await TurnoService(db_session).reprogramar(
            ctx.clinic.id,
            turno.id,
            NOW + timedelta(hours=72),
            sillon_id=sillon_c.id,
            now=NOW,
        )

    assert exc.value.field == "odontologo_id"


@pytest.mark.asyncio
async def test_reprogramar_turno_contiguo_se_acepta(db_session: AsyncSession) -> None:
    """Empezar exactamente cuando termina otro turno no es solape."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))
    await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=72))

    resultado = await TurnoService(db_session).reprogramar(
        ctx.clinic.id,
        turno.id,
        NOW + timedelta(hours=72, minutes=30),
        now=NOW,
    )

    assert _naive(resultado.turno.inicio) == _naive(NOW + timedelta(hours=72, minutes=30))


@pytest.mark.asyncio
async def test_reprogramar_segunda_vez_crea_turno_nuevo_con_nueva_sena(
    db_session: AsyncSession,
) -> None:
    """Count 1 cancela el viejo y crea uno nuevo con token y seña recalculada."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))
    turno.reprogramaciones_count = 1
    turno.created_at = NOW - timedelta(days=10)
    await db_session.flush()
    ctx.practica.precio_base = Decimal("40000.00")
    ctx.practica.sena_pct = 50
    await db_session.flush()
    viejo_id = turno.id
    token_viejo = turno.manage_token
    monto_viejo = turno.monto_sena

    resultado = await TurnoService(db_session).reprogramar(
        ctx.clinic.id,
        viejo_id,
        NOW + timedelta(hours=72),
        now=NOW,
    )

    viejo = resultado.turno_anterior
    nuevo = resultado.turno
    assert viejo is not None
    assert viejo.id == viejo_id
    assert viejo.estado == "cancelado"
    assert viejo.manage_token == token_viejo
    assert viejo.monto_sena == monto_viejo
    assert nuevo.id != viejo_id
    assert nuevo.estado == "pendiente_sena"
    assert nuevo.manage_token != token_viejo
    assert nuevo.reprogramaciones_count == 2
    assert nuevo.monto_sena == Decimal("20000.00")
    assert _naive(nuevo.inicio) == _naive(NOW + timedelta(hours=72))
    assert _naive(resultado.inicio_anterior) == _naive(NOW + timedelta(hours=48))
    assert _naive(nuevo.created_at) > _naive(viejo.created_at)
    assert resultado.sena_migrada is False
    assert resultado.requiere_nueva_sena is True


@pytest.mark.asyncio
async def test_reprogramar_tardia_en_primera_oportunidad_hereda_count(
    db_session: AsyncSession,
) -> None:
    """Count 0 con 6 h para el inicio actual exige seña y crea turno nuevo."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=6))
    viejo_id = turno.id
    token_viejo = turno.manage_token

    resultado = await TurnoService(db_session).reprogramar(
        ctx.clinic.id,
        viejo_id,
        NOW + timedelta(hours=72),
        now=NOW,
    )

    assert resultado.turno_anterior is not None
    assert resultado.turno_anterior.estado == "cancelado"
    assert resultado.turno.id != viejo_id
    assert resultado.turno.estado == "pendiente_sena"
    assert resultado.turno.manage_token != token_viejo
    assert resultado.turno.reprogramaciones_count == 1
    assert resultado.sena_migrada is False
    assert resultado.requiere_nueva_sena is True


@pytest.mark.asyncio
async def test_reprogramar_falla_creacion_y_rollback_deja_viejo_intacto(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un fallo al crear el turno nuevo no debe persistir la cancelación previa."""
    ctx = await _contexto(db_session, duracion_min=30)
    turno = await _crear_turno(db_session, ctx, inicio=NOW + timedelta(hours=48))
    turno.reprogramaciones_count = 1
    await db_session.flush()
    viejo_id = turno.id
    token_viejo = turno.manage_token
    await db_session.commit()
    servicio = TurnoService(db_session, now=lambda: NOW)

    async def _fallar_creacion(*args: object, **kwargs: object) -> Turno:
        raise TurnoConflicto(
            "sillon_id",
            NOW + timedelta(hours=72),
            NOW + timedelta(hours=72, minutes=30),
        )

    monkeypatch.setattr(servicio, "crear_turno", _fallar_creacion)

    with pytest.raises(TurnoConflicto):
        await servicio.reprogramar(
            ctx.clinic.id,
            viejo_id,
            NOW + timedelta(hours=72),
            now=NOW,
        )

    await db_session.rollback()

    recuperado = await db_session.get(Turno, viejo_id)
    assert recuperado is not None
    assert recuperado.estado == "pendiente_sena"
    assert recuperado.manage_token == token_viejo
    assert recuperado.reprogramaciones_count == 1
    assert _naive(recuperado.inicio) == _naive(NOW + timedelta(hours=48))
    total = await db_session.scalar(select(func.count()).select_from(Turno))
    assert total == 1
