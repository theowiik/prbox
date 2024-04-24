import logging
import os

from flask import Flask, Response, request

from .constants import PICOVOICE_ACCESS_KEY, TEMP_DIR
from .core.impl.console_light import ConsoleLight
from .core.impl.orca_tts import OrcaTTS
from .core.impl.six_tts import SixTTS
from .core.impl.system_speaker import SystemSpeaker
from .core.light import Light
from .core.speaker import Speaker
from .core.tts import TTS
from .util import none_or_whitespace

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

light: Light = ConsoleLight()
speaker: Speaker = SystemSpeaker()
tts: TTS = SixTTS()

# Use the PicoVoice TTS service if the access key is set
pv_key = os.getenv(PICOVOICE_ACCESS_KEY)

if not none_or_whitespace(pv_key):
    try:
        tts = OrcaTTS()
    except Exception as e:
        logger.error(f"Failed to create Orca TTS: {e}")

if not os.path.isdir(TEMP_DIR):
    os.makedirs(TEMP_DIR)


@app.route("/light", methods=["POST"])
def configure_light():
    data = request.json
    brightness = data.get("brightness")
    color = data.get("color")
    on = data.get("on")

    light.on() if on else light.off()

    return Response(status=204)


@app.route("/beep", methods=["POST"])
def beep_speaker():
    speaker.beep()

    return Response(status=204)


@app.route("/speak", methods=["POST"])
def speak():
    print("speaking")
    text = request.json.get("text")
    tts.say(text)
    return Response(status=204)
