import logging
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from .blueprints.instructions_bp import instructions_bp
from .blueprints.light_bp import light_bp
from .constants import PICOVOICE_ACCESS_KEY, TEMP_DIR
from .core.impl.console_tts import ConsoleTTS
from .core.impl.orca_tts import OrcaTTS
from .core.impl.system_speaker import SystemSpeaker
from .core.speaker import Speaker
from .core.tts import TTS
from .util import none_or_whitespace

app = FastAPI()

# Register your routes (FastAPI doesn't have blueprints, but you can use routers for modularity)
app.include_router(light_bp.router)
app.include_router(instructions_bp.router)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

speaker: Speaker = SystemSpeaker()
tts: TTS = ConsoleTTS()

# Use the PicoVoice TTS service if the access key is set
pv_key = os.getenv(PICOVOICE_ACCESS_KEY)

if none_or_whitespace(pv_key):
    logger.info("PicoVoice access key not set, using console TTS")
else:
    try:
        tts = OrcaTTS()
    except Exception as e:
        logger.error(f"Failed to create Orca TTS: {e}")

if not os.path.isdir(TEMP_DIR):
    os.makedirs(TEMP_DIR)


def allowed_file(filename: str):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {
        "wav",
        "mp3",
        "aac",
    }


# Pydantic model for speak request
class SpeakRequest(BaseModel):
    text: str


@app.post("/beep")
async def beep_speaker():
    speaker.beep()
    return {"status": "Beeped"}


@app.post("/speak")
async def speak(request: SpeakRequest):
    tts.say(request.text)
    return {"status": "Spoken"}


@app.post("/play")
async def play(audio: UploadFile = File(...)):
    if not allowed_file(audio.filename):
        raise HTTPException(status_code=400, detail="File type not allowed")

    filename = os.path.join(TEMP_DIR, audio.filename)
    with open(filename, "wb") as f:
        f.write(await audio.read())

    speaker.play(filename)
    return {"status": "Audio played successfully"}
