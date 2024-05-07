from flask import Blueprint, jsonify
from webargs import fields
from webargs.flaskparser import use_args

from ..core.impl.console_light import ConsoleLight
from ..core.light import Light

light_bp = Blueprint("light", __name__)
light: Light = ConsoleLight()


@light_bp.route("/light", methods=["POST"])
@use_args({"on": fields.Bool(required=True)}, location="json")
def configure_light(args: dict):
    on = args.get("on")

    light.set_state(on)

    return jsonify({"status": "Light configured"}), 200
