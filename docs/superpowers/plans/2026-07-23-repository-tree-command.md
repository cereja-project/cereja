# Repository Tree Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with TDD checkpoints.

**Goal:** Add `cereja tree [path] [--depth N]` and expose its filesystem traversal as the reusable `cereja.render_repository_tree()` utility.

**Architecture:** Extend `cereja.system.Path.list_dir()` with opt-in hidden-entry and error-propagation behavior. Implement `.gitignore` parsing, filtered traversal, and Unicode rendering in `cereja/system/_repository_tree.py`, re-exporting only `render_repository_tree`. Keep `cereja/cli.py` as a thin argparse/printing adapter.

**Tech Stack:** Python 3.11+ standard library (`pathlib`, `os`, `glob`, `fnmatch`, `argparse`), existing Cereja `Path`, `unittest`, Markdown docs, and the existing flake8 syntax/undefined-name check.

## Global Constraints

- Use the repository's Python `unittest` test suite and run the narrowest relevant check first.
- Write each behavioral test first, run it to establish the expected failure, then implement the minimum code and rerun it green.
- Reuse Cereja utilities before creating new logic; the renderer must consume `cereja.system.Path`.
- Do not add runtime dependencies or require the Git executable.
- Preserve `Path.list_dir()` defaults; new `include_hidden` and `raise_errors` options are keyword-only and opt-in.
- Support only the documented common `.gitignore` subset; do not claim full Git compatibility.
- Keep directories before files, sort case-insensitively with a deterministic name tie-breaker, include empty directories, and never traverse symlinks.
- Hide `.git`, the listed Python/tool caches, and `.pyc`/`.pyo` files regardless of `.gitignore` negation.
- Keep public functions and methods typed with Python 3.11 syntax and absolute imports.
- Update the public version from `2.1.5` to `2.1.6` and update CLI/path documentation in the same change.

---

### Task 1: Extend `Path.list_dir()` without changing defaults

**Files:**
- Modify: `cereja/system/_path.py` (`Path.list_dir`)
- Test: `tests/tests.py` (`PathTest`)

**Interfaces:**
- Produces: `Path.list_dir(search_match="*", only_name=False, recursive=False, *, include_hidden: bool = False, raise_errors: bool = False) -> list[Path]`.
- Existing callers using positional `search_match`, `only_name`, or `recursive` keep their current behavior.

- [ ] **Step 1: Write the failing tests**

Add tests to `PathTest` that create a temporary directory containing `visible.txt` and `.hidden.txt`:

```python
def test_list_dir_hides_dotfiles_by_default(self):
    with TempDir() as temp_dir:
        root = Path(temp_dir)
        with open(root.join("visible.txt").path, "w", encoding="utf-8") as file:
            file.write("visible")
        with open(root.join(".hidden.txt").path, "w", encoding="utf-8") as file:
            file.write("hidden")

        names = [item.name for item in root.list_dir()]

        self.assertEqual(names, ["visible.txt"])

def test_list_dir_includes_dotfiles_when_requested(self):
    with TempDir() as temp_dir:
        root = Path(temp_dir)
        with open(root.join("visible.txt").path, "w", encoding="utf-8") as file:
            file.write("visible")
        with open(root.join(".hidden.txt").path, "w", encoding="utf-8") as file:
            file.write("hidden")

        names = sorted(item.name for item in root.list_dir(include_hidden=True))

        self.assertEqual(names, [".hidden.txt", "visible.txt"])
```

Use the existing Cereja `Path` and `TempDir` helpers; do not introduce a second temporary-directory abstraction.

- [ ] **Step 2: Run the focused tests and verify the red state**

Run:

```text
python -m unittest tests.tests.PathTest.test_list_dir_hides_dotfiles_by_default tests.tests.PathTest.test_list_dir_includes_dotfiles_when_requested -v
```

Expected: the new `include_hidden` call fails with `TypeError: unexpected keyword argument 'include_hidden'`; the default test continues to pass.

- [ ] **Step 3: Implement the compatible extension**

Change the signature to add keyword-only options and pass `include_hidden` to Python 3.11's `glob.glob`:

```python
def list_dir(
        self,
        search_match="*",
        only_name=False,
        recursive=False,
        *,
        include_hidden=False,
        raise_errors=False,
) -> List["Path"]:
    if not self.is_dir:
        raise NotADirectoryError(f"check that the path '{self.path}' is correct")
    try:
        paths = glob.glob(
            self.join(search_match).path,
            recursive=recursive,
            include_hidden=include_hidden,
        )
        return [self.__class__(p).stem if only_name else self.__class__(p) for p in paths]
    except PermissionError as err:
        if raise_errors:
            raise
        logger.error(f"{err}")
        return []
```

Retain the existing return type and default permission behavior. Do not alter `list_files()` in this task.

