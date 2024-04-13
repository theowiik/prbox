from flask import Flask, Response, request

from .parsers import GitHubWebhookParser, WebhookParseer
from .util import titleize

app = Flask(__name__)
parser: WebhookParseer = GitHubWebhookParser()


@app.route("/github", methods=["POST"])
def github() -> Response:
    event = parser.parse(request)

    if event is not None:
        print(titleize("not none!"))
        print(event)
    else:
        print(titleize("none!"))

    return Response(status=200)
