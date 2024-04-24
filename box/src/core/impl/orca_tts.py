import logging
import os

import pvorca
from playsound import playsound

from ...constants import PICOVOICE_ACCESS_KEY, TEMP_DIR
from ..tts import TTS

logger = logging.getLogger(__name__)


class OrcaTTS(TTS):
    def __init__(self):
        self.orca = pvorca.create(access_key=os.getenv(PICOVOICE_ACCESS_KEY))
        self.output_path = os.path.join(TEMP_DIR, "tts.wav")

    def say(self, text: str) -> None:
        try:
            self.orca.synthesize_to_file(text, self.output_path)
        except Exception as e:
            logger.error(f"Failed to synthesize text: {e}")
            return

        try:
            playsound(self.output_path)
        except Exception as e:
            logger.error(f"Failed to play synthesized audio: {e}")
            return
