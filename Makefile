PYTHON ?= python3

.PHONY: all render ae 4k frames check clean

all: render ae

render:
	$(PYTHON) src/render.py --scene all

ae:
	$(PYTHON) src/build_ae.py

4k:
	$(PYTHON) src/render.py --scene all --scale 2 --workers 8

frames:
	$(PYTHON) src/render.py --scene main --limit 30 --scale 0.5 --frames-only

check:
	$(PYTHON) -m py_compile src/*.py
	$(PYTHON) src/build_ae.py

clean:
	rm -rf out
	find . -name '__pycache__' -type d -prune -exec rm -rf '{}' +
