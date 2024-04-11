from flask import Flask, Response, request
from parsers import GitHubWebhookParser, WebhookParseer

app = Flask(__name__)
parser: WebhookParseer = GitHubWebhookParser()


def titleize(title: str) -> str:
    symbol = "#"
    bar = symbol * len(title)
    return f"{bar}\n{title}\n{bar}"


@app.route("/webhook", methods=["POST"])
def webhook() -> Response:
    event = parser.parse(request)

    if event is not None:
        print(titleize("not none!"))
        print(event)
    else:
        print(titleize("none!"))

    return Response(status=200)
