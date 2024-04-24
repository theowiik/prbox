import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEEP_SOUND_PATH = os.path.join(BASE_DIR, "assets", "beep.mp3")

PICOVOICE_ACCESS_KEY = "PICOVOICE_ACCESS_KEY"
TEMP_DIR = os.path.join(BASE_DIR, "temp")
