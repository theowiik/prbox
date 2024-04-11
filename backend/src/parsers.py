from typing import Protocol

from events import PrEvent
from flask import Request


class WebhookParseer(Protocol):
    def parse(self, request: Request) -> None | PrEvent:
        ...


class GitHubWebhookParser:
    def parse(self, request: Request) -> None | PrEvent:
        print("Parsing GitHub event")

        event = request.headers.get("X-GitHub-Event")
        print("GitHub event:", event)

        if event == "pull_request":
            success = request.json.get("action") == "opened"
            return PrEvent(success)

        return None
