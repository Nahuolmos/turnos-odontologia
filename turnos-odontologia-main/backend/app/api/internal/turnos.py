"""Router interno de turnos: catálogo, agenda, alta y cancelación con RBAC."""

from datetime import UTC, date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import UnitOfWork
from app.domain.auth.dependencies import require_role
from app.domain.clinica.repository import SillonRepository
from app.domain.clinica.schemas import SillonOut
from app.domain.personas.repository import PacienteRepository, UserRepository
from app.domain.personas.schemas import PacienteOut
from app.domain.turnos.models import ESTADOS_TURNO
from app.domain.turnos.repository import TipoPracticaRepository
from app.domain.turnos.schemas import (
    OdontologoResumenOut,
    ReprogramacionInternaOut,
    ReprogramarPayload,
    TipoPracticaOut,
    TurnoCancelOut,
    TurnoCreate,
    TurnoOut,
)
from app.domain.turnos.service import (
    PacienteBloqueado,
    PacienteNoEncontrado,
    PracticaNoEncontrada,
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

RolLectura = Annotated[
    dict[str, Any],
    Depends(require_role(["recepcion", "odonto", "admin"])),
]
RolEscritura = Annotated[
    dict[str, Any],
    Depends(require_role(["recepcion", "admin"])),
]


async def get_turno_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TurnoService:
    """Construir un TurnoService con la sesión de la request."""
    return TurnoService(session)


ServiceDep = Annotated[TurnoService, Depends(get_turno_service)]


def _clinic_id(current_user: dict[str, Any]) -> UUID:
    """Extraer y validar el clinic_id de los claims del JWT."""
    raw = current_user.get("clinic_id")
    if not raw:
        raise HTTPException(status_code=401, detail="Token sin clinic_id")
    try:
        return UUID(str(raw))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="clinic_id inválido") from exc


def _user_id(current_user: dict[str, Any]) -> UUID:
    """Extraer y validar el sub (user id) de los claims del JWT."""
    raw = current_user.get("sub")
    if not raw:
        raise HTTPException(status_code=401, detail="Token sin sub")
    try:
        return UUID(str(raw))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="sub inválido") from exc


