from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cereja  # noqa: E402

project = "Cereja"
author = "The Cereja Project"
copyright = "2019, The Cereja Project"
release = cereja.__version__
version = cereja.__version__

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_title = f"Cereja {release}"
html_static_path = []

html_context = {
    "display_github": True,
    "github_user": "cereja-project",
    "github_repo": "cereja",
    "github_version": "master",
    "conf_py_path": "/docs/",
}

html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_typehints = "description"
autosummary_generate = True
napoleon_google_docstring = True
napoleon_numpy_docstring = True

myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
