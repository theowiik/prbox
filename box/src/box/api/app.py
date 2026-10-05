import asyncio
import logging
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..config import Settings
from ..logs import LogBuffer, install, uninstall
from ..render.engine import RenderEngine
from ..scheduler import Scheduler
from ..sources.runner import SourceRunner
from ..sources.weather import MockWeather
from .routes import events, logs, panel, sources

logger = logging.getLogger("box")


def _build_display(settings: Settings):
    if settings.mode == "matrix":
        from ..display.matrix import MatrixDisplay

        return MatrixDisplay(
            settings.width,
            settings.height,
            chain_length=settings.matrix.chain_length,
            parallel=settings.matrix.parallel,
            hardware_mapping=settings.matrix.hardware_mapping,
            gpio_slowdown=settings.matrix.gpio_slowdown,
            pwm_bits=settings.matrix.pwm_bits,
            pwm_lsb_nanoseconds=settings.matrix.pwm_lsb_nanoseconds,
            brightness=settings.matrix.brightness,
        )

    from ..display.dev import DevDisplay

    return DevDisplay(settings.width, settings.height, tty_preview=settings.tty_preview)


async def _validation_error(request: Request, exc: RequestValidationError):
    """FastAPI's 422, minus the `input` echo.

    By default every error carries the offending value back. For a rejected
    animation that is up to 11 MB of base64 returned to a connector that
    already has it — over a Pi's network link, for nothing.
    """
    errors = [{k: v for k, v in e.items() if k != "input"} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Also the uvicorn factory (`box.api.app:create_app`).

    A factory rather than a module-level `app`, so importing this module reads
    no environment and builds nothing — tests construct their own with an
    explicit `Settings`, and a typo in someone's `.env` cannot break them.
    """
    settings = settings or Settings.from_env()
    # Here rather than at import: with --reload the server runs in a fresh
    # process that never goes through __main__. A no-op if already configured.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Installed first, so everything the rest of startup logs is in the tail
        # the dashboard shows.
        buffer = LogBuffer()
        buffer.bind(asyncio.get_running_loop())
        handler = install(buffer)

        display = _build_display(settings)
        engine = RenderEngine(
            display,
            settings.width,
            settings.height,
            fps=settings.fps,
            gamma=settings.gamma,
        )
        scheduler = Scheduler(engine)
        sources = [MockWeather(settings.city, dwell=settings.ambient_dwell)]
        runner = SourceRunner(scheduler, sources, interval=settings.source_interval)

        app.state.settings = settings
        app.state.logs = buffer
        app.state.display = display
        app.state.engine = engine
        app.state.scheduler = scheduler
        app.state.sources = sources

        await engine.start()
        await scheduler.start()
        # Poll once up front so the panel is populated at boot, not a minute in.
        await runner.poll_once()
        await runner.start()

        logger.info(
            "box up — %s %dx%d @%dfps on %s:%d (auth %s)",
            settings.mode,
            settings.width,
            settings.height,
            settings.fps,
            settings.host,
            settings.port,
            "on" if settings.token else "OFF",
        )
        try:
            yield
        finally:
            await runner.stop()
            await scheduler.stop()
            await engine.stop()
            display.close()
            uninstall(handler)

    app = FastAPI(
        title="box",
        description=(
            "A generic LED display box. Connectors POST events to /api/events; "
            "the scheduler decides what the panel shows."
        ),
        version=version("box"),
        lifespan=lifespan,
    )
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.include_router(events.router)
    app.include_router(logs.router)
    app.include_router(panel.router)
    app.include_router(sources.router)
    return app
