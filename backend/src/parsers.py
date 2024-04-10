from typing import Protocol

from events import PrEvent
from flask import Request


class Parser(Protocol):
    def parse(self, request: Request) -> None | PrEvent: ...


class GitHubParser:
    def __init__(self):
        pass

    def parse(self, request: Request) -> None | PrEvent:
        print("Parsing GitHub event")
        return None
