from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..display.base import DisplayState

router = APIRouter()


def _get_display(request: Request):
    return request.app.state.display


class ShowTextRequest(BaseModel):
    text: str
    color: str = "#00FF00"


class SetBrightnessRequest(BaseModel):
    brightness: float = Field(ge=0.0, le=1.0)


@router.get("/api/display")
def get_state(display=Depends(_get_display)) -> DisplayState:
    return display.get_state()


@router.post("/api/display/text")
def show_text(body: ShowTextRequest, display=Depends(_get_display)):
    display.show_text(body.text, body.color)
    return {"status": "ok"}


@router.post("/api/display/clear")
def clear(display=Depends(_get_display)):
    display.clear()
    return {"status": "ok"}


@router.post("/api/display/brightness")
def set_brightness(body: SetBrightnessRequest, display=Depends(_get_display)):
    display.set_brightness(body.brightness)
    return {"status": "ok"}


_PREVIEW_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>prbox</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #111; color: #ccc;
            font-family: 'Courier New', monospace;
            display: flex; flex-direction: column; align-items: center;
            min-height: 100vh; padding: 2rem;
        }
        h1 { color: #fff; margin-bottom: 1.5rem; font-size: 1.5rem; }
        .matrix {
            background: #0a0a0a; border: 3px solid #333; border-radius: 12px;
            padding: 1.5rem 2rem; min-width: 480px; min-height: 120px;
            display: flex; align-items: center; justify-content: center;
            margin-bottom: 2rem; box-shadow: 0 0 20px rgba(0,0,0,0.5);
            transition: opacity 0.3s;
        }
        .matrix-text {
            font-size: 2.5rem; font-weight: bold; letter-spacing: 2px;
            text-shadow: 0 0 10px currentColor; transition: color 0.3s;
        }
        .controls { display: flex; flex-direction: column; gap: 0.75rem; width: 480px; }
        .row { display: flex; gap: 0.5rem; align-items: center; }
        input[type="text"] {
            flex: 1; padding: 0.5rem 0.75rem; background: #222;
            border: 1px solid #444; color: #fff; font-family: inherit;
            font-size: 0.9rem; border-radius: 4px;
        }
        input[type="color"] {
            width: 40px; height: 34px; border: none;
            background: none; cursor: pointer;
        }
        input[type="range"] { flex: 1; accent-color: #666; }
        button {
            padding: 0.5rem 1rem; background: #333; color: #fff;
            border: 1px solid #555; font-family: inherit; font-size: 0.9rem;
            cursor: pointer; border-radius: 4px; transition: background 0.2s;
        }
        button:hover { background: #444; }
        label { font-size: 0.85rem; min-width: 80px; }
        .status { font-size: 0.75rem; color: #666; margin-top: 1rem; }
    </style>
</head>
<body>
    <h1>prbox</h1>
    <div class="matrix" id="matrix">
        <span class="matrix-text" id="text"></span>
    </div>
    <div class="controls">
        <div class="row">
            <input type="text" id="input" placeholder="Enter text to display..." />
            <input type="color" id="color" value="#00ff00" />
            <button onclick="sendText()">Show</button>
        </div>
        <div class="row">
            <label>Brightness</label>
            <input type="range" id="brightness" min="0" max="100" value="100" />
        </div>
        <div class="row">
            <button onclick="clearDisplay()">Clear</button>
        </div>
    </div>
    <div class="status" id="status">Connecting...</div>
    <script>
        const API = '/api/display';

        async function poll() {
            try {
                const res = await fetch(API);
                const s = await res.json();
                document.getElementById('text').textContent = s.text;
                document.getElementById('text').style.color = s.color;
                const el = document.getElementById('matrix');
                el.style.opacity = Math.max(s.brightness, 0.1);
                document.getElementById('status').textContent =
                    'Brightness: ' + Math.round(s.brightness * 100) + '%';
            } catch {
                document.getElementById('status').textContent = 'Disconnected';
            }
        }

        async function sendText() {
            const text = document.getElementById('input').value;
            const color = document.getElementById('color').value;
            await fetch(API + '/text', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text, color})
            });
            document.getElementById('input').value = '';
        }

        async function clearDisplay() {
            await fetch(API + '/clear', {method: 'POST'});
        }

        document.getElementById('brightness').addEventListener('input', async (e) => {
            await fetch(API + '/brightness', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({brightness: e.target.value / 100})
            });
        });

        document.getElementById('input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendText();
        });

        setInterval(poll, 1000);
        poll();
    </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def preview():
    return _PREVIEW_HTML
