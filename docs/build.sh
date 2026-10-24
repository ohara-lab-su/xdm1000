#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCS="$ROOT/docs"
OUT="$DOCS/_build/html"
WORK="$DOCS/_work"
PACKAGE="$ROOT/src/xdm1000"
if [[ ! -d "$PACKAGE" ]]; then
  echo "Package source missing: $PACKAGE" >&2
  exit 1
fi
rm -rf "$OUT" "$WORK"
mkdir -p "$OUT" "$WORK"
for lang in en ja; do
  src="$WORK/$lang"
  mkdir -p "$src"
  cp "$DOCS/conf.py" "$src/conf.py"
  cp -R "$DOCS/$lang/." "$src/"
  sphinx-apidoc --force --module-first -o "$src/api" "$PACKAGE"
  test -s "$src/api/modules.rst" || { echo "API index was not generated: $lang" >&2; exit 1; }
  if [[ "$lang" == en ]]; then
    XDM_DOC_LANG=en sphinx-build -n -W --keep-going -b html "$src" "$OUT"
    XDM_DOC_LANG=en sphinx-build -n -W --keep-going -b html "$src" "$OUT/en"
  else
    XDM_DOC_LANG=ja sphinx-build -n -W --keep-going -b html "$src" "$OUT/ja"
  fi
done
for target in index.html en/index.html ja/index.html api/modules.html en/api/modules.html ja/api/modules.html; do
  test -f "$OUT/$target" || { echo "Missing output: $target" >&2; exit 1; }
done
touch "$OUT/.nojekyll"
