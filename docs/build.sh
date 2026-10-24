#!/usr/bin/env bash
set -euo pipefail

DOCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$DOCS_DIR/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/src/xdm1000"
BUILD_DIR="$DOCS_DIR/_build/html"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "ERROR: Python package not found: $SOURCE_DIR" >&2
  exit 1
fi

export PYTHONPATH="$ROOT_DIR/src:${PYTHONPATH:-}"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Each language has its own source root and toctree.
# Generate API documentation from the same package for both languages.
sphinx-apidoc --force --module-first -o "$DOCS_DIR/en/api" "$SOURCE_DIR"
sphinx-apidoc --force --module-first -o "$DOCS_DIR/ja/api" "$SOURCE_DIR"

# The English source is also the site root; no redirect or extra landing page.
sphinx-build -b html -c "$DOCS_DIR" -D language=en "$DOCS_DIR/en" "$BUILD_DIR"
sphinx-build -b html -c "$DOCS_DIR" -D language=en "$DOCS_DIR/en" "$BUILD_DIR/en"
sphinx-build -b html -c "$DOCS_DIR" -D language=ja "$DOCS_DIR/ja" "$BUILD_DIR/ja"

for page in index.html en/index.html ja/index.html \
            api/modules.html en/api/modules.html ja/api/modules.html \
            manual/architecture.html en/manual/architecture.html ja/manual/architecture.html; do
  if [[ ! -f "$BUILD_DIR/$page" ]]; then
    echo "ERROR: Missing generated page: $page" >&2
    exit 1
  fi
done

touch "$BUILD_DIR/.nojekyll"
