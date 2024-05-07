import logging
import os

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

from .blueprints.light_controller import light_bp
from .constants import PICOVOICE_ACCESS_KEY, TEMP_DIR
from .core.impl.console_tts import ConsoleTTS
from .core.impl.orca_tts import OrcaTTS
from .core.impl.system_speaker import SystemSpeaker
from .core.speaker import Speaker
from .core.tts import TTS
from .util import none_or_whitespace

app = Flask(__name__)
app.register_blueprint(light_bp)

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


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {
        "wav",
        "mp3",
        "aac",
    }


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
    print("Request received!")

    if "audio" not in request.files:
        return jsonify({"error": "Attach audio to 'audio' field in file form"}), 400

    f = request.files["audio"]

    if f.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if f and allowed_file(f.filename):
        filename = secure_filename(f.filename)
        filepath = os.path.join(TEMP_DIR, filename)
        f.save(filepath)

        speaker.play(filepath)

        return jsonify({"status": "Audio played successfully"}), 200

    return jsonify({"error": "File type not allowed"}), 400
