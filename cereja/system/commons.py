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
        subprocess.run(
                cmd,
                shell=True, stdout=subprocess.PIPE).check_returncode()
    except subprocess.CalledProcessError as err:
        err_output = err.output.decode()
        raise Exception(f"{err}:{err_output}")
    except Exception as err:
        raise Exception(err)
