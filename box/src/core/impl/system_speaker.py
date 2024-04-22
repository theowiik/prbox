from ...constants import BEEP_SOUND_PATH
from ..speaker import Speaker
from playsound import playsound


class SystemSpeaker(Speaker):
    """Plays audio through the system's speakers."""

    def beep(self) -> None:
        # TODO: Dont block the main thread
        playsound(BEEP_SOUND_PATH)
