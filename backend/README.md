## Dev

### Run Backend

`flask --app src/prbox run`

### Open Ports (optional)

To avoid port forwarding, you can use `ngrok` to open a public URL to your local server.

`ngrok http 5000 --verify-webhook github --verify-webhook-secret={SECRET} --domain={DOMAIN}`
