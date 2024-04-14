def none_or_whitespace(s: str) -> bool:
    return s is None or s.strip() == ""


def greet(s: str) -> str:
    return f"Hello, {s}!"
