def none_or_whitespace(s: str) -> bool:
    return s is None or s.strip() == ""


def greet(s: str) -> str:
    return f"Hello, {s}!"


def hex_to_rgb(hex_code: str) -> tuple:
    """Converts a hex color code to an RGB tuple."""
    hex_code = hex_code.lstrip('#')
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))


def print_color(text: str, hex_code: str) -> None:
    """Prints text in the terminal with the color specified by the given hex code."""
    rgb = hex_to_rgb(hex_code)
    print(f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m{text}\x1b[0m")