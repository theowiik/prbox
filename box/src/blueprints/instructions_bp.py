from flask import Blueprint, jsonify, request
from pydantic import BaseModel, ValidationError
from typing import List, Optional

instructions_bp = Blueprint("instructions", __name__)


@instructions_bp.route("/instructions", methods=["POST"])
def run_instructions():
    try:
        data = request.get_json()
        instructions_set = InstructionsSet(**data)
        print("Parsed data:", instructions_set.json(indent=2))
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    print("Doing some instructions")

    return jsonify({"status": "okidoki"}), 200


class LightInstruction(BaseModel):
    enabled: bool
    color: str


class SoundInstruction(BaseModel):
    name: str


class Step(BaseModel):
    action: str
    light: Optional[LightInstruction]
    sound: Optional[SoundInstruction]
    blocking: bool
    duration_ms: int


class AudioFile(BaseModel):
    name: str
    data: str


class InstructionsSet(BaseModel):
    audio_files: List[AudioFile]
    instructions: List[Step]
