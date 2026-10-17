# The whole repo from the top. Everything runs through uv, so there is nothing
# to install first and nothing to configure.
.PHONY: dev demo gif check format

# The port, if a .env moved it; the same file the box itself reads.
-include .env
BOX_PORT ?= 8000
BOX_URL ?= http://localhost:$(BOX_PORT)
VISUAL ?= rainbow

dev:                     # start the box on http://localhost:8000 (emulated panel)
	$(MAKE) -C box dev

demo:                    # play a built-in visual now: make demo VISUAL=beer
	curl -fsS -H "Content-Type: application/json" \
	  -d '{"name":"$(VISUAL)"}' $(BOX_URL)/api/display/visual

gif:                     # make gif GIF=party.gif
	cd connectors/gifcast && uv run gifcast $(GIF)

check:
	$(MAKE) -C box check
	cd connectors/gifcast && uv run pytest

format:
	$(MAKE) -C box format
	cd connectors/gifcast && uv run ruff format . && uv run ruff check --fix .
