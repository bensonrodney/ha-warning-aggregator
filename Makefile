RUFF_VERSION := 0.16.5

.PHONY: help version release test lint hacs manifest zip

help:
	@echo "make version              print the current integration version"
	@echo "make release [BUMP=patch] bump, tag vX.Y.Z, push to every remote (CI publishes)"
	@echo "make release SET=1.4.0    release an explicit version"
	@echo "make test                 run the test suite"
	@echo "make lint                 ruff check + format --check"
	@echo "make hacs                 offline HACS checks"
	@echo "make manifest             hassfest-style manifest checks"
	@echo "make zip                  build warning_aggregator.zip"

version:
	@python3 scripts/bump_version.py --show

BUMP ?= patch
release:
ifdef SET
	@scripts/release.sh --set $(SET)
else
	@scripts/release.sh $(BUMP)
endif

test:
	uv run --python 3.13 --with-requirements requirements_test.txt pytest

lint:
	uvx ruff@$(RUFF_VERSION) check .
	uvx ruff@$(RUFF_VERSION) format --check .

hacs:
	python3 scripts/hacs_check.py

manifest:
	python3 scripts/manifest_check.py

zip:
	python3 scripts/build_zip.py
