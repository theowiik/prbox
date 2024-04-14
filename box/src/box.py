from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route('/configure_light', methods=['POST'])
def configure_light():
    data = request.json
    brightness = data.get('brightness')
    color = data.get('color')
    on_off = data.get('on_off')

    return jsonify({'status': 'success', 'brightness': brightness, 'color': color, 'on_off': on_off})

@app.route('/beep_speaker', methods=['POST'])
def beep_speaker():
    # Add your logic here to beep the speaker
    return jsonify({'status': 'success', 'action': 'beep'})

@app.route('/speak', methods=['POST'])
def speak():
    text = request.json.get('text')
    # Add your logic here to handle text to speech conversion
    return jsonify({'status': 'success', 'text': text})

if __name__ == '__main__':
    app.run(debug=True)
