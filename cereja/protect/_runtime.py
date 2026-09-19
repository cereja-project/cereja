from __future__ import annotations

import io
import importlib.abc
import importlib.util
import os
import sys
from importlib.resources.abc import Traversable, TraversableResources
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import BinaryIO, Iterator, TextIO

from cereja.hashtools._crypto import CryptoError, decrypt

CONTROL_DIR = "__cereja__"
CODE_DIR = "code"
RESOURCE_DIR = "resources"
ENCRYPTED_SUFFIX = ".enc"
DEFAULT_KEY_ENV = "CEREJA_PROTECT_KEY"


class ProtectionError(RuntimeError):
    """Raised when protected code cannot be built or loaded."""


def _get_password(key_env: str) -> str:
    password = os.environ.get(key_env)
    if not password:
        raise ProtectionError(
            f"Missing runtime key. Set environment variable {key_env!r} "
            "before importing protected code."
        )
    return password


def _decrypt_file(path: Path, password: str) -> bytes:
    try:
        encrypted = path.read_text(encoding="ascii")
        return decrypt(encrypted, password)
    except FileNotFoundError:
        raise ProtectionError(f"Protected payload not found: {path}") from None
    except (UnicodeDecodeError, CryptoError, ValueError) as exc:
        raise ProtectionError(
            f"Unable to decrypt protected payload: {path}"
        ) from exc


class _ProtectedFinder(importlib.abc.MetaPathFinder):
    def __init__(self, package_name: str, package_dir: Path, password: str):
        self.package_name = package_name
        self.package_dir = package_dir.resolve()
        self.password = password
        self.control_dir = self.package_dir / CONTROL_DIR
        self.code_dir = self.control_dir / CODE_DIR
        self.resource_dir = self.control_dir / RESOURCE_DIR

    def find_spec(self, fullname: str, path=None, target=None):
        prefix = self.package_name + "."
        if not fullname.startswith(prefix):
            return None

        relative_name = fullname[len(prefix):]
        relative_path = Path(*relative_name.split("."))
        package_payload = (
            self.code_dir
            / relative_path
            / ("__init__.py" + ENCRYPTED_SUFFIX)
        )
        module_payload = self.code_dir / (
            str(relative_path) + ".py" + ENCRYPTED_SUFFIX
        )

        if package_payload.is_file():
            loader = _ProtectedLoader(
                self,
                fullname,
                package_payload,
                relative_path,
                True,
            )
            spec = importlib.util.spec_from_loader(
                fullname,
                loader,
                is_package=True,
            )
            if spec is not None:
                spec.origin = str(
                    self.package_dir / relative_path / "__init__.py"
                )
                spec.submodule_search_locations = [
                    str(self.package_dir / relative_path)
                ]
            return spec

        if module_payload.is_file():
            loader = _ProtectedLoader(
                self,
                fullname,
                module_payload,
                relative_path,
                False,
            )
            spec = importlib.util.spec_from_loader(
                fullname,
                loader,
                is_package=False,
            )
            if spec is not None:
                spec.origin = str(
                    self.package_dir / (str(relative_path) + ".py")
                )
            return spec

        return None


