from flask import Flask, Response, request
from .core.impl.console_light import ConsoleLight
from .core.impl.console_speaker import ConsoleSpeaker
from .core.light import Light
from .core.speaker import Speaker

app = Flask(__name__)

light: Light = ConsoleLight()
speaker: Speaker = ConsoleSpeaker()


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
    text = request.json.get("text")
    return Response(status=204)
