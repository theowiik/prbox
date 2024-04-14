from ..speaker import Speaker


class ConsoleSpeaker(Speaker):
    def beep(self):
        print("🔊 Beep!")