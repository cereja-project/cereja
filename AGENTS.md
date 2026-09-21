# AGENTS.md

## Working principle

Use the smallest context that is sufficient to understand, change, and verify the requested behavior.

Search before broad reading. Expand context only when the evidence requires it.

## Context discipline

* Start from the task. If it names a file, symbol, command, test, or error, inspect that target first.
* Before editing, inspect the current working tree and preserve unrelated existing changes.
* Locate the closest implementation and relevant tests before opening additional files.
* For large files, search for the relevant symbol, test, or phrase and read local ranges first. Do not read the whole file unless necessary.
* Do not bulk-read `cereja/`, `tests/`, `docs/`, `.agents/`, generated stubs, fixtures, notebooks, or other large artifacts.
* Prefer `rg`, `git grep`, or equivalent focused search. When bounded snippets are useful, use `cereja context search` with the smallest explicit roots and limits that fit the task.
* Use the repository root as a search root only when the relevant area is genuinely unknown.
* Do not use the persistent context cache for routine exploration. It writes per-user state and does not itself reduce returned context.
* Stop expanding context once the responsible implementation, affected contracts, and verification path are known.

Do not browse `.agents/` to discover guidance. Let skill metadata determine relevance. If a skill is selected, load only the references required for the task.

## Repository contracts

Preserve these unless changing them is explicit in the task:

* Support Python 3.11 and newer. Do not introduce syntax or standard-library requirements newer than 3.11.
* Keep runtime code free of mandatory third-party dependencies. Prefer the standard library within that constraint.
* Treat documented public APIs, import paths, aliases, object identity, and persisted compatibility formats as contracts.
* Keep `import cereja` lightweight, silent, and free of unrelated feature initialization.
* Keep root CLI dispatch lightweight. Command implementations load only after a command is selected.
* Do not add or widen public exports incidentally.
* Do not weaken established safe defaults such as TLS verification, sensitive-data redaction or non-persistence, opt-in sensitive identifiers, overwrite protection, atomic publication, or non-execution of untrusted content.
* Keep changes scoped to the requested behavior. Do not perform unrelated cleanup or create transient planning artifacts unless requested.

## Load task-specific context only when triggered

### Public imports or exports

When changing public imports, aliases, package facades, or exports, read as needed:

* `docs/guides/imports.md`
* `cereja/_exports.py`
* `cereja/_lazy.py`
* the affected implementation
* the relevant import, export, and lazy-loading tests

`__init__.pyi` files are generated. Do not edit them directly.

After an intentional export change:

```bash
python tools/generate_export_stubs.py
python tools/generate_export_stubs.py --check
```

Change `tests/fixtures/public_exports.json` only for an intentional public API change, never merely to make a compatibility test pass.

### CLI

Start with the affected module under `cereja/commands/` and search for its command-specific tests.

Read `cereja/entrypoint.py`, `cereja/commands/registry.py`, and registry/entrypoint tests only when root dispatch, command registration, global options, compatibility facades, or lazy command loading are affected.

Do not load unrelated command implementations.

### Context search or cache

For context behavior, start with the specific implementation under `cereja/system/_context/` and its focused tests.

Read `cereja/commands/context.py` for CLI behavior and `docs/guides/context-cache.md` when the user-facing or persistence contract is involved.

### Security-sensitive behavior

When changing compression/encryption, HTTP/transfers, static security analysis, privacy, protected code, or hardware/system collection, read the corresponding file under `docs/guides/` and the focused tests before changing its safety boundary or externally observable behavior.

Do not generalize a security guarantee beyond what the relevant guide and tests establish.

### Packaging, versions, or releases

Start with `pyproject.toml`, `cereja/_version.py`, and the relevant workflow under `.github/workflows/`.

Keep `VERSION` and `__version__` in `cereja/_version.py` consistent.

`cj_setup.py` is legacy tooling. Do not run it unless the task explicitly targets that script.

### Documentation

Read the target document first. Inspect implementation and tests only as needed to verify claims about behavior.

## Verification

Run the smallest checks that establish the affected behavior first.

For a focused change, run the relevant test module or test case rather than the complete suite by default.

For public import/export changes, run the applicable import, public-export, lazy-loading, and generated-stub checks.

For cryptographic implementation or compatibility changes, include:

```bash
python -S -m unittest tests.testcrypto tests.test_crypto_safety -v
```

Use `.github/workflows/pythonpackage.yml` as the source of truth for repository-wide CI gates.

Run the complete suite or broader gates when the change is cross-cutting, when focused checks cannot establish safety, or before claiming repository-wide validation:

```bash
python -m unittest discover -s tests -v
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

A local run on one Python version or operating system does not establish that the configured CI matrix passes.

Do not weaken, skip, or rewrite a test merely to make it pass unless the tested contract is intentionally changing.

Do not claim a check passed unless it was actually executed.

## Code Review Rules

* Flag accidental breaks to documented public APIs, import compatibility, persisted formats, or generated export contracts.
* Flag new mandatory runtime dependencies unless the change explicitly authorizes them.
* Flag changes that weaken established security or privacy defaults without an explicit requirement and corresponding tests.
* Flag manual edits to generated `__init__.pyi` files or compatibility fixtures that are not justified by the source-of-truth change.
* Leave deterministic formatting and lint enforcement to CI unless it exposes a behavioral defect.

## Completion

Before finishing:

* inspect the resulting diff;
* confirm unrelated existing work was preserved;
* confirm generated artifacts are consistent when applicable;
* report the behavior changed and the checks actually executed;
* state material validation that was not performed.

Do not equate generated code, a passing focused test, or a local run with successful repository-wide validation.
