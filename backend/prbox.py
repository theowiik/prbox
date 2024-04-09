import json
from flask import Flask, Response, request

app = Flask(__name__)


def titleize(title: str) -> str:
    symbol = "#"
    bar = symbol * len(title)
    return f"{bar}\n{title}\n{bar}"


@app.route("/webhook", methods=["POST"])
def respond():
    print(titleize("RECIEVED WEBHOOK"))

    json_formatted_str = json.dumps(request.json, indent=2)
    print(json_formatted_str)

    return Response(status=200)
