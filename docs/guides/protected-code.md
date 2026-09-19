# Protected Python Code

Cereja can build an import-compatible protected copy of a Python module or
regular package. Python source and selected static resources are encrypted with
the existing `cereja.hashtools._crypto` format and decrypted only in memory when
the runtime needs them.

This feature protects plaintext at rest. It is not DRM and it cannot prevent a
user who controls the Python process from inspecting runtime memory, loaded
objects, or source exposed by Python introspection.

## Protect a package

Set the environment variable that will supply the runtime key. The same variable
can be used during the build to avoid an interactive password prompt.

PowerShell:

```powershell
$env:MYAPP_CODE_KEY = "secret"
cereja protect path/to/mypackage -o build/protected --key-env MYAPP_CODE_KEY
```

POSIX shells:

```bash
export MYAPP_CODE_KEY="secret"
cereja protect path/to/mypackage -o build/protected --key-env MYAPP_CODE_KEY
```

If the variable is not set during the build, the CLI asks for the password and
confirmation without echoing the value. The password is never embedded in the
generated bootstrap.

The result keeps the original import name:

```text
build/protected/
└── mypackage/
    ├── __init__.py
    └── __cereja__/
        ├── code/
        │   ├── __init__.py.enc
        │   └── ...
        └── resources/
            └── ...
```

Add `build/protected` to the Python import path and import the package normally:

```python
import mypackage
from mypackage.feature import run
```

Client code does not import Cereja explicitly. The generated bootstrap imports
the Cereja protected-code runtime internally, registers an import finder for the
package, decrypts the original package initializer in memory, and then handles
protected submodule imports on demand.

Cereja must still be installed in the runtime environment.

## Protect a standalone module

A single Python module is also supported:

```bash
cereja protect path/to/feature.py -o build/protected --key-env MYAPP_CODE_KEY
```

The consumer still uses:

```python
import feature
```

The generated `feature.py` is only a bootstrap. The original source is stored
encrypted under `__cereja__/code/`.

## Static resources

The default protected static extensions are:

```text
.json .html .htm .js .css
```

Additional extensions can be added:

```bash
cereja protect mypackage -o build/protected \
  --include-extension .yaml \
  --include-extension .svg
```

Protected resources are available without materializing plaintext through
standard package-resource APIs:

```python
from importlib.resources import files

config = files("mypackage").joinpath("config.json").read_text(encoding="utf-8")
template = files("mypackage").joinpath(
    "templates", "index.html"
).read_text(encoding="utf-8")
```

`pkgutil.get_data()` is also supported.

Direct filesystem access is different. Code such as
`open(Path(__file__).parent / "config.json")` expects a real plaintext file and
cannot remain transparent while also guaranteeing that plaintext is never
written to disk. Migrate that access to `importlib.resources` or add an
application-specific in-memory integration.

Files whose extensions are not selected for protection are copied unchanged.
This allows native extensions and other runtime files to remain available.

## Runtime behavior

The protected package uses a custom `MetaPathFinder` and loader. When Python
imports a protected module, Cereja:

1. reads the encrypted payload;
2. authenticates and decrypts it through `cereja.hashtools._crypto.decrypt`;
3. compiles the source bytes in memory;
4. executes the code in the normal module namespace;
5. never publishes the decrypted source as a file.

The custom loader does not generate bytecode for protected submodules. CPython
may create a `__pycache__` entry for the small plaintext bootstrap itself. That
bootstrap contains no original application source.

Python introspection can still request protected source through the loader.
That source is decrypted in memory for the request and is not written to disk.

## Build safety

Protection is built in a staging directory. Existing protected package output
is not replaced until the new tree has been generated successfully. Use
`--force` to replace an existing protected output.

The source package itself is never a valid output target. Output directories
inside the source package are rejected. Symbolic links inside protected package
trees are rejected in this first version.

Only regular packages containing `__init__.py` and standalone `.py` modules
are supported. Namespace packages are not supported yet.

The directory name `__cereja__` is reserved inside protected packages.

## Distribution

If the protected tree is repackaged into a wheel or sdist, the
`__cereja__/**/*.enc` payloads must be included as package data. A packaging
configuration that drops those files will produce an importable bootstrap with
missing encrypted payloads.

## Security boundary

The runtime key is supplied through an environment variable by default. This
keeps it out of the protected artifact, but environment variables are not a
hardware-backed secret store. A future key-provider interface can integrate
operating-system key stores, secret managers, license services, or HSM-backed
key retrieval without changing consumer imports.

The cryptographic primitive is intentionally the existing Cereja compatibility
format. It uses PBKDF2-HMAC-SHA256, an HMAC-authenticated historical keystream,
and Base64 storage. That construction is custom and has not undergone an
independent cryptographic audit.

The guarantee of this feature is narrower: the generated protected artifact and
normal runtime import path do not write the original protected source or static
resource plaintext to disk. A sufficiently privileged runtime user can still
recover executable code or plaintext from the running process.
