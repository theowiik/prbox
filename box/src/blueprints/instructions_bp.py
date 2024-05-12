from flask import Blueprint, jsonify
from webargs import fields
from webargs.flaskparser import use_args

instructions_bp = Blueprint("instructions", __name__)
instructions_dto = {}


@instructions_bp.route("/instructions", methods=["POST"])
@use_args(instructions_dto, location="json")
def run_instructions(args: dict):
    print("doing some instructions")

    return jsonify({"status": "okidoki"}), 200
