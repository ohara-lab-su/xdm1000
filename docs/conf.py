from __future__ import annotations
import os
import sys
from pathlib import Path

# The configuration is copied to docs/_work/<lang>/conf.py by build.sh.
# Resolve the repository root from either the staging or the source location.
CONF_DIR = Path(__file__).resolve().parent
if CONF_DIR.parent.name == "_work":
    ROOT = CONF_DIR.parents[2]
else:
    ROOT = CONF_DIR.parent
sys.path.insert(0, str(ROOT / "src"))
project = "xdm1000"
root_doc = "index"
extensions = ["myst_parser", "sphinx.ext.autodoc", "sphinx.ext.napoleon", "sphinx.ext.viewcode"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
exclude_patterns = ["_build", "_work"]
html_theme = "sphinx_rtd_theme"
language = os.environ.get("XDM_DOC_LANG", "en")
autodoc_mock_imports = ["serial", "ese774_frame", "xlogger", "xlogger_py"]
