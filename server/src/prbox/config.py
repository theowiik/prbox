import os

DISPLAY_MODE = os.getenv("PRBOX_DISPLAY_MODE", "dev")
DISPLAY_WIDTH = int(os.getenv("PRBOX_DISPLAY_WIDTH", "32"))
DISPLAY_HEIGHT = int(os.getenv("PRBOX_DISPLAY_HEIGHT", "8"))
