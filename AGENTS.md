# AGENTS.md

## Scope

Repository-wide instructions for agents working on Cereja.

Optimize for the smallest sufficient context. Do not explore the repository broadly when a focused search can identify the implementation, tests, and contracts involved.

## Context discipline

1. Start with the task and this file.
2. If the task names a file, symbol, command, or test, inspect that target first.
3. Locate related code with search before opening additional files.
4. Read the closest relevant tests before changing behavior.
5. Expand context only through direct dependencies, callers, public contracts, or documentation required by the task.
6. Stop reading when the evidence is sufficient to make and verify the requested change.

Do not preload entire directories such as `cereja/`, `tests/`, `docs/`, or `.agents/`.

Do not read large generated files or compatibility fixtures merely to understand the project.

When the location of relevant code is unknown, prefer bounded search. For example:

```bash
python -m cereja context search \
  --root cereja \
  --root tests \
  --query "TargetSymbol" \
  --extension py \
  --max-results 8 \
  --max-snippets 2 \
  --max-snippet-chars 240
```

Use `rg`, `git grep`, or an equivalent repository search when they are more direct.

Use `context list` only when file inventory is actually required.

Do not enable the persistent context cache unless repeated searches justify it.

## Repository invariants

Preserve these unless the task explicitly changes them:

* Python 3.11 is the minimum supported version.
* Runtime code remains dependency-free unless a dependency change is explicitly approved.
* Prefer standard-library implementations.
* Preserve backward compatibility where practical.
* Public APIs should remain small, reusable, and composable.
* Importing `cereja` must remain lightweight and free of incidental output or unrelated feature initialization.
* CLI root dispatch must remain lightweight; command implementations are loaded only when selected.
* Avoid unrelated refactors while making a focused change.

Do not use syntax or standard-library features unavailable in Python 3.11.

## Read by task, not by default

### Public imports or package exports

Read only as needed:

* `docs/guides/imports.md`
* `cereja/_exports.py`
* `cereja/_lazy.py`
* the affected implementation module
* `tests/test_import_contract.py`
* `tests/test_public_exports.py`
* relevant `tests/test_lazy*.py`

`__init__.pyi` files are generated. Do not edit them directly.

After an intentional export change:

```bash
python tools/generate_export_stubs.py
python tools/generate_export_stubs.py --check
```

Change `tests/fixtures/public_exports.json` only for a deliberate, reviewed public API change. Never update it merely to make a compatibility test pass.

### CLI work

Start with:

* the affected module under `cereja/commands/`
* the relevant tests in `tests/test_cli.py`

Read `cereja/entrypoint.py` and `cereja/commands/registry.py` only when dispatch, registration, global options, or command loading is involved.

Do not load unrelated command implementations.

### Context search or cache

Start with the specific component involved:

* `cereja/commands/context.py` for CLI behavior
* `cereja/system/_context/` for implementation
* `tests/test_context_search.py` for search behavior
* `tests/test_context_cache.py` for cache behavior

Read `docs/guides/context-cache.md` when user-facing behavior or documentation is part of the task.

### Packaging, versions, or distribution

Start with `pyproject.toml`.

Read `_version.py`, distribution tooling, CI, or packaging documentation only when the requested change touches those contracts.

### Documentation

Read the target document first. Inspect implementation or tests only when needed to verify a behavioral claim.

### Agent skills

Do not load skills automatically.

If a task clearly matches a skill description under `.agents/skills/`, read that skill's `SKILL.md`. Load only the reference files selected by that skill for the specific problem.

Generic Cereja development does not by itself require the `python-backend-dev` skill.

## Implementation discipline

Before editing behavior, identify:

* the implementation responsible for it;
* the closest existing tests;
* any public API, import, CLI, serialization, filesystem, or compatibility contract affected.

Prefer extending the existing local design over introducing a new abstraction.

Add a shared abstraction only when the current task demonstrates concrete duplication, coupling, or reuse that requires it.

Do not change public behavior incidentally.

Treat generated artifacts as outputs, not sources of truth.

## Verification

Run the smallest checks that prove the affected behavior first.

For a focused change, prefer the relevant test module or test case:

```bash
python -m unittest tests.<relevant_test_module> -v
```

For changes to lazy loading or the public import surface, run the relevant contract checks:

```bash
python -m unittest discover -s tests -p test_import_contract.py -v
python -m unittest discover -s tests -p test_public_exports.py -v
python -m unittest discover -s tests -p "test_lazy*.py" -v
python tools/generate_export_stubs.py --check
```

Use the full suite when the change is cross-cutting, when targeted tests cannot establish safety, or before claiming repository-wide test success:

```bash
python -m unittest discover -s tests -v
```

Use the CI syntax and undefined-name check when Python code changes warrant repository-level validation:

```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

Do not claim a check passed unless it was actually executed.

## Completion

Before finishing:

* inspect the resulting diff;
* ensure unrelated files were not changed;
* confirm generated files are consistent when applicable;
* report the behavior changed and the checks actually executed;
* state any relevant validation that was not performed.

Do not turn a focused task into repository-wide cleanup.
