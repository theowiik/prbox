import json
from typing import Protocol

from flask.wrappers import Request

from .events import PrEvent


class WebhookParseer(Protocol):
    def parse(self, request: Request) -> PrEvent:
        """
        Parses an incoming webhook request and returns a PrEvent.
        Returns the 'OTHER' event if the request does not match any known event.

        Args:
            request (Request): The incoming webhook request.

        Returns:
            PrEvent: The parsed event.
        """
        ...


class GitHubWebhookParser:
    def parse(self, request: Request) -> PrEvent:
        print("Parsing GitHub event")

        event = request.headers.get("X-GitHub-Event")
        print("GitHub event:", event)
        
        print("Request JSON:", json.dumps(request.json, indent=4))

        # PR created
        if event == "pull_request":
            opened = request.json.get("action") == "opened"

            if opened:
                return "pr_opened"

        # Checks failed
        if event == "check_suite":
            print("check_run")

            return "HANDLE"

        return None
