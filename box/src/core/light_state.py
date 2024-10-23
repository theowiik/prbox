class LightState:
    def __init__(self, brightness: float, color: str, on: bool):
        if brightness < 0 or brightness > 1:
            raise ValueError("Brightness must be between 0 and 1.")

        if not color.startswith("#") or len(color) != 7:
            raise ValueError("Color must be a valid hex code.")

        if not all(c in "0123456789ABCDEF" for c in color[1:]):
            raise ValueError("Color must be a valid hex code.")

        if not isinstance(on, bool):
            raise ValueError("On must be a boolean.")

        self.brightness = brightness
        self.color = color
        self.on = on
