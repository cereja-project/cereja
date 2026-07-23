# Repository Tree Command Design

**Date:** 2026-07-23
**Status:** Approved

## Goal

Add a `cereja tree` command that renders the structure of a repository as a
deterministic Unicode tree. The command must work without Git and without new
runtime dependencies while honoring the common `.gitignore` patterns defined
in this specification.

## Command Interface

```text
cereja tree [path] [--depth N]
```

- `path` is optional and defaults to the current directory.
- Without `--depth`, traversal includes every non-ignored descendant.
- `--depth 0` renders only the root.
- `--depth 1` renders the root and its direct children.
- `--depth N` accepts only non-negative integers.
- Successful output is written to stdout and returns exit code `0`.
- The root label uses the resolved directory name followed by `/`.

Example:

```text
project/
├── cereja/
│   └── cli.py
└── pyproject.toml
```

Directories appear before files at each level. Each group is sorted
case-insensitively by name, with the original name used as a deterministic
tie-breaker. Directories have a trailing `/`. Hidden files and directories are
included unless an ignore rule or the built-in cache exclusions remove them.
Empty directories are included.

Symbolic links are displayed using their entry name and are never traversed.
A symlink that points to a directory is therefore a leaf and does not receive
a trailing `/`. Broken symbolic links are also displayed as leaves.

## CLI Integration

`cereja/cli.py` will register the `tree` subcommand and its optional arguments.
Its handler will validate the root path, call the tree renderer, print the
result, and return `0`.

Traversal, ignore-rule parsing, matching, and rendering will live in a new
private module, `cereja/_repository_tree.py`. Keeping this logic outside the
existing CLI module prevents the entry point from accumulating filesystem and
pattern-matching responsibilities. The module is an internal implementation
detail and will not be re-exported as part of Cereja's public Python API.

## Traversal and Data Flow

The renderer receives a resolved directory and an optional maximum depth. It
walks entries one directory at a time using `pathlib.Path`, carrying the
applicable ignore rules into each child directory.

For each visited directory:

1. Load its `.gitignore`, if present, after the inherited rules.
2. Evaluate entries against built-in exclusions and the ordered ignore rules.
3. Sort included directories and files deterministically.
4. Render the entries at the current depth.
5. Recurse only into included real directories when the depth permits.

A nested `.gitignore` applies only to its containing directory and
descendants. Because its rules are appended after inherited rules, its matching
rules take precedence over rules from parent directories.

Ignored directories are not traversed. Consequently, a negated file rule
cannot re-include a file whose parent directory remains excluded. A later rule
may re-include the directory itself, after which its descendants can be
evaluated normally.

## Supported `.gitignore` Rules

The parser intentionally supports the common subset selected for this feature:

- empty lines;
- comment lines beginning with `#`;
- negation using a leading `!`;
- leading `/` to anchor a pattern to the directory containing that
  `.gitignore`;
- trailing `/` to match directories only;
- `*`, `?`, and bracket expressions such as `[abc]`;
- `**` across directory boundaries;
- `.gitignore` files nested at any traversed level.

Paths are normalized to `/` before matching. Within patterns, `*`, `?`, and
bracket expressions do not match `/`; `**` may match across path segments. A
pattern with no `/` matches an entry name at any level beneath the
`.gitignore` that defines it. A pattern containing `/` matches the relative
path from that `.gitignore` directory.

Rules are evaluated in file and traversal order, and the last matching rule
wins. A negated matching rule marks the path as included. Surrounding
whitespace is removed from rule lines.

The following less-common Git details are outside this command's contract:

- escaping a leading `#` or `!`;
- preserving trailing spaces through backslash escapes;
- Git's global excludes file;
- `.git/info/exclude`;
- attributes or index state known only to Git.

## Built-in Exclusions

The following directory names are always omitted:

- `.git`
- `__pycache__`
- `.pytest_cache`
- `.mypy_cache`
- `.ruff_cache`
- `.tox`
- `.nox`

Files ending in `.pyc` or `.pyo` are also always omitted. These exclusions
cannot be negated by `.gitignore`, because they are command-level cache
filters rather than repository rules. The `.gitignore` files themselves
remain visible unless another applicable rule explicitly ignores them.

## Errors

- A missing root or a root that is not a directory produces `Error: ...` on
  stderr and exit code `1`.
- An unreadable directory or `.gitignore` identifies the affected path in an
  `Error: ...` message and returns exit code `1`.
- A non-integer or negative `--depth` is rejected by `argparse` as a usage
  error and returns exit code `2`.

The existing CLI error boundary will be extended only as needed to keep these
expected filesystem failures concise. Unexpected programming errors must not
be swallowed.

## Documentation and Version

- Add the complete command reference and examples to `docs/cli.md`.
- Add `cereja tree` to the concise CLI example in `README.md`.
- Change the package version from `2.1.5` to `2.1.6`, as approved for this
  public CLI addition.

## Testing

Tests use `unittest` and real isolated filesystem trees. They verify observable
CLI output rather than private implementation details.

Focused scenarios:

- the root label, Unicode connectors, directory-first ordering, and stable
  alphabetical ordering;
- the current directory default and an explicit root path;
- unlimited traversal and `--depth 0`, `--depth 1`, and deeper limits;
- comments, negation, anchored patterns, directory-only patterns, `*`, `?`,
  bracket expressions, and `**`;
- nested `.gitignore` precedence;
- built-in cache and compiled-Python exclusions;
- visible hidden files and visible `.gitignore`;
- non-traversal of directory symlinks where the platform permits symlink
  creation;
- missing paths, file roots, negative depths, and non-integer depths;
- `tree` appearing in `cereja --help`.

Verification commands:

```text
python -m unittest tests.test_cli -v
python -m unittest discover -s tests -v
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

## Alternatives Considered

### Ask Git for the effective file list

This gives exact ignore behavior with little application code, but requires
Git to be installed and the target to belong to a Git working tree.

### Add `pathspec`

This provides mature `.gitignore` matching in Python, but adds a runtime
dependency for one CLI command.

### Implement the common subset internally

This is the selected approach. It keeps the package dependency-free and works
before repository initialization. The explicit subset above limits complexity
and prevents the implementation from claiming complete Git compatibility.
