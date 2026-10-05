# The whole repo from the top. Everything runs through uv, so there is nothing
# to install first and nothing to configure: the connectors find the box.
.PHONY: dev demo gif reviews check format

dev:                     # start the box on http://localhost:8000
	$(MAKE) -C box dev

demo:                    # send a generative visual: make demo ARGS=life
	cd connectors/boxdemo && uv run boxdemo $(ARGS)

gif:                     # make gif GIF=party.gif
	cd connectors/gifcast && uv run gifcast $(GIF)

reviews:                 # watch En Stor Stark Review; keeps running
	cd connectors/essr && uv run essr $(ARGS)

check:
	$(MAKE) -C box check
	cd connectors/boxdemo && uv run pytest
	cd connectors/gifcast && uv run pytest
	cd connectors/essr && uv run pytest

format:
	$(MAKE) -C box format
	cd connectors/boxdemo && uv run ruff format . && uv run ruff check --fix .
	cd connectors/gifcast && uv run ruff format . && uv run ruff check --fix .
	cd connectors/essr && uv run ruff format . && uv run ruff check --fix .
