def none_or_whitespace(s: str) -> bool:
    return s is None or s.strip() == ""


def titleize(title: str) -> str:
    symbol = "#"
    bar = symbol * len(title)
    return f"{bar}\n{title}\n{bar}"
