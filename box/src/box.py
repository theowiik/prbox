import logging
import os

from flask import Flask, jsonify, request
from playsound import playsound
from werkzeug.utils import secure_filename

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


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {
        "wav",
        "mp3",
        "aac",
    }


@app.route("/light", methods=["POST"])
def configure_light():
    data = request.json
    on = data.get("on")

    light.on() if on else light.off()

    return jsonify({"status": "Light configured"}), 200


@app.route("/beep", methods=["POST"])
def beep_speaker():
    speaker.beep()

    return jsonify({"status": "Beeped"}), 200


@app.route("/speak", methods=["POST"])
def speak():
    text = request.json.get("text")
    tts.say(text)

    return jsonify({"status": "Spoken"}), 200


@app.route("/play", methods=["POST"])
def play():
    print("eeeee!!")
    data = request.json
    name = data['name'] if data and 'name' in data else 'default_name'

    if "audio" not in request.files:
        return jsonify({"error": "No audio part"}), 400

    file = request.files['audio']

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(TEMP_DIR, filename)
        file.save(filepath)

        playsound(filepath)
        # os.remove(filepath)

        return jsonify({"status": "Audio played successfully", "name": name}), 200

    return jsonify({"error": "File type not allowed"}), 400