- [ ] **Step 4: Run the focused tests and regression test**

Run:

```text
python -m unittest tests.tests.PathTest -v
```

Expected: all `PathTest` tests pass, including the pre-existing default listing assertion.

- [ ] **Step 5: Commit the isolated utility change**

```text
git add tests/tests.py cereja/system/_path.py
git commit -m "feat(system): add configurable hidden path listing"
```

### Task 2: Implement the reusable repository-tree renderer

**Files:**
- Create: `cereja/system/_repository_tree.py`
- Modify: `cereja/system/__init__.py` to re-export `render_repository_tree`
- Test: `tests/test_repository_tree.py`

**Interfaces:**
- Consumes: `Path.list_dir(include_hidden=True, raise_errors=True)`, `Path.is_link`, `Path.is_dir`, `Path.name`, and `Path.join`.
- Produces: `render_repository_tree(path: str | os.PathLike[str] | Path = ".", *, depth: int | None = None) -> str`.
- The function returns the rendered tree without a trailing newline; the CLI adds the terminal newline with `print()`.

- [ ] **Step 1: Write failing public-API tests**

Create isolated real filesystem scenarios in `tests/test_repository_tree.py`. Start with the base rendering contract:

```python
class RepositoryTreeTest(unittest.TestCase):
    def test_render_repository_tree_orders_directories_before_files(self):
        with temporary_workspace_directory() as temp_dir:
            root = Path(temp_dir) / "project"
            (root / "z-file.txt").write_text("z", encoding="utf-8")
            (root / "a-dir").mkdir()
            (root / "a-dir" / "nested.py").write_text("pass", encoding="utf-8")

            rendered = render_repository_tree(root)

            self.assertEqual(
                rendered,
                "project/\n├── a-dir/\n│   └── nested.py\n└── z-file.txt",
            )
```

Add these separate tests: `test_render_repository_tree_depth_zero_shows_root_only`, `test_render_repository_tree_depth_one_hides_grandchildren`, `test_render_repository_tree_defaults_to_current_directory`, `test_render_repository_tree_includes_empty_directories`, `test_render_repository_tree_hides_builtin_caches`, `test_render_repository_tree_shows_nonignored_hidden_files`, and `test_render_repository_tree_does_not_traverse_directory_symlinks` (the last test is skipped only when the platform cannot create symlinks). Each test must have one observable Act and an exact output assertion.

- [ ] **Step 2: Run the new tests and verify the red state**

Run:

```text
python -m unittest tests.test_repository_tree -v
```

Expected: import or symbol failures because `render_repository_tree` and its module do not yet exist.

- [ ] **Step 3: Implement the minimum renderer and rule model**

Implement these private units in `cereja/system/_repository_tree.py`:

```python
BUILTIN_IGNORED_DIRS = frozenset({
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".nox",
})
BUILTIN_IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})

def render_repository_tree(
        path: str | os.PathLike[str] | Path = ".",
        *,
        depth: int | None = None,
) -> str:
    root = path if isinstance(path, Path) else Path(path)
    if not root.exists:
        raise FileNotFoundError(f"Path not found: {root.path}")
    if not root.is_dir or root.is_link:
        raise NotADirectoryError(f"Path is not a directory: {root.path}")
    if depth is not None and depth < 0:
        raise ValueError("depth must be non-negative")
    lines = [f"{root.name}/"]
    _render_directory(root, relative_base="", inherited_rules=(), level=0, depth=depth, lines=lines)
    return "\n".join(lines)
```

The traversal must check `entry.is_link` before `entry.is_dir`, load `.gitignore` text with `open(ignore_file.path, encoding="utf-8", errors="replace")`, and pass inherited plus nested rules to descendants. Sort entries with directories first, then `(entry.name.casefold(), entry.name)`.

Represent each parsed rule with an internal immutable record containing its pattern, negation flag, directory-only flag, anchor flag, and ignore-file base. Match normalized `/` paths using a small glob-to-regex helper: `*`, `?`, and bracket expressions stay within one segment; `**` spans segments; patterns without `/` compare against each descendant basename; patterns with `/` compare against the path relative to the rule base. Evaluate matching rules in order and let the last match decide inclusion.

- [ ] **Step 4: Run the complete renderer test module**

Run:

```text
python -m unittest tests.test_repository_tree -v
```

Expected: all renderer, depth, cache, hidden-entry, ignore-rule, nested-ignore, and symlink tests pass.

- [ ] **Step 5: Commit the reusable renderer**

```text
git add tests/test_repository_tree.py cereja/system/_repository_tree.py cereja/system/__init__.py
git commit -m "feat(system): add reusable repository tree renderer"
```

### Task 3: Wire the public renderer into the CLI

