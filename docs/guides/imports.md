# Imports and public API

Cereja resolves its public exports on demand. Importing the root package loads
only the bootstrap registry, resolver, and release metadata; it does not print
a banner, start a worker, or initialize the functional domains.

```python
import cereja as cj

# Loads Path's implementation and its required dependencies now, not above.
path = cj.Path(".")

from cereja.system import Path
assert cj.Path is Path
```

Existing root and package import paths remain supported, including aliases such
as `stride_values`, `async_to_sync`, and `sync_to_async`. The facade returns and
caches the original objects, not proxy classes or wrapper functions. Existing
platform-specific exports remain platform-specific.

## What is deferred

Importing a package such as `cereja.concurrently` does not load its worker
implementations. Accessing `TaskList` loads its implementation, but does not load
`cereja.concurrently.process` merely to populate the package namespace.

A requested implementation can still load its real dependencies. In particular,
`FileIO` retains the dependencies of its existing implementation. Lazy exports
are not per-function isolation and do not change the behavior of file operations.
Errors in a deferred dependency occur on first access to the corresponding
feature, and are not converted into an unrelated missing-export error.

`from cereja import *` is still supported, but explicitly requests the complete
public surface and therefore defeats most of the lazy-loading benefit. Prefer
selective imports or `import cereja as cj` with selective attribute access.

## Discovery and tooling

`dir(cereja)` lists public names without loading their implementations.
`vars(cereja)` and `cereja.__dict__` contain only attributes already materialized
plus package metadata; they are not the complete API inventory. Introspection
that calls `getattr` for every name, including some help/documentation tools,
can intentionally resolve all exports.

The distribution includes explicit `__init__.pyi` re-exports and a `py.typed`
marker for static tools. This preserves discovery of the public API; it does
not imply that every legacy implementation has complete type annotations.

## Banner and release metadata

The banner is opt-in:

```python
import cereja
cereja.print_cereja_version()
```

`NON_BMP_SUPPORTED` remains a Boolean, evaluated on its first access. It checks
whether the current output encoding can represent the cherry character without
writing to the stream. It is not a guarantee that the terminal font has the glyph.

`VERSION` and `__version__` remain available at the root. Release values are now
literal metadata in `cereja/_version.py`, so importing the library or reading its
build metadata does not depend on a runtime Git command. Maintainers must update
both representations together, including development/prerelease versions;
the public version-formatting helpers remain available separately.

## Maintaining exports

Edit the static registry in `cereja/_exports.py` deliberately. Do not scan or
import feature modules to discover the public surface at runtime. Regenerate
the checked-in tooling declarations after an export change:

```bash
python tools/generate_export_stubs.py
python tools/generate_export_stubs.py --check
```

The frozen compatibility fixture in `tests/fixtures/public_exports.json` is
independent of the runtime registry and should change only for a reviewed API
change, not merely to make a failing compatibility test pass. Keep ordinary
implementation dependencies explicit; do not introduce root-facade imports to
initialize unrelated domains as a side effect.

Measure isolated imports from a checkout with:

```bash
python benchmarks/imports.py --samples 7
```

The benchmark reports module counts, captured output, started threads, and
per-process timings. Compare timings on equivalent systems, and treat the
loaded-module contracts as the deterministic regression checks.
