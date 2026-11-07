"""Motor de reglas del dominio turnos: duración, seña, anti-solape y cancelación."""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.clinica.models import Sillon
from app.domain.clinica.repository import BloqueoRepository
from app.domain.personas.models import Paciente, User
from app.domain.turnos.models import ESTADOS_VIGENTES, Turno
from app.domain.turnos.repository import TipoPracticaRepository, TurnoRepository
from app.domain.turnos.schemas import SlotOut

TZ_CLINICA = ZoneInfo("America/Argentina/Buenos_Aires")
HORARIO_APERTURA = 9
HORARIO_CIERRE = 19


class TurnoError(Exception):
    """Error base del dominio turnos."""


class TurnoConflicto(TurnoError):  # noqa: N818 - nombre fijado por el contrato del change
    """El rango solicitado se solapa con otro turno vigente."""

    def __init__(self, field: str, inicio: datetime, fin: datetime):
        self.field = field
        self.inicio = inicio
        self.fin = fin
        super().__init__(f"Conflicto de {field} entre {inicio.isoformat()} y {fin.isoformat()}")


class TurnoNoEncontrado(TurnoError):  # noqa: N818 - nombre fijado por el contrato del change
    """El turno o recurso asociado no existe en la clínica."""


class TurnoYaCancelado(TurnoError):  # noqa: N818 - nombre fijado por el contrato del change
    """El turno ya estaba cancelado."""


class TurnoNoReprogramable(TurnoError):  # noqa: N818 - nombre fijado por el contrato
    """El turno está en un estado que no admite reprogramación."""


class TurnoVentanaInsuficiente(TurnoError):  # noqa: N818 - nombre fijado por el contrato
    """El nuevo horario no cumple la ventana mínima de 12 horas."""


class PracticaNoEncontrada(TurnoError):  # noqa: N818 - nombre fijado por el contrato del change
    """La práctica no existe, está inactiva o pertenece a otra clínica."""


class PacienteNoEncontrado(TurnoError):  # noqa: N818 - nombre fijado por el contrato del change
    """El paciente no existe o pertenece a otra clínica."""


class PacienteBloqueado(TurnoError):  # noqa: N818 - nombre fijado por el contrato del change
    """El paciente tiene un bloqueo vigente por ausentismo (RN-AUS-02)."""

    def __init__(self, bloqueado_hasta: datetime):
        aware = (
            bloqueado_hasta
            if bloqueado_hasta.tzinfo is not None
            else bloqueado_hasta.replace(tzinfo=UTC)
        )
        self.bloqueado_hasta = aware
        super().__init__(f"Paciente bloqueado para reservar hasta {aware.isoformat()}")


@dataclass
class ResultadoCancelacion:
    """Resultado de una cancelación con su política de seña."""

    turno: Turno
    sena_retenida: bool


@dataclass(frozen=True)
class IndicadoresGestion:
    """Indicadores de autogestión derivados del estado y el horario del turno."""

    puede_reprogramar: bool
    puede_reprogramar_sin_sena: bool
    cancelacion_retiene_sena: bool


@dataclass
class ResultadoReprogramacion:
    """Resultado de una reprogramación con su política de seña y trazabilidad."""

    turno: Turno
    turno_anterior: Turno | None
    inicio_anterior: datetime
    sena_migrada: bool
    requiere_nueva_sena: bool


