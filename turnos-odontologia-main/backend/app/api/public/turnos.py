"""Router público de turnos: disponibilidad y reservas sin login.

Supuesto v1: existe una única clínica activa. ``get_default_clinic_id`` resuelve
la primera clínica activa ordenada por ``created_at``; si no hay ninguna, la API
responde 503. Cuando el producto pase a multi-clínica, este helper deberá
resolver la clínica por host, slug o configuración explícita.
"""

from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import UnitOfWork
from app.domain.clinica.models import Clinic
from app.domain.turnos.models import Turno
from app.domain.turnos.repository import TipoPracticaRepository
from app.domain.turnos.schemas import (
    CancelacionPublicaOut,
    ReprogramacionPublicaOut,
    ReprogramarPayload,
    ReservaCreadaOut,
    ReservaCreate,
    SlotOut,
    TipoPracticaOut,
    TurnoGestionOut,
    TurnoPublicoOut,
)
from app.domain.turnos.service import (
    PacienteBloqueado,
    TurnoConflicto,
    TurnoError,
    TurnoNoEncontrado,
    TurnoNoReprogramable,
    TurnoService,
    TurnoVentanaInsuficiente,
    TurnoYaCancelado,
)
from app.infrastructure.db.base import get_db

router = APIRouter(tags=["turnos"])


async def get_turno_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TurnoService:
    """Construir un TurnoService con la sesión de la request."""
    return TurnoService(session)


ServiceDep = Annotated[TurnoService, Depends(get_turno_service)]


async def get_default_clinic_id(session: AsyncSession) -> UUID:
    """Resolver la clínica activa de v1 (primera por created_at)."""
    result = await session.execute(
        select(Clinic)
        .where(Clinic.is_active.is_(True))
        .order_by(Clinic.created_at.asc(), Clinic.id.asc())
        .limit(1)
    )
    clinic = result.scalar_one_or_none()
    if clinic is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No hay una clínica activa configurada",
        )
    return clinic.id


def _traducir_error(exc: TurnoError) -> HTTPException:
    """Traducir errores de dominio a respuestas HTTP públicas."""
    if isinstance(exc, PacienteBloqueado):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": str(exc),
                "bloqueado_hasta": exc.bloqueado_hasta.isoformat(),
            },
        )
    if isinstance(exc, TurnoConflicto):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, TurnoYaCancelado):
        return HTTPException(status_code=409, detail=f"Turno ya cancelado: {exc}")
    if isinstance(exc, (TurnoNoReprogramable, TurnoVentanaInsuficiente)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=404, detail=str(exc))


def _turno_gestion_out(
    service: TurnoService,
    turno: Turno,
    now: datetime,
) -> TurnoGestionOut:
    """Construir la vista pública de gestión con los flags derivados en servidor."""
    indicadores = service.indicadores_gestion(turno, now)
    return TurnoGestionOut(
        **TurnoPublicoOut.model_validate(turno).model_dump(),
        puede_reprogramar=indicadores.puede_reprogramar,
        puede_reprogramar_sin_sena=indicadores.puede_reprogramar_sin_sena,
        cancelacion_retiene_sena=indicadores.cancelacion_retiene_sena,
    )


def _resolver_practica_id(
    tipo_practica_id: UUID | None,
    practica: UUID | None,
) -> UUID:
    """Resolver el id de práctica aceptando ``practica`` como alias."""
    if (
        tipo_practica_id is not None
        and practica is not None
        and tipo_practica_id != practica
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'practica' y 'tipo_practica_id' no coinciden",
        )
    efectivo = tipo_practica_id if tipo_practica_id is not None else practica
    if efectivo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Se requiere 'practica' o 'tipo_practica_id'",
        )
    return efectivo