def _ensure_aware(value: datetime) -> datetime:
    """Normalizar datetimes naive a UTC para poder compararlos."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _traducir_error(exc: TurnoError) -> HTTPException:
    """Traducir errores de dominio a respuestas HTTP consistentes."""
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
    if isinstance(exc, (PracticaNoEncontrada, TurnoNoEncontrado, PacienteNoEncontrado)):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/tipos-practica", response_model=list[TipoPracticaOut])
async def listar_tipos_practica(
    current_user: RolLectura,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[TipoPracticaOut]:
    """Listar las prácticas activas de la clínica del JWT."""
    practicas = await TipoPracticaRepository(session).get_activas(_clinic_id(current_user))
    return [TipoPracticaOut.model_validate(practica) for practica in practicas]


@router.get("/pacientes", response_model=list[PacienteOut])
async def listar_pacientes(
    current_user: RolLectura,
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query()] = None,
) -> list[PacienteOut]:
    """Buscar pacientes activos de la clínica del JWT por nombre o teléfono."""
    pacientes = await PacienteRepository(session).list_activos(
        _clinic_id(current_user),
        q=q,
    )
    return [PacienteOut.model_validate(paciente) for paciente in pacientes]


@router.get("/odontologos", response_model=list[OdontologoResumenOut])
async def listar_odontologos(
    current_user: RolLectura,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[OdontologoResumenOut]:
    """Listar odontólogos activos de la clínica del JWT."""
    odontologos = await UserRepository(session).get_odontologos_activos(
        _clinic_id(current_user)
    )
    return [
        OdontologoResumenOut.model_validate(odontologo) for odontologo in odontologos
    ]


@router.get("/sillones", response_model=list[SillonOut])
async def listar_sillones(
    current_user: RolLectura,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[SillonOut]:
    """Listar los sillones activos de la clínica del JWT."""
    sillones = await SillonRepository(session).get_activos(_clinic_id(current_user))
    return [SillonOut.model_validate(sillon) for sillon in sillones]


@router.get("/turnos", response_model=list[TurnoOut])
async def listar_turnos(
    current_user: RolLectura,
    service: ServiceDep,
    fecha: Annotated[date | None, Query()] = None,
    desde: Annotated[datetime | None, Query()] = None,
    hasta: Annotated[datetime | None, Query()] = None,
    sillon_id: Annotated[UUID | None, Query()] = None,
    odontologo_id: Annotated[UUID | None, Query()] = None,
    estado: Annotated[str | None, Query()] = None,
) -> list[TurnoOut]:
    """Listar la agenda clínica con filtros combinables y confinamiento odonto."""
    if estado is not None and estado not in ESTADOS_TURNO:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {estado}")
    if (
        desde is not None
        and hasta is not None
        and _ensure_aware(desde) > _ensure_aware(hasta)
    ):
        raise HTTPException(status_code=422, detail="desde no puede ser mayor que hasta")

    if current_user.get("rol") == "odonto":
        odontologo_id = _user_id(current_user)

    turnos = await service.listar_agenda(
        _clinic_id(current_user),
        fecha=fecha,
        desde=desde,
        hasta=hasta,
        sillon_id=sillon_id,
        odontologo_id=odontologo_id,
        estado=estado,
    )
    return [TurnoOut.model_validate(turno) for turno in turnos]


@router.post(
    "/turnos",
    response_model=TurnoOut,
    status_code=status.HTTP_201_CREATED,
)
async def crear_turno(
    payload: TurnoCreate,
    current_user: RolEscritura,
    service: ServiceDep,
) -> TurnoOut:
    """Crear un turno presencial o telefónico (recepción/admin)."""
    try:
        turno = await service.crear_turno(
            _clinic_id(current_user),
            payload.paciente_id,
            payload.sillon_id,
            payload.odontologo_id,
            payload.tipo_practica_id,
            payload.inicio,
        )
    except TurnoError as exc:
        raise _traducir_error(exc) from exc

    await UnitOfWork(service.session).commit()
    return TurnoOut.model_validate(turno)


@router.post("/turnos/{turno_id}/cancelar", response_model=TurnoCancelOut)
async def cancelar_turno(
    turno_id: UUID,
    current_user: RolLectura,
    service: ServiceDep,
) -> TurnoCancelOut:
    """Cancelar un turno; odonto solo puede cancelar los propios."""
    clinic_id = _clinic_id(current_user)
    if current_user.get("rol") == "odonto":
        turno = await service.turnos.get_by_id_and_clinic(clinic_id, turno_id)
        if turno is None:
            raise HTTPException(status_code=404, detail=str(turno_id))
        if turno.odontologo_id != _user_id(current_user):
            raise HTTPException(
                status_code=403,
                detail="No autorizado para cancelar este turno",
            )

    try:
        resultado = await service.cancelar(clinic_id, turno_id)
    except TurnoError as exc:
        raise _traducir_error(exc) from exc

    await UnitOfWork(service.session).commit()
    return TurnoCancelOut(
        turno=TurnoOut.model_validate(resultado.turno),
        sena_retenida=resultado.sena_retenida,
    )


@router.post(
    "/turnos/{turno_id}/reprogramar",
    response_model=ReprogramacionInternaOut,
)
async def reprogramar_turno(
    turno_id: UUID,
    payload: ReprogramarPayload,
    current_user: RolLectura,
    service: ServiceDep,
) -> ReprogramacionInternaOut:
    """Reprogramar un turno; odonto solo puede mover los propios."""
    clinic_id = _clinic_id(current_user)
    if current_user.get("rol") == "odonto":
        turno = await service.turnos.get_by_id_and_clinic(clinic_id, turno_id)
        if turno is None:
            raise HTTPException(status_code=404, detail=str(turno_id))
        if turno.odontologo_id != _user_id(current_user):
            raise HTTPException(
                status_code=403,
                detail="No autorizado para reprogramar este turno",
            )

    try:
        resultado = await service.reprogramar(
            clinic_id,
            turno_id,
            payload.inicio,
            payload.sillon_id,
            payload.odontologo_id,
        )
    except TurnoError as exc:
        await UnitOfWork(service.session).rollback()
        raise _traducir_error(exc) from exc

    turno_resultante_id = resultado.turno.id
    await UnitOfWork(service.session).commit()
    turno = await service.turnos.get_by_id_and_clinic(clinic_id, turno_resultante_id)
    if turno is None:  # pragma: no cover - inconsistencia imposible tras commit
        raise HTTPException(status_code=404, detail=str(turno_resultante_id))

    manage_token = (
        resultado.turno.manage_token if resultado.turno_anterior is not None else None
    )
    return ReprogramacionInternaOut(
        turno=TurnoOut.model_validate(turno),
        sena_migrada=resultado.sena_migrada,
        requiere_nueva_sena=resultado.requiere_nueva_sena,
        manage_token=manage_token,
    )


__all__ = ["get_turno_service", "router"]
