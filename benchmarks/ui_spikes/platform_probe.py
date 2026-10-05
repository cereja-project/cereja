"""Noninteractive wakeup probe; never changes terminal modes or reads input."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import selectors
import socket
import sys
import threading
import time


def probe():
    report = {'os': platform.system(), 'python': platform.python_version(),
              'stdin_tty': sys.stdin.isatty(), 'stdout_tty': sys.stdout.isatty(),
              'terminal_mode_changes': 0, 'input_reads': 0}
    left, right = socket.socketpair()
    with left, right, selectors.DefaultSelector() as selector:
        selector.register(left, selectors.EVENT_READ)
        report['selector'] = type(selector).__name__
        start = time.perf_counter_ns()
        report['idle_ready'] = len(selector.select(.02))
        report['idle_wait_ns'] = time.perf_counter_ns() - start
        worker = threading.Thread(target=lambda: right.send(b'x'))
        worker.start()
        report['posted_ready'] = len(selector.select(1))
        report['posted_payload'] = left.recv(1).decode()
        worker.join(1)
    if os.name == 'nt':
        from ctypes import wintypes as w
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateEventW.argtypes = [ctypes.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR]
        kernel.CreateEventW.restype = w.HANDLE
        kernel.SetEvent.argtypes = [w.HANDLE]
        kernel.SetEvent.restype = w.BOOL
        kernel.ResetEvent.argtypes = [w.HANDLE]
        kernel.ResetEvent.restype = w.BOOL
        kernel.WaitForMultipleObjects.argtypes = [w.DWORD, ctypes.POINTER(w.HANDLE), w.BOOL, w.DWORD]
        kernel.WaitForMultipleObjects.restype = w.DWORD
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.CloseHandle.restype = w.BOOL
        kernel.GetStdHandle.argtypes = [w.DWORD]
        kernel.GetStdHandle.restype = w.HANDLE
        kernel.GetConsoleMode.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        kernel.GetConsoleMode.restype = w.BOOL
        handles = [kernel.CreateEventW(None, True, False, None) for _ in range(2)]
        if not all(handles):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            array = (w.HANDLE * 2)(*handles)
            timeout = kernel.WaitForMultipleObjects(2, array, False, 20)
            worker = threading.Thread(target=lambda: kernel.SetEvent(handles[1]))
            worker.start()
            woke = kernel.WaitForMultipleObjects(2, array, False, 1000)
            worker.join(1)
            assert kernel.ResetEvent(handles[1])
            reset = kernel.WaitForMultipleObjects(2, array, False, 0)
            report['win32_event'] = {'idle_result': timeout, 'wakeup_index': woke,
                                     'reset_result': reset}
            assert (timeout, woke, reset) == (258, 1, 258)
            mode = w.DWORD()
            report['console_input_available'] = bool(kernel.GetConsoleMode(
                kernel.GetStdHandle(w.DWORD(-10).value), ctypes.byref(mode)))
        finally:
            for handle in handles:
                kernel.CloseHandle(handle)
    report['posix_pty'] = 'not run on Windows' if os.name == 'nt' else 'not exercised by this probe'
    assert report['idle_ready'] == 0 and report['posted_ready'] == 1
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(probe(), indent=2) + '\n', encoding='utf-8')
