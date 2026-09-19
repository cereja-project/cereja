from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable

from cereja.hashtools._crypto import CryptoError, encrypt

from ._runtime import (
    CODE_DIR,
    CONTROL_DIR,
    DEFAULT_KEY_ENV,
    ENCRYPTED_SUFFIX,
    RESOURCE_DIR,
    ProtectionError,
)

DEFAULT_STATIC_EXTENSIONS = frozenset({
    ".json",
    ".html",
    ".htm",
    ".js",
    ".css",
})
_IGNORED_NAMES = {"__pycache__"}
_IGNORED_SUFFIXES = {".pyc", ".pyo"}


def protect_path(
    source: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    password: str | bytes,
    *,
    key_env: str = DEFAULT_KEY_ENV,
    static_extensions: Iterable[str] | None = None,
    force: bool = False,
) -> Path:
    """Build an import-compatible protected module or package tree."""
    source_path = Path(source).resolve()
    output_root = Path(output_dir).resolve()

    if not source_path.exists():
        raise FileNotFoundError(str(source_path))
    if not key_env or "\x00" in key_env:
        raise ProtectionError(
            "key_env must be a non-empty environment "
            "variable name"
        )

    extensions = _normalize_extensions(
        static_extensions
    )

    if source_path.is_file():
        if source_path.suffix.lower() != ".py":
            raise ProtectionError(
                "Single-file protection currently "
                "supports Python modules only"
            )
        return _protect_module(
            source_path,
            output_root,
            password,
            key_env=key_env,
            force=force,
        )

    if not (
        source_path.is_dir()
        and (source_path / "__init__.py").is_file()
    ):
        raise ProtectionError(
            "Package protection requires a directory "
            "containing __init__.py"
        )

    return _protect_package(
        source_path,
        output_root,
        password,
        key_env=key_env,
        static_extensions=extensions,
        force=force,
    )


def _normalize_extensions(
    static_extensions: Iterable[str] | None,
) -> frozenset[str]:
    values = set(DEFAULT_STATIC_EXTENSIONS)
    if static_extensions is None:
        return frozenset(values)

    for extension in static_extensions:
        normalized = extension.strip().lower()
        if not normalized:
            continue
        if not normalized.startswith("."):
            normalized = "." + normalized
        values.add(normalized)
    return frozenset(values)


def _protect_package(
    source: Path,
    output_root: Path,
    password: str | bytes,
    *,
    key_env: str,
    static_extensions: frozenset[str],
    force: bool,
) -> Path:
    if not source.name.isidentifier():
        raise ProtectionError(
            "Package directory is not a valid Python "
            f"identifier: {source.name!r}"
        )

    destination = output_root / source.name
    _validate_output_location(
        source,
        output_root,
    )
    _check_destination(
        destination,
        force,
    )
    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    stage_root = Path(
        tempfile.mkdtemp(
            prefix=".cereja-protect-",
            dir=output_root,
        )
    )
    staged = stage_root / source.name
    staged.mkdir()

    try:
        control = staged / CONTROL_DIR
        code_root = control / CODE_DIR
        resource_root = control / RESOURCE_DIR
        code_root.mkdir(parents=True)
        resource_root.mkdir(parents=True)

        for path in source.rglob("*"):
            relative = path.relative_to(source)

            if CONTROL_DIR in relative.parts:
                raise ProtectionError(
                    "Source package uses reserved "
                    f"directory name {CONTROL_DIR!r}: "
                    f"{relative}"
                )
            if any(
                part in _IGNORED_NAMES
                for part in relative.parts
            ):
                continue
            if path.is_symlink():
                raise ProtectionError(
                    "Symbolic links are not supported "
                    "in protected packages: "
                    f"{relative}"
                )
            if path.is_dir():
                (staged / relative).mkdir(
                    parents=True,
                    exist_ok=True,
                )
                continue
            if (
                path.suffix.lower()
                in _IGNORED_SUFFIXES
            ):
                continue

            suffix = path.suffix.lower()
            if suffix == ".py":
                payload = (
                    code_root
                    / relative.with_name(
                        relative.name
                        + ENCRYPTED_SUFFIX
                    )
                )
                _write_encrypted(
                    payload,
                    path.read_bytes(),
                    password,
                )
                continue

            if suffix in static_extensions:
                payload = (
                    resource_root
                    / relative.with_name(
                        relative.name
                        + ENCRYPTED_SUFFIX
                    )
                )
                _write_encrypted(
                    payload,
                    path.read_bytes(),
                    password,
                )
                continue

            target = staged / relative
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            shutil.copy2(path, target)

        (staged / "__init__.py").write_text(
            _package_bootstrap(key_env),
            encoding="utf-8",
        )
        _publish_package(
            staged,
            destination,
            stage_root,
        )
        return destination
    finally:
        shutil.rmtree(
            stage_root,
            ignore_errors=True,
        )


