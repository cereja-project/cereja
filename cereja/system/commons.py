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
import logging
import os
import subprocess
import sys

__all__ = ["memory_of_this", "memory_usage", "run_on_terminal"]

from concurrent.futures import ThreadPoolExecutor

from typing import List

# Configuração de log para acompanhamento no Colab
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def memory_of_this(obj):
        return sys.getsizeof(obj)


def memory_usage(n_most=10):
    return sorted(
        map(lambda x: (x[0], sys.getsizeof(x[1])), globals().items()),
        key=lambda x: x[1],
        reverse=True,
    )[:n_most]


def run_on_terminal(cmd: str, get_output: bool = True) -> bytes | None:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        result.check_returncode()
        if get_output:
            return result.stdout
    except subprocess.CalledProcessError as e:
        logging.exception(f"Failed: {e.stderr.decode('utf-8')}")
        if get_output:
            return e.stderr


def run_commands_in_parallel(commands: List[str], max_workers: int = 6) -> None:
    """
    Executes a list of shell commands in parallel using a thread pool.

    Args:
        commands (List[str]): A list of commands to be executed.
        max_workers (int): Maximum number of concurrent commands.
    """

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(run_on_terminal, commands)
