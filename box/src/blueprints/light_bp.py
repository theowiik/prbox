from flask import Blueprint, jsonify
from webargs import fields
from webargs.flaskparser import use_args

from ..core.impl.console_light import ConsoleLight
from ..core.light import Light
from ..core.light_state import LightState

light_bp = Blueprint("light", __name__)
light: Light = ConsoleLight()

light_dto = {
    "on": fields.Bool(required=True),
    "brightness": fields.Float(required=True, validate=lambda b: 0 <= b <= 1),
    "color": fields.Str(
        required=True,
        validate=lambda c: c.startswith("#")
        and len(c) == 7
        and all(ch in "0123456789ABCDEF" for ch in c[1:]),
    ),
}


def dto_to_light_state(args: dict) -> LightState:
    return LightState(
        brightness=args.get("brightness"),
        color=args.get("color"),
        on=args.get("on"),
    )


@light_bp.route("/light", methods=["POST"])
@use_args(light_dto, location="json")
def configure_light(args: dict):
    state = dto_to_light_state(args)
    light.set_state(state)

    return jsonify({"status": "Light configured"}), 200
