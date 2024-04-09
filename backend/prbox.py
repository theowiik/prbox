from flask import Flask, request, Response

app = Flask(__name__)

@app.route('/', methods=['POST'])
def ping():
    print("Ping!")
    return Response(status=200)


@app.route('/webhook', methods=['POST'])
def respond():
    print(request.json)
    return Response(status=200)
