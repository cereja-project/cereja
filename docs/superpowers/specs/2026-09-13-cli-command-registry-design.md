# Command Registry CLI Design

## Goal
Move all Cereja CLI command configuration out of `cereja/cli.py` into `cereja.commands`, with one lazy root dispatcher that owns `cereja --help`, command discovery, version handling, and compatibility routing.

## Root behavior
`cereja.entrypoint` is the installed entrypoint and the single root dispatcher. It builds a lightweight argparse parser from static command metadata only. Root help must list every supported command without importing command implementation modules.

Commands: `compress`, `decompress`, `encrypt`, `decrypt`, `tree`, `context`, `security`, `http`, `download`, `system`, `module`.

`cereja <command> ...` dynamically imports only the selected command module and calls its `main(argv)`.

## Registry
`cereja.commands.registry` contains immutable command metadata: name, help text, module path. The registry is the source of truth for both root help and dispatch. It must not import implementation modules.

## Compatibility
- `from cereja.cli import main` remains supported and delegates to `cereja.entrypoint.main`.
- Legacy `cereja --startmodule PATH` remains supported temporarily and routes to `cereja module create PATH`.
- Existing command syntax and output remain compatible unless already intentionally changed.
- `cereja.security._cli` remains a compatibility facade to the command module if needed by tests/internal callers.

## Command modules
Create focused modules under `cereja/commands`: `compress.py`, `decompress.py`, `encrypt.py`, `decrypt.py`, `tree.py`, `context.py`, `security.py`, `module.py`, plus existing `http.py`, `download.py`, `system.py`.

Shared command-only primitives (`CliError`, integer validators, output-path checks) live in `cereja.commands._common`.

## Lazy-import constraint
Running `cereja --help`, `cereja --version`, or importing `cereja.entrypoint` must not import HTTP, security analysis, hardware collectors, compression implementation, context database, or file implementation modules.

## Testing
TDD coverage must verify:
- root help lists every registry command including http/download/system;
- help does not import implementations;
- each legacy command dispatches through its command module;
- old `cereja.cli.main` facade behaves identically;
- `--startmodule` compatibility routes to `module create`;
- representative legacy command behavior remains unchanged;
- installed entrypoint/distribution checks remain green.

## Final state
`cereja/cli.py` is a small compatibility facade and contains no parser, command registration, or command handlers. Temporary Superpowers spec/plan files are removed before merge.