import logging

from flask import Flask, Response, request

from .events import PrOpenedEvent, StarredEvent
from .parsers import GitHubWebhookParser, WebhookParseer

app = Flask(__name__)
parser: WebhookParseer = GitHubWebhookParser()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route("/github", methods=["POST"])
def github() -> Response:
    event = parser.parse(request)

    if event is None:
        logger.info("Don't care 🥱")
    elif isinstance(event, PrOpenedEvent):
        logger.info("PR opened 🎉")
    elif isinstance(event, StarredEvent):
        logger.info("Repository starred 🌟")
    else:
        logger.warning(f"Unhandled event 🤷‍♂️: {event}")

    return Response(status=200)
