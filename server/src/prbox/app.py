import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import DISPLAY_MODE
from .display.dev import DevDisplay
from .routers import display as display_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if DISPLAY_MODE == "matrix":
        from .display.matrix import MatrixDisplay

        app.state.display = MatrixDisplay()
    else:
        app.state.display = DevDisplay()

    logger.info("Display mode: %s", DISPLAY_MODE)
    yield


app = FastAPI(title="prbox", lifespan=lifespan)
app.include_router(display_router.router)
