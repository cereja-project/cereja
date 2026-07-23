# Repository Tree Command Design

**Date:** 2026-07-23
**Status:** Approved

## Goal

Add a `cereja tree` command that renders the structure of a repository as a
deterministic Unicode tree. The command must work without Git and without new
runtime dependencies while honoring the common `.gitignore` patterns defined
in this specification. The implementation must also strengthen Cereja's
reusable filesystem API instead of leaving the behavior isolated inside the
CLI.

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
Its handler will call Cereja's public tree renderer, print the result, and
return `0`. Path and depth validation belong to the reusable renderer so the
CLI and Python callers receive the same behavior.

Traversal, ignore-rule parsing, matching, and rendering will live in
`cereja/system/_repository_tree.py`. The module will export:

```python
def render_repository_tree(
    path: str | os.PathLike[str] | Path = ".",
    *,
    depth: int | None = None,
) -> str:
    ...
```

`cereja.system` will re-export the function, which also makes it available as
`cereja.render_repository_tree`. The CLI is therefore the first consumer of a
new Cereja filesystem utility rather than the owner of the implementation.
Ignore-rule types and matching helpers remain private.

The existing `cereja.system.Path.list_dir()` will gain two keyword-only
options:

- `include_hidden=False`, preserving its current default while allowing the
  renderer to include non-ignored dotfiles;
- `raise_errors=False`, preserving its current permission-error behavior while
  allowing the renderer to surface unreadable paths.

The extension will use the `include_hidden` support available in Python 3.11's
`glob` module, which matches the package's minimum Python version.

## Cereja Utility Reuse Audit

The implementation will use Cereja's `Path` abstraction for path validation,
joining, directory listing, link detection, names, and file/directory
classification. `Path.list_dir()` will be improved as described above because
its current defaults omit hidden entries and suppress `PermissionError`, both
of which are configurable requirements for the tree renderer.

Other related utilities were evaluated:

- `FileIO` is designed to load and mutate file content in memory and currently
  suppresses permission errors during reads. A `.gitignore` parser needs a
  small, streaming, error-reporting read, so forcing `FileIO` into this path
  would weaken the error contract.
- `GitRepository` and `GitCommandRunner` require the Git executable, which was
  explicitly rejected for this feature.
- `Unicode` converts code points and exposes Unicode metadata. Literal box
  drawing characters are clearer for four fixed rendering tokens and avoid
  unnecessary object construction.

This audit is required by the repository's working principles: reuse is
preferred when responsibilities align, but existing tools are not used merely
to claim reuse.

## Traversal and Data Flow

The renderer receives a Cereja `Path` (or converts a path-like input into one)
and an optional maximum depth. It walks entries one directory at a time using
`Path.list_dir(include_hidden=True, raise_errors=True)`, carrying the
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
- A Python caller that passes a negative `depth` directly to
  `render_repository_tree()` receives `ValueError`.

The existing CLI error boundary will be extended only as needed to keep these
expected filesystem failures concise. Unexpected programming errors must not
be swallowed.

## Documentation and Version

- Add the complete command reference and examples to `docs/cli.md`.
- Add `cereja tree` to the concise CLI example in `README.md`.
- Document `cereja.render_repository_tree` and the new `Path.list_dir()`
  options in `docs/guides/files-and-paths.md`.
- Change the package version from `2.1.5` to `2.1.6`, as approved for this
  public CLI addition.

## Testing

Tests use `unittest` and real isolated filesystem trees. Most tree behavior is
verified through the public `render_repository_tree()` utility; focused CLI
tests verify argument wiring, stdout, help, and exit codes. Tests do not call
private ignore or rendering helpers.

Focused scenarios:

- the root label, Unicode connectors, directory-first ordering, and stable
  alphabetical ordering;
- `Path.list_dir()` preserving its current default and including dotfiles only
  when `include_hidden=True`;
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
python -m unittest tests.test_repository_tree tests.tests.PathTest tests.test_cli -v
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
