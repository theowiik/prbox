import multiprocessing

from playsound import playsound

from ...constants import BEEP_SOUND_PATH
from ..speaker import Speaker


class SystemSpeaker(Speaker):
    """Plays audio through the system's speakers."""

    def beep(self) -> None:
        self.play(BEEP_SOUND_PATH)

    def play(self, path: str) -> None:
        p = multiprocessing.Process(target=playsound, args=(path,))
        p.start()
