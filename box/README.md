# box Interface

## Dev

- Python 3.12
- Port 6000

### Environment Variables

```bash
# Optional, if you want to use PicoVoice as TTS
PICOVOICE_ACCESS_KEY=<key>
```

### Commands

#### Docker 🐳

```bash
docker-compose up
```

#### Manual

| What?                  | How?                                                 |
| ---------------------- | ---------------------------------------------------- |
| 📦 Install dependencies | `pip install -r requirements.txt`                    |
| 🚀 Run                  | `flask --app src/box run --host=0.0.0.0 --port=6000` |
| 🧪 Run tests            | `pytest`                                             |