def _protect_module(
    source: Path,
    output_root: Path,
    password: str | bytes,
    *,
    key_env: str,
    force: bool,
) -> Path:
    if not source.stem.isidentifier():
        raise ProtectionError(
            "Module name is not a valid Python "
            f"identifier: {source.stem!r}"
        )

    _validate_output_location(
        source,
        output_root,
    )
    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = output_root / source.name
    payload = (
        output_root
        / CONTROL_DIR
        / CODE_DIR
        / (source.name + ENCRYPTED_SUFFIX)
    )
    if (
        destination.exists()
        or payload.exists()
    ) and not force:
        raise ProtectionError(
            "Protected output already exists for "
            f"{source.name!r}; use force=True "
            "to replace it"
        )

    stage_root = Path(
        tempfile.mkdtemp(
            prefix=".cereja-protect-",
            dir=output_root,
        )
    )
    try:
        staged_stub = stage_root / source.name
        staged_payload = (
            stage_root
            / CONTROL_DIR
            / CODE_DIR
            / (source.name + ENCRYPTED_SUFFIX)
        )
        _write_encrypted(
            staged_payload,
            source.read_bytes(),
            password,
        )
        staged_stub.write_text(
            _module_bootstrap(key_env),
            encoding="utf-8",
        )

        _publish_module(
            staged_stub,
            staged_payload,
            destination,
            payload,
            stage_root,
        )
        return destination
    finally:
        shutil.rmtree(
            stage_root,
            ignore_errors=True,
        )


def _write_encrypted(
    destination: Path,
    data: bytes,
    password: str | bytes,
) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    try:
        encrypted = encrypt(
            data,
            password,
        )
    except CryptoError as exc:
        raise ProtectionError(
            "Unable to encrypt protected payload"
        ) from exc
    destination.write_text(
        encrypted,
        encoding="ascii",
    )


def _check_destination(
    destination: Path,
    force: bool,
) -> None:
    if (
        destination.exists()
        and not force
    ):
        raise ProtectionError(
            f"Output already exists: {destination}. "
            "Use force=True to replace it"
        )


def _publish_package(
    staged: Path,
    destination: Path,
    stage_root: Path,
) -> None:
    backup = stage_root / "previous-package"
    had_previous = destination.exists()

    if had_previous:
        os.replace(
            destination,
            backup,
        )

    try:
        os.replace(
            staged,
            destination,
        )
    except Exception:
        if destination.exists():
            shutil.rmtree(
                destination,
                ignore_errors=True,
            )
        if (
            had_previous
            and backup.exists()
        ):
            os.replace(
                backup,
                destination,
            )
        raise


def _publish_module(
    staged_stub: Path,
    staged_payload: Path,
    destination: Path,
    payload: Path,
    stage_root: Path,
) -> None:
    backup_stub = stage_root / "previous-module"
    backup_payload = (
        stage_root / "previous-payload"
    )
    had_stub = destination.exists()
    had_payload = payload.exists()

    if had_stub:
        os.replace(
            destination,
            backup_stub,
        )
    if had_payload:
        os.replace(
            payload,
            backup_payload,
        )

    payload.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        os.replace(
            staged_payload,
            payload,
        )
        os.replace(
            staged_stub,
            destination,
        )
    except Exception:
        destination.unlink(
            missing_ok=True,
        )
        payload.unlink(
            missing_ok=True,
        )
        if (
            had_stub
            and backup_stub.exists()
        ):
            os.replace(
                backup_stub,
                destination,
            )
        if (
            had_payload
            and backup_payload.exists()
        ):
            payload.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            os.replace(
                backup_payload,
                payload,
            )
        raise


def _validate_output_location(
    source: Path,
    output_root: Path,
) -> None:
    if source.is_dir():
        if (
            output_root / source.name
            == source
        ):
            raise ProtectionError(
                "Output directory would replace "
                "the source package"
            )
        try:
            output_root.relative_to(source)
        except ValueError:
            return
        raise ProtectionError(
            "Output directory cannot be inside "
            "the source package"
        )

    if output_root == source.parent:
        raise ProtectionError(
            "Output directory for a module must "
            "differ from the source directory"
        )


def _package_bootstrap(
    key_env: str,
) -> str:
    return (
        '"""Generated by Cereja protected '
        'package tooling."""\n'
        "from cereja.protect import "
        "bootstrap_package as __cereja_bootstrap\n"
        "__cereja_bootstrap("
        "__name__, __file__, "
        f"key_env={key_env!r})\n"
        "del __cereja_bootstrap\n"
    )


def _module_bootstrap(
    key_env: str,
) -> str:
    return (
        '"""Generated by Cereja protected '
        'module tooling."""\n'
        "from cereja.protect import "
        "bootstrap_module as __cereja_bootstrap\n"
        "__cereja_bootstrap("
        "__name__, __file__, "
        f"key_env={key_env!r})\n"
        "del __cereja_bootstrap\n"
    )
