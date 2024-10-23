from ..tts import TTS


class ConsoleTTS(TTS):
    def say(self, text: str) -> None:
        print(f"🗣️  '{text}'")
