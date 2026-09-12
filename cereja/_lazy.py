"""PEP 562 package facades without proxy objects or eager discovery."""

from importlib import import_module as _import_module

from ._exports import EXPORTS as _EXPORTS, STAR_EXPORTS as _STAR_EXPORTS


def attach(namespace: dict, exports: dict | None = None) -> None:
    """Install lazy attributes on a package, caching only successful resolutions.

    Importlib coordinates module initialization. Holding another lock across an
    import can deadlock mutually dependent packages, so do not add one here.
    """
    package = namespace["__name__"]
    targets = _EXPORTS[package] if exports is None else exports

    def __getattr__(name: str):
        try:
            module_name, attribute = targets[name]
        except KeyError:
            raise AttributeError(f"module {package!r} has no attribute {name!r}") from None
        module = _import_module(module_name)
        # Import errors and exceptions inside the implementation must propagate.
        value = module if attribute is None else getattr(module, attribute)
        # Preserve identity and an override installed while the import ran.
        return namespace.setdefault(name, value)

    def __dir__() -> list[str]:
        return sorted(namespace.keys() | targets.keys())

    namespace["__getattr__"] = __getattr__
    namespace["__dir__"] = __dir__
    namespace["__all__"] = _STAR_EXPORTS.get(package, tuple(targets))