class TurnoService:
    """Servicio de dominio para alta, consulta, cancelación y agenda de turnos."""

    def __init__(
        self,
        session: AsyncSession,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.practicas = TipoPracticaRepository(session)
        self.turnos = TurnoRepository(session)
        self.bloqueos = BloqueoRepository(session)
        self._now: Callable[[], datetime] = now or (lambda: datetime.now(UTC))

    @staticmethod
    def _as_aware(value: datetime) -> datetime:
        """Normalizar datetimes naive (SQLite) a UTC aware."""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @classmethod
    def _calcular_fin(cls, inicio: datetime, duracion_min: int) -> datetime:
        """Derivar el fin sumando la duración de la práctica."""
        return cls._as_aware(inicio) + timedelta(minutes=duracion_min)

    @staticmethod
    def _calcular_sena(precio_base: Decimal | int | float, sena_pct: int) -> Decimal:
        """Calcular la seña con Decimal y redondeo half-up a dos decimales."""
        precio = Decimal(str(precio_base))
        porcentaje = Decimal(sena_pct) / Decimal(100)
        return (precio * porcentaje).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _generar_manage_token() -> str:
        """Generar un token portador opaco y URL-safe."""
        return secrets.token_urlsafe(32)

    def _parametro_datetime(self, value: datetime) -> datetime:
        """Adaptar un datetime aware al almacenamiento del dialecto activo.

        SQLite guarda ``DateTime(timezone=True)`` sin offset; PostgreSQL
        conserva el ``timestamptz``. Enviar el valor en el formato que espera
        cada dialecto evita comparaciones inconsistentes.
        """
        aware = self._as_aware(value).astimezone(UTC)
        bind = self.session.get_bind()
        if bind is not None and bind.dialect.name == "sqlite":
            return aware.replace(tzinfo=None)
        return aware

    async def _verificar_bloqueo(
        self,
        clinic_id: UUID,
        paciente_id: UUID,
        referencia: datetime,
    ) -> None:
        """Rechazar la reserva si el paciente tiene un bloqueo vigente."""
        bloqueo = await self.bloqueos.get_vigente(clinic_id, paciente_id, referencia)
        if bloqueo is not None:
            raise PacienteBloqueado(bloqueo.hasta)

    async def get_por_token(self, clinic_id: UUID, turno_id: UUID, token: str) -> Turno:
        """Recuperar un turno exigiendo id y token válidos."""
        turno = await self.turnos.get_by_manage_token(clinic_id, turno_id, token)
        if turno is None:
            raise TurnoNoEncontrado(str(turno_id))
        return turno

    async def get_por_token_solo(self, clinic_id: UUID, token: str) -> Turno:
        """Recuperar un turno usando únicamente el ``manage_token`` como credencial."""
        turno = await self.turnos.get_by_manage_token_solo(clinic_id, token)
        if turno is None:
            raise TurnoNoEncontrado("token de gestión inválido")
        return turno

    def indicadores_gestion(
        self,
        turno: Turno,
        now: datetime | None = None,
    ) -> IndicadoresGestion:
        """Derivar los flags de gestión sin persistirlos (ventana inclusiva de 12 h)."""
        if turno.estado not in ESTADOS_VIGENTES:
            return IndicadoresGestion(
                puede_reprogramar=False,
                puede_reprogramar_sin_sena=False,
                cancelacion_retiene_sena=False,
            )

        referencia = self._as_aware(now if now is not None else self._now())
        anticipacion = self._as_aware(turno.inicio) - referencia
        dentro_de_ventana = anticipacion < timedelta(hours=12)
        return IndicadoresGestion(
            puede_reprogramar=True,
            puede_reprogramar_sin_sena=(
                turno.reprogramaciones_count == 0 and not dentro_de_ventana
            ),
            cancelacion_retiene_sena=dentro_de_ventana,
        )

    async def crear_turno(
        self,
        clinic_id: UUID,
        paciente_id: UUID,
        sillon_id: UUID,
        odontologo_id: UUID,
        tipo_practica_id: UUID,
        inicio: datetime,
        now: datetime | None = None,
    ) -> Turno:
        """Crear un turno pendiente de seña derivando fin, seña y token."""
        practica = await self.practicas.get_by_id_and_clinic(clinic_id, tipo_practica_id)
        if practica is None or not practica.activa:
            raise PracticaNoEncontrada(str(tipo_practica_id))

        paciente = await self.session.get(Paciente, paciente_id)
        if paciente is None or paciente.clinic_id != clinic_id:
            raise PacienteNoEncontrado(str(paciente_id))

        referencia = self._as_aware(now) if now is not None else self._now()
        await self._verificar_bloqueo(clinic_id, paciente_id, referencia)

        sillon = await self.session.get(Sillon, sillon_id)
        if sillon is None or sillon.clinic_id != clinic_id:
            raise TurnoNoEncontrado(f"Sillón {sillon_id} no encontrado")

        odontologo = await self.session.get(User, odontologo_id)
        if odontologo is None or odontologo.clinic_id != clinic_id:
            raise TurnoNoEncontrado(f"Odontólogo {odontologo_id} no encontrado")

        inicio_utc = self._as_aware(inicio).astimezone(UTC)
        fin_utc = self._calcular_fin(inicio_utc, practica.duracion_min)

        if await self.turnos.exists_overlap(
            clinic_id,
            inicio=inicio_utc,
            fin=fin_utc,
            sillon_id=sillon_id,
        ):
            raise TurnoConflicto("sillon_id", inicio_utc, fin_utc)

        if await self.turnos.exists_overlap(
            clinic_id,
            inicio=inicio_utc,
            fin=fin_utc,
            odontologo_id=odontologo_id,
        ):
            raise TurnoConflicto("odontologo_id", inicio_utc, fin_utc)

        turno = await self.turnos.create(
            {
                "clinic_id": clinic_id,
                "paciente_id": paciente_id,
                "sillon_id": sillon_id,
                "odontologo_id": odontologo_id,
                "tipo_practica_id": tipo_practica_id,
                "inicio": inicio_utc,
                "fin": fin_utc,
                "estado": "pendiente_sena",
                "manage_token": self._generar_manage_token(),
                "reprogramaciones_count": 0,
                "monto_sena": self._calcular_sena(practica.precio_base, practica.sena_pct),
            }
        )
        return turno

    async def get_or_create_paciente(
        self,
        clinic_id: UUID,
        nombre: str,
        telefono: str,
    ) -> Paciente:
        """Buscar un paciente por (clínica, teléfono) o crearlo sin commit."""
        result = await self.session.execute(
            select(Paciente)
            .where(
                Paciente.clinic_id == clinic_id,
                Paciente.telefono == telefono,
            )
            .order_by(Paciente.created_at.asc())
            .limit(1)
        )
        paciente = result.scalars().first()
        if paciente is not None:
            return paciente

        paciente = Paciente(
            clinic_id=clinic_id,
            nombre=nombre,
            telefono=telefono,
            dni="",
        )
        self.session.add(paciente)
        await self.session.flush()
        return paciente

    async def crear_reserva_publica(
        self,
        clinic_id: UUID,
        nombre: str,
        telefono: str,
        sillon_id: UUID,
        odontologo_id: UUID,
        tipo_practica_id: UUID,
        inicio: datetime,
    ) -> tuple[Turno, str]:
        """Resolver/reutilizar el paciente y crear el turno con su token."""
        paciente = await self.get_or_create_paciente(clinic_id, nombre, telefono)
        turno = await self.crear_turno(
            clinic_id,
            paciente.id,
            sillon_id,
            odontologo_id,
            tipo_practica_id,
            inicio,
        )
        return turno, turno.manage_token

    async def cancelar(
        self,
        clinic_id: UUID,
        turno_id: UUID,
        now: datetime | None = None,
    ) -> ResultadoCancelacion:
        """Cancelar un turno y calcular si la seña se retiene (ventana de 12h)."""
        turno = await self.turnos.get_by_id_and_clinic(clinic_id, turno_id)
        if turno is None:
            raise TurnoNoEncontrado(str(turno_id))
        if turno.estado == "cancelado":
            raise TurnoYaCancelado(str(turno_id))

        referencia = self._as_aware(now if now is not None else self._now())
        inicio = self._as_aware(turno.inicio)
        sena_retenida = (inicio - referencia) < timedelta(hours=12)

        turno.estado = "cancelado"
        await self.session.flush()
        await self.session.refresh(turno)
        return ResultadoCancelacion(turno=turno, sena_retenida=sena_retenida)

    async def _resolver_recursos_reprogramacion(
        self,
        clinic_id: UUID,
        sillon_id: UUID,
        odontologo_id: UUID,
    ) -> tuple[UUID, UUID]:
        """Validar que sillón y odontólogo existan y pertenezcan a la clínica."""
        sillon = await self.session.get(Sillon, sillon_id)
        if sillon is None or sillon.clinic_id != clinic_id:
            raise TurnoNoEncontrado(f"Sillón {sillon_id} no encontrado")

        odontologo = await self.session.get(User, odontologo_id)
        if odontologo is None or odontologo.clinic_id != clinic_id:
            raise TurnoNoEncontrado(f"Odontólogo {odontologo_id} no encontrado")

        return sillon.id, odontologo.id

    async def _reprogramar_misma_fila(
        self,
        turno: Turno,
        *,
        inicio: datetime,
        fin: datetime,
        sillon_id: UUID,
        odontologo_id: UUID,
        inicio_anterior: datetime,
    ) -> ResultadoReprogramacion:
        """Mover la misma fila conservando estado, seña y manage_token."""
        turno.inicio = inicio
        turno.fin = fin
        turno.sillon_id = sillon_id
        turno.odontologo_id = odontologo_id
        turno.reprogramaciones_count += 1
        await self.session.flush()
        await self.session.refresh(turno)
        return ResultadoReprogramacion(
            turno=turno,
            turno_anterior=None,
            inicio_anterior=inicio_anterior,
            sena_migrada=True,
            requiere_nueva_sena=False,
        )

    async def _reprogramar_con_turno_nuevo(
        self,
        clinic_id: UUID,
        turno: Turno,
        *,
        inicio: datetime,
        sillon_id: UUID,
        odontologo_id: UUID,
        inicio_anterior: datetime,
        referencia: datetime,
    ) -> ResultadoReprogramacion:
        """Cancelar el turno viejo y crear uno nuevo pendiente de seña.

        El ``flush`` intermedio libera el rango del turno viejo dentro de la
        misma transacción. Un fallo posterior requiere ``rollback`` del llamador.
        """
        turno_anterior = turno
        conteo_anterior = turno.reprogramaciones_count
        paciente_id = turno.paciente_id
        tipo_practica_id = turno.tipo_practica_id

        turno_anterior.estado = "cancelado"
        await self.session.flush()

        nuevo = await self.crear_turno(
            clinic_id,
            paciente_id,
            sillon_id,
            odontologo_id,
            tipo_practica_id,
            inicio,
            now=referencia,
        )
        nuevo.reprogramaciones_count = conteo_anterior + 1
        await self.session.flush()
        await self.session.refresh(nuevo)
        return ResultadoReprogramacion(
            turno=nuevo,
            turno_anterior=turno_anterior,
            inicio_anterior=inicio_anterior,
            sena_migrada=False,
            requiere_nueva_sena=True,
        )

    async def reprogramar(
        self,
        clinic_id: UUID,
        turno_id: UUID,
        inicio: datetime,
        sillon_id: UUID | None = None,
        odontologo_id: UUID | None = None,
        now: datetime | None = None,
    ) -> ResultadoReprogramacion:
        """Reprogramar un turno vigente aplicando la política de seña de C-06.

        Sigue el orden de ``design.md`` D5: existencia → estado → ventana del
        nuevo horario → práctica activa → recursos de la clínica → anti-solape →
        escritura. Solo hace ``flush``; el router es el único que commitea y
        debe hacer ``rollback`` ante cualquier :class:`TurnoError`.
        """
        turno = await self.turnos.get_by_id_and_clinic(clinic_id, turno_id)
        if turno is None:
            raise TurnoNoEncontrado(str(turno_id))
        if turno.estado not in ESTADOS_VIGENTES:
            raise TurnoNoReprogramable(
                f"El turno {turno_id} está en estado '{turno.estado}' "
                "y ya no se puede reprogramar"
            )

        referencia = self._as_aware(now if now is not None else self._now())
        inicio_utc = self._as_aware(inicio).astimezone(UTC)
        if inicio_utc - referencia < timedelta(hours=12):
            raise TurnoVentanaInsuficiente(
                "El nuevo horario debe tener al menos 12 horas de anticipación"
            )

        practica = await self.practicas.get_by_id_and_clinic(
            clinic_id,
            turno.tipo_practica_id,
        )
        if practica is None or not practica.activa:
            raise PracticaNoEncontrada(str(turno.tipo_practica_id))

        sillon_efectivo, odontologo_efectivo = await self._resolver_recursos_reprogramacion(
            clinic_id,
            sillon_id if sillon_id is not None else turno.sillon_id,
            odontologo_id if odontologo_id is not None else turno.odontologo_id,
        )

        fin_utc = self._calcular_fin(inicio_utc, practica.duracion_min)
        if await self.turnos.exists_overlap(
            clinic_id,
            inicio=inicio_utc,
            fin=fin_utc,
            sillon_id=sillon_efectivo,
            excluir_turno_id=turno.id,
        ):
            raise TurnoConflicto("sillon_id", inicio_utc, fin_utc)

        if await self.turnos.exists_overlap(
            clinic_id,
            inicio=inicio_utc,
            fin=fin_utc,
            odontologo_id=odontologo_efectivo,
            excluir_turno_id=turno.id,
        ):
            raise TurnoConflicto("odontologo_id", inicio_utc, fin_utc)

        inicio_anterior = self._as_aware(turno.inicio)
        tardia = (inicio_anterior - referencia) < timedelta(hours=12)
        es_segunda = turno.reprogramaciones_count >= 1

        if not tardia and not es_segunda:
            return await self._reprogramar_misma_fila(
                turno,
                inicio=inicio_utc,
                fin=fin_utc,
                sillon_id=sillon_efectivo,
                odontologo_id=odontologo_efectivo,
                inicio_anterior=inicio_anterior,
            )

        return await self._reprogramar_con_turno_nuevo(
            clinic_id,
            turno,
            inicio=inicio_utc,
            sillon_id=sillon_efectivo,
            odontologo_id=odontologo_efectivo,
            inicio_anterior=inicio_anterior,
            referencia=referencia,
        )

    async def expirar_pendientes(
        self,
        clinic_id: UUID | None = None,
        *,
        now: datetime | None = None,
        ttl_min: int | None = None,
    ) -> list[Turno]:
        """Cancelar los turnos ``pendiente_sena`` vencidos (RN-RES-04).

        Devuelve los turnos liberados. El método es idempotente: un segundo
        barrido sobre el mismo conjunto no encuentra pendientes vencidos.
        No hace commit; el llamador decide el límite de transacción.
        """
        referencia = self._as_aware(now) if now is not None else self._now()
        vigencia = settings.mp_ttl_min if ttl_min is None else ttl_min
        cutoff = referencia - timedelta(minutes=vigencia)

        turnos = await self.turnos.list_pendientes_expirados(
            clinic_id,
            self._parametro_datetime(cutoff),
        )
        for turno in turnos:
            turno.estado = "cancelado"
        if turnos:
            await self.session.flush()
        return turnos

    async def listar_agenda(
        self,
        clinic_id: UUID,
        *,
        fecha: date | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        sillon_id: UUID | None = None,
        odontologo_id: UUID | None = None,
        estado: str | None = None,
    ) -> list[Turno]:
        """Listar la agenda aplicando fecha local o rango y filtros opcionales."""
        if fecha is not None:
            inicio_local = datetime.combine(fecha, time.min, tzinfo=TZ_CLINICA)
            desde = inicio_local.astimezone(UTC)
            hasta = (inicio_local + timedelta(days=1)).astimezone(UTC)
        else:
            desde = self._as_aware(desde).astimezone(UTC) if desde is not None else None
            hasta = self._as_aware(hasta).astimezone(UTC) if hasta is not None else None

        return await self.turnos.list_agenda(
            clinic_id,
            desde=desde,
            hasta=hasta,
            sillon_id=sillon_id,
            odontologo_id=odontologo_id,
            estado=estado,
        )

    def _intervalo_ocupado(
        self,
        turnos: list[Turno],
        *,
        inicio: datetime,
        fin: datetime,
        sillon_id: UUID | None = None,
        odontologo_id: UUID | None = None,
    ) -> bool:
        """Indicar si algún turno vigente intersecta el rango para el recurso dado."""
        for turno in turnos:
            if turno.estado not in ESTADOS_VIGENTES:
                continue
            if sillon_id is not None and turno.sillon_id != sillon_id:
                continue
            if odontologo_id is not None and turno.odontologo_id != odontologo_id:
                continue
            turno_inicio = self._as_aware(turno.inicio)
            turno_fin = self._as_aware(turno.fin)
            if turno_inicio < fin and turno_fin > inicio:
                return True
        return False

    async def disponibilidad(
        self,
        clinic_id: UUID,
        fecha: date,
        tipo_practica_id: UUID,
    ) -> list[SlotOut]:
        """Calcular huecos libres de la grilla 09:00–19:00 para una práctica."""
        practica = await self.practicas.get_by_id_and_clinic(clinic_id, tipo_practica_id)
        if practica is None or not practica.activa:
            raise PracticaNoEncontrada(str(tipo_practica_id))

        sillones_result = await self.session.execute(
            select(Sillon)
            .where(
                Sillon.clinic_id == clinic_id,
                Sillon.activo.is_(True),
                Sillon.is_active.is_(True),
            )
            .order_by(Sillon.nombre.asc())
        )
        sillones = list(sillones_result.scalars().all())

        odontologos_result = await self.session.execute(
            select(User)
            .where(
                User.clinic_id == clinic_id,
                User.rol == "odonto",
                User.activo.is_(True),
                User.is_active.is_(True),
            )
            .order_by(User.email.asc())
        )
        odontologos = list(odontologos_result.scalars().all())

        if not sillones or not odontologos:
            return []

        dia = fecha.date() if isinstance(fecha, datetime) else fecha
        apertura_local = datetime.combine(dia, time(HORARIO_APERTURA), tzinfo=TZ_CLINICA)
        cierre_local = datetime.combine(dia, time(HORARIO_CIERRE), tzinfo=TZ_CLINICA)

        turnos = await self.turnos.list_agenda(
            clinic_id,
            desde=apertura_local.astimezone(UTC),
            hasta=cierre_local.astimezone(UTC),
        )
        ocupados = [turno for turno in turnos if turno.estado in ESTADOS_VIGENTES]

        slots: list[SlotOut] = []
        cursor = apertura_local
        duracion = timedelta(minutes=practica.duracion_min)
        while cursor < cierre_local:
            slot_fin = cursor + duracion
            if slot_fin > cierre_local:
                break
            inicio_utc = cursor.astimezone(UTC)
            fin_utc = slot_fin.astimezone(UTC)

            sillon_libre = next(
                (
                    sillon
                    for sillon in sillones
                    if not self._intervalo_ocupado(
                        ocupados,
                        inicio=inicio_utc,
                        fin=fin_utc,
                        sillon_id=sillon.id,
                    )
                ),
                None,
            )
            if sillon_libre is not None:
                odontologo_libre = next(
                    (
                        odontologo
                        for odontologo in odontologos
                        if not self._intervalo_ocupado(
                            ocupados,
                            inicio=inicio_utc,
                            fin=fin_utc,
                            odontologo_id=odontologo.id,
                        )
                    ),
                    None,
                )
                if odontologo_libre is not None:
                    slots.append(
                        SlotOut(
                            inicio=cursor,
                            fin=slot_fin,
                            sillon_id=sillon_libre.id,
                            odontologo_id=odontologo_libre.id,
                        )
                    )
            cursor = slot_fin

        return slots


__all__ = [
    "IndicadoresGestion",
    "PacienteBloqueado",
    "PacienteNoEncontrado",
    "PracticaNoEncontrada",
    "ResultadoCancelacion",
    "ResultadoReprogramacion",
    "TurnoConflicto",
    "TurnoError",
    "TurnoNoEncontrado",
    "TurnoNoReprogramable",
    "TurnoService",
    "TurnoVentanaInsuficiente",
    "TurnoYaCancelado",
]