**Files:**
- Modify: `cereja/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `cereja.system.render_repository_tree`.
- Produces: `cereja tree [path] [--depth N]`, with stdout on success and the existing `Error: <message>` stderr boundary on expected filesystem errors.

- [ ] **Step 1: Write failing CLI tests**

Add tests for help, explicit path output, and the default current directory. Use `redirect_stdout` and the existing temporary workspace helpers:

```python
def test_tree_command_renders_explicit_path(self):
    with temporary_workspace_directory() as temp_dir:
        root = Path(temp_dir) / "project"
        root.mkdir()
        (root / "README.md").write_text("readme", encoding="utf-8")
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["tree", str(root)])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.getvalue(), "project/\n└── README.md\n")
```

Add subprocess coverage for `python -m cereja tree --depth -1` expecting return code `2`, and a direct `main(["tree", missing_path])` test expecting return code `1` and an error on stderr.

- [ ] **Step 2: Run the new CLI tests and verify the red state**

Run:

```text
python -m unittest tests.test_cli.CliTest.test_tree_command_renders_explicit_path -v
```

Expected: `argparse` reports `invalid choice: 'tree'` because the subparser is not registered yet.

- [ ] **Step 3: Register the parser and handler**

Import `render_repository_tree` absolutely, add a non-negative argparse converter, and register the subparser:

```python
def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed

tree_parser = subparsers.add_parser("tree", help="Draw a repository tree.")
tree_parser.add_argument("path", nargs="?", default=".", help="Root directory.")
tree_parser.add_argument("--depth", type=_non_negative_int, help="Maximum depth.")
tree_parser.set_defaults(handler=_handle_tree)

def _handle_tree(args: argparse.Namespace) -> int:
    print(render_repository_tree(args.path, depth=args.depth))
    return 0
```

Extend the existing expected-error tuple with `PermissionError` so unreadable directories and `.gitignore` files retain the documented `Error: <message>` formatting and return code.

- [ ] **Step 4: Run focused CLI tests and module help**

Run:

```text
python -m unittest tests.test_cli.CliTest -v
python -m cereja --help
```

Expected: every CLI test passes and help contains `tree`.

- [ ] **Step 5: Commit the CLI integration**

```text
git add tests/test_cli.py cereja/cli.py
git commit -m "feat(cli): add repository tree command"
```

### Task 4: Update public docs and version

**Files:**
- Modify: `docs/cli.md`
- Modify: `README.md`
- Modify: `docs/guides/files-and-paths.md`
- Modify: `cereja/__init__.py`

**Interfaces:**
- Documents: `cereja tree`, `--depth`, filtering guarantees, and `cereja.render_repository_tree()`.
- Produces: package version `2.1.6`.

- [ ] **Step 1: Add documentation examples**

Document copyable commands and a short Unicode output example in `docs/cli.md`; add `cereja tree .` to the README CLI block; add a Python example to the files-and-paths guide:

```python
import cereja as cj

print(cj.render_repository_tree(".", depth=2))
```

Document that `.gitignore` common rules and built-in caches are filtered, hidden non-ignored files remain visible, and links are not traversed.

- [ ] **Step 2: Update the version**

Change only the version assignment in `cereja/__init__.py`:

```python
VERSION = "2.1.6.final.0"
```

- [ ] **Step 3: Verify docs/version surfaces**

Run:

```text
python -m cereja --version
git diff --check
```

Expected: version output is non-empty and reports `2.1.6`; whitespace validation exits successfully.

- [ ] **Step 4: Commit docs and version**

```text
git add docs/cli.md README.md docs/guides/files-and-paths.md cereja/__init__.py
git commit -m "docs(cli): document repository tree command"
```

### Task 5: Integrated verification and handoff

**Files:**
- Modify: none; this task only verifies the completed implementation.

**Interfaces:**
- Consumes: all prior task commits.
- Produces: observed test and lint evidence for the integrated feature.

- [ ] **Step 1: Run the focused integration set**

```text
python -m unittest tests.test_repository_tree tests.tests.PathTest tests.test_cli -v
```

Expected: all focused tests pass.

- [ ] **Step 2: Run the full suite**

```text
python -m unittest discover -s tests -v
```

Expected: the full repository suite passes without network access.

- [ ] **Step 3: Run the required syntax/undefined-name lint**

```text
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

Expected: exit code `0` and no syntax or undefined-name findings.

- [ ] **Step 4: Inspect the final diff and status**

```text
git diff HEAD~4 --check
git status --short
```

Expected: no whitespace errors; only intentional user changes remain, with no generated caches or build artifacts added.

- [ ] **Step 5: Report concrete verification evidence**

Summarize the command behavior, public API reuse (`Path.list_dir` and `render_repository_tree`), version change, commits, and the exact observed results. Explicitly call out any platform-specific symlink test that could not run.
