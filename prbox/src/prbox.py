from flask import Flask, Response, request

from .parsers import GitHubWebhookParser, WebhookParseer
from .events import PrEvent

app = Flask(__name__)
parser: WebhookParseer = GitHubWebhookParser()


@app.route("/github", methods=["POST"])
def github() -> Response:
    event = parser.parse(request)

    if event == PrEvent.OTHER:
        print("dont care 🥱")
    elif event == PrEvent.PR_OPENED:
        print("PR opened 🎉")

    return Response(status=200)
