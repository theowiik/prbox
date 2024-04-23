import os
from flask import Flask, Response, request

from .core.impl.orca_tts import OrcaTTS
from .util import none_or_whitespace
from .constants import PICOVOICE_ACCESS_KEY, TEMP_DIR
from .core.tts import TTS
from .core.impl.six_tts import SixTTS
from .core.impl.system_speaker import SystemSpeaker
from .core.impl.console_light import ConsoleLight
from .core.light import Light
from .core.speaker import Speaker

app = Flask(__name__)

light: Light = ConsoleLight()
speaker: Speaker = SystemSpeaker()
tts: TTS = SixTTS()


# Use the PicoVoice TTS service if the access key is set
pv_key = os.getenv(PICOVOICE_ACCESS_KEY)
print(f"this is the key: {pv_key}")
if not none_or_whitespace(pv_key):
    tts = OrcaTTS()

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
