PY ?= python
SPEC ?= examples/spec-example.json

.PHONY: test check build check-sources package sync sync-check

test:
	$(PY) -m unittest discover -s tests -v

check:
	$(PY) scripts/build_exam_pdf.py --spec $(SPEC) --check-spec

build:
	$(PY) scripts/build_exam_pdf.py --spec $(SPEC) --verify

check-sources:
	$(PY) scripts/check_sources.py --spec $(SPEC) --allow-blocked

package:
	mkdir -p dist
	git archive --format=zip -o dist/exam-paper-maker.skill HEAD

sync:
	$(PY) scripts/sync_skill.py

sync-check:
	$(PY) scripts/sync_skill.py --check