class _ProtectedLoader(importlib.abc.Loader):
    def __init__(
        self,
        finder: _ProtectedFinder,
        fullname: str,
        payload_path: Path,
        relative_path: Path,
        is_package: bool,
    ):
        self.finder = finder
        self.fullname = fullname
        self.payload_path = payload_path
        self.relative_path = relative_path
        self._is_package = is_package

    @property
    def logical_path(self) -> Path:
        if self._is_package:
            return (
                self.finder.package_dir
                / self.relative_path
                / "__init__.py"
            )
        return self.finder.package_dir / (
            str(self.relative_path) + ".py"
        )

    def create_module(self, spec):
        return None

    def get_filename(self, fullname: str) -> str:
        if fullname != self.fullname:
            raise ImportError(fullname)
        return str(self.logical_path)

    def get_source(self, fullname: str) -> str:
        if fullname != self.fullname:
            raise ImportError(fullname)
        source = _decrypt_file(
            self.payload_path,
            self.finder.password,
        )
        return importlib.util.decode_source(source)

    def is_package(self, fullname: str) -> bool:
        if fullname != self.fullname:
            raise ImportError(fullname)
        return self._is_package

    def exec_module(self, module: ModuleType) -> None:
        source = _decrypt_file(
            self.payload_path,
            self.finder.password,
        )
        module.__file__ = str(self.logical_path)
        module.__loader__ = self
        if module.__spec__ is not None:
            module.__spec__.loader = self
            module.__spec__.origin = str(self.logical_path)

        if self._is_package:
            package_path = str(self.logical_path.parent)
            module.__path__ = [package_path]
            if module.__spec__ is not None:
                module.__spec__.submodule_search_locations = [
                    package_path
                ]

        code = compile(
            source,
            str(self.logical_path),
            "exec",
            dont_inherit=True,
        )
        exec(code, module.__dict__)

    def get_data(self, path: str) -> bytes:
        requested = _safe_relative(
            Path(path),
            self.finder.package_dir,
        )
        encrypted = (
            self.finder.resource_dir
            / _encrypted_resource_path(requested)
        )
        if encrypted.is_file():
            return _decrypt_file(
                encrypted,
                self.finder.password,
            )

        physical = self.finder.package_dir / requested
        if (
            physical.is_file()
            and CONTROL_DIR not in physical.parts
        ):
            return physical.read_bytes()
        raise OSError(f"Resource not found: {path}")

    def get_resource_reader(self, fullname: str):
        if fullname == self.finder.package_name:
            relative_dir = Path()
        else:
            prefix = self.finder.package_name + "."
            if not fullname.startswith(prefix):
                return None
            relative_dir = Path(
                *fullname[len(prefix):].split(".")
            )
        return _ProtectedResourceReader(
            self.finder,
            relative_dir,
        )


class _ProtectedResourceReader(TraversableResources):
    def __init__(
        self,
        finder: _ProtectedFinder,
        package_relative_dir: Path,
    ):
        self.finder = finder
        self.package_relative_dir = package_relative_dir

    def files(self) -> Traversable:
        return _ProtectedTraversable(
            self.finder,
            self.package_relative_dir,
            PurePosixPath(),
        )


class _ProtectedTraversable(Traversable):
    def __init__(
        self,
        finder: _ProtectedFinder,
        package_relative_dir: Path,
        relative: PurePosixPath,
    ):
        self.finder = finder
        self.package_relative_dir = package_relative_dir
        self.relative = relative

    @property
    def name(self) -> str:
        if self.relative.parts:
            return self.relative.name
        if self.package_relative_dir.parts:
            return self.package_relative_dir.name
        return self.finder.package_name.rsplit(".", 1)[-1]

    def _logical_relative(self) -> Path:
        return self.package_relative_dir.joinpath(
            *self.relative.parts
        )

    def _physical_path(self) -> Path:
        return (
            self.finder.package_dir
            / self._logical_relative()
        )

    def _encrypted_path(self) -> Path:
        return (
            self.finder.resource_dir
            / _encrypted_resource_path(
                self._logical_relative()
            )
        )

    def _encrypted_dir(self) -> Path:
        return (
            self.finder.resource_dir
            / self._logical_relative()
        )

    def is_file(self) -> bool:
        return (
            self._encrypted_path().is_file()
            or self._physical_path().is_file()
        )

    def is_dir(self) -> bool:
        return (
            self._encrypted_dir().is_dir()
            or self._physical_path().is_dir()
        )

    def iterdir(self) -> Iterator[Traversable]:
        names: set[str] = set()
        physical = self._physical_path()
        if physical.is_dir():
            for child in physical.iterdir():
                if child.name == CONTROL_DIR:
                    continue
                names.add(child.name)

        encrypted = self._encrypted_dir()
        if encrypted.is_dir():
            for child in encrypted.iterdir():
                name = child.name
                if (
                    child.is_file()
                    and name.endswith(ENCRYPTED_SUFFIX)
                ):
                    name = name[:-len(ENCRYPTED_SUFFIX)]
                names.add(name)

        for name in sorted(names):
            yield self.joinpath(name)

    def joinpath(
        self,
        *descendants: str,
    ) -> Traversable:
        relative = self.relative
        for descendant in descendants:
            child = PurePosixPath(descendant)
            if (
                child.is_absolute()
                or ".." in child.parts
            ):
                raise ValueError(
                    "Resource path must stay inside "
                    f"the package: {descendant!r}"
                )
            relative = relative.joinpath(child)
        return _ProtectedTraversable(
            self.finder,
            self.package_relative_dir,
            relative,
        )

    def __truediv__(self, child: str) -> Traversable:
        return self.joinpath(child)

    def open(
        self,
        mode: str = "r",
        *args,
        **kwargs,
    ) -> BinaryIO | TextIO:
        if mode not in {"r", "rb"}:
            raise ValueError(
                "Protected resources are read-only"
            )

        encrypted = self._encrypted_path()
        if encrypted.is_file():
            data = _decrypt_file(
                encrypted,
                self.finder.password,
            )
            if "b" in mode:
                return io.BytesIO(data)

            encoding = (
                kwargs.pop("encoding", None)
                or "utf-8"
            )
            errors = (
                kwargs.pop("errors", None)
                or "strict"
            )
            newline = kwargs.pop("newline", None)
            if kwargs:
                unexpected = ", ".join(
                    sorted(kwargs)
                )
                raise TypeError(
                    f"Unexpected arguments: {unexpected}"
                )
            return io.TextIOWrapper(
                io.BytesIO(data),
                encoding=encoding,
                errors=errors,
                newline=newline,
            )

        physical = self._physical_path()
        if (
            not physical.is_file()
            or CONTROL_DIR in physical.parts
        ):
            raise FileNotFoundError(str(physical))
        return physical.open(
            mode,
            *args,
            **kwargs,
        )


