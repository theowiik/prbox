import json
from typing import Protocol

from flask.wrappers import Request

from .events import PrMergedEvent, PrOpenedEvent, StarredEvent


class WebhookParseer(Protocol):
    def parse(self, request: Request) -> None | PrOpenedEvent | StarredEvent:
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
    def parse(self, request: Request) -> None | PrOpenedEvent | StarredEvent:
        parsers = [
            self._try_parse_pr_opened,
            self._try_parse_pr_merged,
            self._try_parse_starred,
        ]

        for parser in parsers:
            result = parser(request)
            if result is not None:
                return result

        return None

    def _try_parse_pr_opened(self, request: Request) -> None | PrOpenedEvent:
        if (
            self._get_event(request) == "pull_request"
            and request.json.get("action") == "opened"
        ):
            return PrOpenedEvent(self._get_login(request))

        return None

    def _try_parse_pr_merged(self, request: Request) -> None | PrMergedEvent:
        if (
            self._get_event(request) == "pull_request"
            and request.json.get("action") == "closed"
            and request.json["pull_request"]["merged"]
        ):
            return PrMergedEvent(self._get_login(request))

        return None

    def _try_parse_starred(self, request: Request) -> None | StarredEvent:
        if (
            self._get_event(request) == "star"
            and request.json.get("action") == "created"
        ):
            return StarredEvent(self._get_login(request))

        return None

    def _get_login(self, request: Request) -> str:
        return request.json["sender"]["login"]

    def _get_event(self, request: Request) -> str:
        return request.headers.get("X-GitHub-Event")
