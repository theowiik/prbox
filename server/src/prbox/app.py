import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings
from .controller import DisplayController
from .render.engine import RenderEngine
from .routers import display as display_router
from .routers import sources as sources_router
from .sources.weather import MockWeather

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
)
logger = logging.getLogger("prbox")


def _build_display(settings: Settings):
    if settings.mode == "matrix":
        from .display.matrix import MatrixDisplay

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

    from .display.dev import DevDisplay

    return DevDisplay(settings.width, settings.height, tty_preview=settings.tty_preview)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        display = _build_display(settings)
        engine = RenderEngine(
            display,
            settings.width,
            settings.height,
            fps=settings.fps,
            gamma=settings.gamma,
        )

        app.state.settings = settings
        app.state.display = display
        app.state.engine = engine
        app.state.controller = DisplayController(engine)
        app.state.weather = MockWeather(settings.city)

        await engine.start()
        logger.info(
            "prbox up — mode=%s %dx%d @%dfps gamma=%.1f",
            settings.mode,
            settings.width,
            settings.height,
            settings.fps,
            settings.gamma,
        )
        try:
            yield
        finally:
            await engine.stop()
            display.close()

    app = FastAPI(
        title="prbox",
        description="A fun little event display box with LED matrix",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.include_router(display_router.router)
    app.include_router(sources_router.router)
    return app


app = create_app()
