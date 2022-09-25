"""
Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import functools
import os
import subprocess
from datetime import datetime
from typing import Union

from cereja.config.cj_types import PEP440

__all__ = ["get_version", "latest_git", "get_version_pep440_compliant"]


def get_version(version: Union[str, PEP440] = None) -> PEP440:
    """
    Dotted version of the string type is expected
    e.g:
    '1.0.3.a.3' # Pep440 see https://www.python.org/dev/peps/pep-0440/
    :param version: Dotted version of the string
    """
    if version is None:
        from cereja import VERSION as version

    if isinstance(version, str):
        version = version.split(".")
        version_note = version.pop(3)
        version = list(map(int, version))
        version.insert(3, version_note)

    assert len(version) == 5, "Version must be size 5"

    assert version[3] in ("alpha", "beta", "rc", "final")
    return version


@functools.lru_cache()
def latest_git():
    """
    Return a numeric identifier of the latest git changeset.
    """
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_log = subprocess.run(
            ["git", "log", "--pretty=format:%ct", "--quiet", "-1", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            cwd=repo_dir,
            universal_newlines=True,
    )
    timestamp = git_log.stdout
    try:
        timestamp = datetime.utcfromtimestamp(int(timestamp))
    except ValueError:
        return None
    return timestamp.strftime("%Y%m%d%H%M%S")


def get_version_pep440_compliant(version: str = None) -> str:
    """
    Dotted version of the string type is expected
    e.g:
    '1.0.3.a.3' # Pep440 see https://www.python.org/dev/peps/pep-0440/
    :param version: Dotted version of the string
    """
    version_mapping = {"alpha": "a", "beta": "b", "rc": "rc"}
    version = get_version(version)
    root_version = ".".join(map(str, version[:3]))

    sub = ""
    if version[3] == "alpha" and version[4] == 0:
        git = latest_git()
        if git:
            sub = f".dev{git}"

    elif version[3] != "final":
        sub = version_mapping[version[3]] + str(version[4])
    elif version[3] == "final" and version[4] != 0:
        sub = f"-{version[4]}"

    return f"{root_version}{sub}"
