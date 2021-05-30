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
import subprocess
import sys

__all__ = ['memory_of_this', 'memory_usage', 'run_on_terminal']


def memory_of_this(obj):
    return sys.getsizeof(obj)


def memory_usage(n_most=10):
    return sorted(map(lambda x: (x[0], sys.getsizeof(x[1])), globals().items()), key=lambda x: x[1], reverse=True)[
           :n_most]


def run_on_terminal(cmd: str):
    try:
        result = subprocess.run(
                cmd,
                shell=True, stdout=subprocess.PIPE)
        result.check_returncode()
        return result.stdout
    except subprocess.CalledProcessError as err:
        err_output = err.output.decode()
        raise Exception(f"{err}:{err_output}")
    except Exception as err:
        raise Exception(err)