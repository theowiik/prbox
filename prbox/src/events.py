class PrOpenedEvent:
    """Pull request was opened."""

    def __init__(self, username: str) -> None:
        self.username = username


class PrMergedEvent:
    """Pull request was merged."""

    def __init__(self, username: str) -> None:
        self.username = username


class StarredEvent:
    """Pull request got a star."""

    def __init__(self, username: str) -> None:
        self.username = username
