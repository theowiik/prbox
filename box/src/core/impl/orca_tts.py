import os
from ...constants import PICOVOICE_ACCESS_KEY, TEMP_DIR
from ..tts import TTS
import pvorca


class OrcaTTS(TTS):
    def __init__(self):
        self.orca = pvorca.create(access_key=os.getenv(PICOVOICE_ACCESS_KEY))
        self.output_path = os.path.join(TEMP_DIR, "output.wav")

    def say(self, text: str) -> None:
        self.orca.synthesize_to_file(text, self.output_path)