def _safe_relative(path: Path, root: Path) -> Path:
    candidate = path.resolve()
    try:
        return candidate.relative_to(root)
    except ValueError:
        raise OSError(
            "Resource path escapes protected "
            f"package: {path}"
        ) from None


def _encrypted_resource_path(relative: Path) -> Path:
    if not relative.parts:
        return relative
    return relative.with_name(
        relative.name + ENCRYPTED_SUFFIX
    )


def _find_existing_finder(
    package_name: str,
    package_dir: Path,
):
    resolved = package_dir.resolve()
    for finder in sys.meta_path:
        if (
            isinstance(finder, _ProtectedFinder)
            and finder.package_name == package_name
            and finder.package_dir == resolved
        ):
            return finder
    return None


def bootstrap_package(
    package_name: str,
    bootstrap_file: str,
    *,
    key_env: str = DEFAULT_KEY_ENV,
) -> None:
    """Load a protected package without writing plaintext to disk."""
    package_dir = Path(
        bootstrap_file
    ).resolve().parent
    password = _get_password(key_env)

    previous = _find_existing_finder(
        package_name,
        package_dir,
    )
    if previous is not None:
        sys.meta_path.remove(previous)

    finder = _ProtectedFinder(
        package_name,
        package_dir,
        password,
    )
    sys.meta_path.insert(0, finder)

    module = sys.modules[package_name]
    payload = finder.code_dir / (
        "__init__.py" + ENCRYPTED_SUFFIX
    )
    loader = _ProtectedLoader(
        finder,
        package_name,
        payload,
        Path(),
        True,
    )

    try:
        loader.exec_module(module)
    except Exception:
        if finder in sys.meta_path:
            sys.meta_path.remove(finder)
        if previous is not None:
            sys.meta_path.insert(0, previous)
        raise


def bootstrap_module(
    module_name: str,
    bootstrap_file: str,
    *,
    key_env: str = DEFAULT_KEY_ENV,
) -> None:
    """Load a protected standalone module in memory."""
    bootstrap_path = Path(
        bootstrap_file
    ).resolve()
    password = _get_password(key_env)
    payload = (
        bootstrap_path.parent
        / CONTROL_DIR
        / CODE_DIR
        / (bootstrap_path.name + ENCRYPTED_SUFFIX)
    )
    finder = _ProtectedFinder(
        module_name,
        bootstrap_path.parent,
        password,
    )
    loader = _ProtectedLoader(
        finder,
        module_name,
        payload,
        Path(bootstrap_path.stem),
        False,
    )
    loader.exec_module(sys.modules[module_name])