@router.get("/tipos-practica", response_model=list[TipoPracticaOut])
async def listar_tipos_practica(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[TipoPracticaOut]:
    """Listar las prácticas activas de la clínica activa de v1."""
    clinic_id = await get_default_clinic_id(session)
    practicas = await TipoPracticaRepository(session).get_activas(clinic_id)
    return [TipoPracticaOut.model_validate(practica) for practica in practicas]


@router.get("/slots", response_model=list[SlotOut])
async def listar_slots(
    session: Annotated[AsyncSession, Depends(get_db)],
    service: ServiceDep,
    fecha: Annotated[date, Query(...)],
    tipo_practica_id: Annotated[UUID | None, Query()] = None,
    practica: Annotated[UUID | None, Query()] = None,
) -> list[SlotOut]:
    """Devolver únicamente horarios libres para la práctica indicada.

    Acepta ``practica`` como alias de ``tipo_practica_id``. Si no llega
    ninguno, o si llegan ambos con valores distintos, responde 422.
    """
    practica_id = _resolver_practica_id(tipo_practica_id, practica)
    clinic_id = await get_default_clinic_id(session)
    try:
        return await service.disponibilidad(clinic_id, fecha, practica_id)
    except TurnoError as exc:
        raise _traducir_error(exc) from exc


@router.post(
    "/reservas",
    response_model=ReservaCreadaOut,
    status_code=status.HTTP_201_CREATED,
)
async def crear_reserva(
    payload: ReservaCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    service: ServiceDep,
) -> ReservaCreadaOut:
    """Crear paciente (si falta) y turno en una única transacción pública."""
    clinic_id = await get_default_clinic_id(session)
    try:
        turno, manage_token = await service.crear_reserva_publica(
            clinic_id,
            payload.nombre,
            payload.telefono,
            payload.sillon_id,
            payload.odontologo_id,
            payload.tipo_practica_id,
            payload.inicio,
        )
    except TurnoError as exc:
        await UnitOfWork(session).rollback()
        raise _traducir_error(exc) from exc

    turno_id = turno.id
    await UnitOfWork(session).commit()
    creado = await service.turnos.get_by_id_and_clinic(clinic_id, turno_id)
    if creado is None:  # pragma: no cover - inconsistencia imposible tras commit
        raise HTTPException(status_code=404, detail=str(turno_id))
    return ReservaCreadaOut(
        turno=TurnoPublicoOut.model_validate(creado),
        manage_token=manage_token,
    )


@router.get("/reservas/gestion/{token}", response_model=TurnoGestionOut)
async def consultar_reserva_por_token(
    token: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    service: ServiceDep,
) -> TurnoGestionOut:
    """Consultar una reserva usando solo el manage_token como credencial."""
    clinic_id = await get_default_clinic_id(session)
    try:
        turno = await service.get_por_token_solo(clinic_id, token)
    except TurnoNoEncontrado as exc:
        raise _traducir_error(exc) from exc
    return _turno_gestion_out(service, turno, datetime.now(UTC))


@router.get("/reservas/{turno_id}", response_model=TurnoPublicoOut)
async def consultar_reserva(
    turno_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    service: ServiceDep,
    token: Annotated[str, Query()] = "",
) -> TurnoPublicoOut:
    """Consultar una reserva exigiendo el manage_token correcto."""
    clinic_id = await get_default_clinic_id(session)
    try:
        turno = await service.get_por_token(clinic_id, turno_id, token)
    except TurnoNoEncontrado as exc:
        raise _traducir_error(exc) from exc
    return TurnoPublicoOut.model_validate(turno)


@router.post("/reservas/{turno_id}/cancelar", response_model=CancelacionPublicaOut)
async def cancelar_reserva(
    turno_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    service: ServiceDep,
    token: Annotated[str, Query()] = "",
) -> CancelacionPublicaOut:
    """Cancelar una reserva por token y devolver la política de seña."""
    clinic_id = await get_default_clinic_id(session)
    try:
        await service.get_por_token(clinic_id, turno_id, token)
        resultado = await service.cancelar(clinic_id, turno_id)
    except TurnoError as exc:
        raise _traducir_error(exc) from exc

    await UnitOfWork(session).commit()
    turno = await service.get_por_token(clinic_id, turno_id, token)
    return CancelacionPublicaOut(
        turno=_turno_gestion_out(service, turno, datetime.now(UTC)),
        sena_retenida=resultado.sena_retenida,
    )


@router.post(
    "/reservas/{turno_id}/reprogramar",
    response_model=ReprogramacionPublicaOut,
)
async def reprogramar_reserva(
    turno_id: UUID,
    payload: ReprogramarPayload,
    session: Annotated[AsyncSession, Depends(get_db)],
    service: ServiceDep,
    token: Annotated[str, Query()] = "",
) -> ReprogramacionPublicaOut:
    """Reprogramar una reserva por token; el router controla el commit."""
    clinic_id = await get_default_clinic_id(session)
    try:
        await service.get_por_token(clinic_id, turno_id, token)
        resultado = await service.reprogramar(
            clinic_id,
            turno_id,
            payload.inicio,
            payload.sillon_id,
            payload.odontologo_id,
        )
    except TurnoError as exc:
        await UnitOfWork(session).rollback()
        raise _traducir_error(exc) from exc

    turno_resultante_id = resultado.turno.id
    await UnitOfWork(session).commit()
    turno = await service.turnos.get_by_id_and_clinic(clinic_id, turno_resultante_id)
    if turno is None:  # pragma: no cover - inconsistencia imposible tras commit
        raise HTTPException(status_code=404, detail=str(turno_resultante_id))

    manage_token = (
        resultado.turno.manage_token if resultado.turno_anterior is not None else None
    )
    return ReprogramacionPublicaOut(
        turno=_turno_gestion_out(service, turno, datetime.now(UTC)),
        sena_migrada=resultado.sena_migrada,
        requiere_nueva_sena=resultado.requiere_nueva_sena,
        manage_token=manage_token,
    )


__all__ = ["get_default_clinic_id", "get_turno_service", "router"]
