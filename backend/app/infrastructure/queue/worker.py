import asyncio
import signal

from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


async def process_jobs() -> None:
    logger.info("worker_started")
    while True:
        await asyncio.sleep(60)
        logger.debug("worker_heartbeat")


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
