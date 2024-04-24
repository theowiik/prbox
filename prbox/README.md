# prbox Integration

## Dev

- Python 3.12
- Port 5000

### Commands

#### Docker 🐳

```bash
docker-compose up
```

#### Manual

| What?                                           | How?                                                                                         |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------- |
| 📦 Install dependencies                          | `pip install -r requirements.txt`                                                            |
| 🚀 Run backend                                   | `flask --app src/prbox run --host=0.0.0.0`                                                   |
| 🧪 Run tests                                     | `pytest`                                                                                     |
| 🔓 (optional) Open ports without port-forwarding | `ngrok http 5000 --verify-webhook github --verify-webhook-secret={SECRET} --domain={DOMAIN}` |
