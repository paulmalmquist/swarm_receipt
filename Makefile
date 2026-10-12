PYTHON ?= python3
.PHONY: setup lint test demo eval verify run
setup:
	$(PYTHON) --version
lint:
	$(PYTHON) -m compileall -q domain.py adapters.py storage.py server.py demo.py cli.py evaluate.py verify.py
	node --check web/app.js
test:
	$(PYTHON) -m unittest discover -s tests -v
demo:
	$(PYTHON) cli.py demo --out data/demo-receipt.md
eval:
	$(PYTHON) evaluate.py
verify:
	$(PYTHON) verify.py
run:
	$(PYTHON) server.py
