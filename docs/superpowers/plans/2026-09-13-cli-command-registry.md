# Command Registry CLI Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate every Cereja CLI command to `cereja.commands` and make a lightweight registry drive root help and lazy dispatch while preserving legacy CLI behavior.

**Architecture:** `cereja.commands.registry` stores static metadata only. `cereja.entrypoint` parses root options and command names, then dynamically imports exactly one command module. `cereja.cli` becomes a compatibility facade. Each command module owns its parser and execution.

**Tech Stack:** Python 3.11+ stdlib `argparse`/`importlib`; existing Cereja APIs; unittest; zero new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-09-13-cli-command-registry-design.md`

## Global Constraints
- Preserve existing command syntax and behavior.
- `cereja --help` lists all commands from one registry.
- Root help/version/import do not import command implementations.
- Preserve `from cereja.cli import main`.
- Preserve `--startmodule` as compatibility routing to `module create`.
- No unrelated refactors.

---

### Task 1: Registry and root-dispatch contracts
**Files:** create `tests/test_command_registry.py`; create `cereja/commands/registry.py`; modify `cereja/entrypoint.py`.
- [ ] Add failing tests for complete root help, lazy imports, registry uniqueness, command dispatch, version, and unknown command behavior.
- [ ] Verify RED on current dispatcher.
- [ ] Implement static registry and root parser using `parse_known_args`; command subparsers exist only to render help and identify the command.
- [ ] Dynamically import selected module and call `main(remaining_args)`.
- [ ] Verify focused tests GREEN.

### Task 2: Shared CLI primitives and legacy commands
**Files:** create `cereja/commands/_common.py`, `compress.py`, `decompress.py`, `encrypt.py`, `decrypt.py`, `tree.py`, `context.py`, `module.py`; update relevant tests.
- [ ] Add/adjust tests before each migration so legacy behavior is pinned.
- [ ] Move parsers and handlers out of `cereja/cli.py` without changing behavior.
- [ ] Share only command-specific validation/error primitives where duplication is real.
- [ ] Implement `module create PATH` and legacy `--startmodule` routing.
- [ ] Verify legacy CLI tests GREEN.

### Task 3: Security and compatibility facades
**Files:** create `cereja/commands/security.py`; replace `cereja/security/_cli.py` with compatibility facade; replace `cereja/cli.py` with compatibility facade; update tests/benchmark imports where appropriate.
- [ ] Add failing facade/dispatch tests.
- [ ] Move security parser/handler to commands.
- [ ] Make `cereja.cli.main` delegate lazily to entrypoint and contain no parser/handlers.
- [ ] Keep security compatibility entrypoint working.
- [ ] Verify imports remain lazy and no circular import exists.

### Task 4: Help/docs/distribution validation
**Files:** update `docs/cli.md` as needed and CLI tests.
- [ ] Verify `cereja --help` lists compress/decompress/encrypt/decrypt/tree/context/security/http/download/system/module.
- [ ] Verify representative `--help` for each command.
- [ ] Run full configured CI including distribution and cross-platform import contracts.
- [ ] Remove temporary Superpowers spec/plan files from final diff.
- [ ] Open draft PR with exact final head and CI evidence.