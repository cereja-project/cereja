import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cereja.hashtools._crypto import CryptoError
from cereja.protect import ProtectionError, protect_path


ROOT = Path(__file__).resolve().parents[1]
KEY_ENV = "CEREJA_TEST_PROTECT_KEY"


class ProtectedCodeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source_root = self.root / "source"
        self.output_root = self.root / "protected"
        self.source_root.mkdir()

    def _create_package(self) -> Path:
        package = self.source_root / "samplepkg"
        nested = package / "nested"
        templates = package / "templates"
        nested.mkdir(parents=True)
        templates.mkdir()

        (package / "__init__.py").write_text(
            "from .core import answer\n"
            "from importlib.resources import files\n"
            "CONFIG = files(__package__).joinpath("
            "'data.json').read_text(encoding='utf-8')\n",
            encoding="utf-8",
        )
        (package / "core.py").write_text(
            'SOURCE_MARKER = "PLAINTEXT_PYTHON_MARKER"\n'
            "from .nested.util import value\n"
            "answer = value + 1\n",
            encoding="utf-8",
        )
        (nested / "__init__.py").write_text(
            "from .util import value\n",
            encoding="utf-8",
        )
        (nested / "util.py").write_text(
            "value = 41\n",
            encoding="utf-8",
        )
        (package / "data.json").write_text(
            '{"marker": "PLAINTEXT_JSON_MARKER"}',
            encoding="utf-8",
        )
        (templates / "index.html").write_text(
            "<h1>PLAINTEXT_HTML_MARKER</h1>",
            encoding="utf-8",
        )
        (package / "raw.bin").write_bytes(
            b"unprotected-binary"
        )
        return package

    def _run(
        self,
        output_root: Path,
        script: str,
        *,
        key: str | None,
    ) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env.pop(KEY_ENV, None)
        if key is not None:
            env[KEY_ENV] = key

        existing = env.get("PYTHONPATH")
        entries = [
            str(output_root),
            str(ROOT),
        ]
        if existing:
            entries.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(entries)

        return subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
        )

    def _all_output_bytes(
        self,
        output_root: Path,
    ) -> bytes:
        return b"\n".join(
            path.read_bytes()
            for path in output_root.rglob("*")
            if path.is_file()
        )

    def test_protected_package_imports_and_resources_in_memory(self):
        package = self._create_package()
        destination = protect_path(
            package,
            self.output_root,
            "secret",
            key_env=KEY_ENV,
        )

        self.assertEqual(
            destination,
            self.output_root / "samplepkg",
        )
        self.assertTrue(
            (
                destination
                / "__cereja__"
                / "code"
                / "core.py.enc"
            ).is_file()
        )
        self.assertFalse(
            (destination / "core.py").exists()
        )
        self.assertFalse(
            (destination / "data.json").exists()
        )

        generated = self._all_output_bytes(
            self.output_root
        )
        self.assertNotIn(
            b"PLAINTEXT_PYTHON_MARKER",
            generated,
        )
        self.assertNotIn(
            b"PLAINTEXT_JSON_MARKER",
            generated,
        )
        self.assertNotIn(
            b"PLAINTEXT_HTML_MARKER",
            generated,
        )

        script = r"""
import importlib.resources
import inspect
import json
import pkgutil

import samplepkg
import samplepkg.core
from samplepkg.nested import value

payload = {
    "answer": samplepkg.answer,
    "nested": value,
    "config": samplepkg.CONFIG,
    "html": importlib.resources.files("samplepkg").joinpath(
        "templates", "index.html"
    ).read_text(encoding="utf-8"),
    "pkgutil": pkgutil.get_data(
        "samplepkg", "data.json"
    ).decode("utf-8"),
    "raw": importlib.resources.files(
        "samplepkg"
    ).joinpath("raw.bin").read_bytes().decode("ascii"),
    "source": inspect.getsource(
        samplepkg.core
    ),
}
print(json.dumps(payload))
"""
        result = self._run(
            self.output_root,
            script,
            key="secret",
        )
        self.assertEqual(
            result.returncode,
            0,
            result.stderr,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["answer"], 42)
        self.assertEqual(payload["nested"], 41)
        self.assertIn(
            "PLAINTEXT_JSON_MARKER",
            payload["config"],
        )
        self.assertIn(
            "PLAINTEXT_HTML_MARKER",
            payload["html"],
        )
        self.assertIn(
            "PLAINTEXT_JSON_MARKER",
            payload["pkgutil"],
        )
        self.assertEqual(
            payload["raw"],
            "unprotected-binary",
        )
        self.assertIn(
            "PLAINTEXT_PYTHON_MARKER",
            payload["source"],
        )

        after_import = self._all_output_bytes(
            self.output_root
        )
        self.assertNotIn(
            b"PLAINTEXT_PYTHON_MARKER",
            after_import,
        )
        self.assertNotIn(
            b"PLAINTEXT_JSON_MARKER",
            after_import,
        )

    def test_missing_and_wrong_runtime_keys_fail_closed(self):
        package = self._create_package()
        protect_path(
            package,
            self.output_root,
            "secret",
            key_env=KEY_ENV,
        )

        missing = self._run(
            self.output_root,
            "import samplepkg",
            key=None,
        )
        self.assertNotEqual(
            missing.returncode,
            0,
        )
        self.assertIn(
            "Missing runtime key",
            missing.stderr,
        )

        wrong = self._run(
            self.output_root,
            "import samplepkg",
            key="wrong",
        )
        self.assertNotEqual(
            wrong.returncode,
            0,
        )
        self.assertIn(
            "Unable to decrypt protected payload",
            wrong.stderr,
        )

    def test_standalone_module_keeps_import_syntax(self):
        module = self.source_root / "standalone.py"
        module.write_text(
            'MARKER = "STANDALONE_PLAINTEXT_MARKER"\n'
            "VALUE = 99\n",
            encoding="utf-8",
        )

        destination = protect_path(
            module,
            self.output_root,
            "module-secret",
            key_env=KEY_ENV,
        )
        self.assertEqual(
            destination,
            self.output_root / "standalone.py",
        )

        result = self._run(
            self.output_root,
            (
                "import standalone; "
                "print(standalone.VALUE)"
            ),
            key="module-secret",
        )
        self.assertEqual(
            result.returncode,
            0,
            result.stderr,
        )
        self.assertEqual(
            result.stdout.strip(),
            "99",
        )
        self.assertNotIn(
            b"STANDALONE_PLAINTEXT_MARKER",
            self._all_output_bytes(
                self.output_root
            ),
        )

    def test_force_preserves_previous_output_when_build_fails(self):
        package = self._create_package()
        destination = protect_path(
            package,
            self.output_root,
            "secret",
            key_env=KEY_ENV,
        )
        before = {
            path.relative_to(destination): path.read_bytes()
            for path in destination.rglob("*")
            if path.is_file()
        }

        with patch(
            "cereja.protect._builder.encrypt",
            side_effect=CryptoError("failure"),
        ):
            with self.assertRaises(
                ProtectionError
            ):
                protect_path(
                    package,
                    self.output_root,
                    "replacement-secret",
                    key_env=KEY_ENV,
                    force=True,
                )

        after = {
            path.relative_to(destination): path.read_bytes()
            for path in destination.rglob("*")
            if path.is_file()
        }
        self.assertEqual(
            after,
            before,
        )

    def test_output_cannot_replace_or_live_inside_source(self):
        package = self._create_package()
        with self.assertRaises(
            ProtectionError
        ):
            protect_path(
                package,
                package.parent,
                "secret",
                force=True,
            )

        with self.assertRaises(
            ProtectionError
        ):
            protect_path(
                package,
                package / "build",
                "secret",
            )


if __name__ == "__main__":
    unittest.main()
