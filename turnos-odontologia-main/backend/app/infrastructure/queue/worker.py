"""Worker de tareas periódicas: expiración de turnos pendientes de seña."""

import asyncio
import signal
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging, get_logger
from app.infrastructure.db.base import get_async_session_factory
from app.infrastructure.queue.expirations import ejecutar_ciclo_expiracion

configure_logging()
logger = get_logger(__name__)

WORKER_POLL_SECONDS = 60


async def ejecutar_ciclo(
    session_factory: Callable[[], AsyncSession] | None = None,
) -> int:
    """Ejecutar un ciclo de expiración aislando los errores de base.

    Un error en un ciclo se registra y se devuelve 0 liberados para que el
    bucle del worker continúe con el siguiente ciclo.
    """
    factory = session_factory or get_async_session_factory()
    async with factory() as session:
        try:
            return await ejecutar_ciclo_expiracion(session)
        except Exception:  # noqa: BLE001 - el worker no debe morir por un ciclo
            logger.exception("worker_expiracion_error")
            await session.rollback()
            return 0


async def process_jobs() -> None:
    """Bucle principal: un ciclo de expiración por intervalo de polling."""
    logger.info("worker_started")
    while True:
        liberados = await ejecutar_ciclo()
        if liberados:
            logger.info("turnos_expirados", count=liberados)
        await asyncio.sleep(WORKER_POLL_SECONDS)


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown() -> None:
        logger.info("worker_shutdown")
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown)

    try:
        loop.run_until_complete(process_jobs())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
