- [prbox](#prbox)
  - [Dev](#dev)
    - [Run Backend](#run-backend)
    - [Open Ports (optional)](#open-ports-optional)
  - [TODO](#todo)

# prbox

Pull request box

## Dev

### Run Backend

`flask --app prbox run`

### Open Ports (optional)

To avoid port forwarding, you can use `ngrok` to open a public URL to your local server.

`ngrok http 5000 --verify-webhook github --verify-webhook-secret={SECRET} --domain={DOMAIN}`

## TODO

- [ ] Dockerize front and backend
