import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import DISPLAY_HEIGHT, DISPLAY_MODE, DISPLAY_WIDTH
from .display.dev import DevDisplay
from .routers import display as display_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if DISPLAY_MODE == "matrix":
        from .display.matrix import MatrixDisplay

        app.state.display = MatrixDisplay(DISPLAY_WIDTH, DISPLAY_HEIGHT)
    else:
        app.state.display = DevDisplay(DISPLAY_WIDTH, DISPLAY_HEIGHT)

    logger.info("Display mode: %s (%dx%d)", DISPLAY_MODE, DISPLAY_WIDTH, DISPLAY_HEIGHT)
    yield


app = FastAPI(title="prbox", lifespan=lifespan)
app.include_router(display_router.router)
