import pyttsx3

from ..tts import TTS


class SixTTS(TTS):
    def say(self, text: str) -> None:
        self.engine = pyttsx3.init(driverName="sapi5")
        self.engine.say(text)
        self.engine.runAndWait()
