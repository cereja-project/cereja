"""Headless native ConPTY fixture for the official Ledger entry and VT input."""
import ctypes as C
from pathlib import Path
import subprocess
import sys
import time

from cereja.ui._win32 import BOOL, COORD, DWORD, HANDLE, WORD


class StartupInfo(C.Structure):
    _fields_ = [('cb', DWORD), ('lpReserved', C.c_wchar_p), ('lpDesktop', C.c_wchar_p),
                ('lpTitle', C.c_wchar_p), ('dwX', DWORD), ('dwY', DWORD), ('dwXSize', DWORD),
                ('dwYSize', DWORD), ('dwXCountChars', DWORD), ('dwYCountChars', DWORD),
                ('dwFillAttribute', DWORD), ('dwFlags', DWORD), ('wShowWindow', WORD),
                ('cbReserved2', WORD), ('lpReserved2', C.c_void_p), ('hStdInput', HANDLE),
                ('hStdOutput', HANDLE), ('hStdError', HANDLE)]


class StartupInfoEx(C.Structure):
    _fields_ = [('StartupInfo', StartupInfo), ('lpAttributeList', C.c_void_p)]


class ProcessInfo(C.Structure):
    _fields_ = [('hProcess', HANDLE), ('hThread', HANDLE), ('dwProcessId', DWORD), ('dwThreadId', DWORD)]


CHILD = r'''
import os, sys
from unittest.mock import patch
from cereja.commands.ui import main
from cereja.tui.app import TUI
from cereja.ui._win32 import Win32API
from cereja.ui.events import KeyEvent, PasteEvent
# The test runner can have redirected standard handles. Bind this child's own
# pseudoconsole devices, as the existing hidden-console probe also does.
sys.stdin = open('CONIN$', 'r', encoding='utf-8')
sys.stdout = sys.stderr = open('CONOUT$', 'w', encoding='utf-8', buffering=1)
os.environ['TERM'] = 'xterm-256color'
api = Win32API()
handles = api.stream_handle(sys.stdin), api.stream_handle(sys.stdout)
before = tuple(api.get_mode(h) for h in handles)
assert sys.stdin.isatty() and sys.stdout.isatty(), (before, sys.stdin, sys.stdout)
seen = []
copies = []
original_run, original_handle = TUI.run, TUI.handle
def run(app):
    assert app.session.capabilities.paste
    assert api.get_mode(handles[0]) & 0x200
    return original_run(app)
def handle(app, event):
    had_selection = app.composer.selection is not None
    answer = original_handle(app, event)
    if isinstance(event, PasteEvent):
        assert app.composer.text == event.text
        assert len(app.results.blocks) == 1
        assert not app.bridge.active
        seen.append(event.text)
    if had_selection and isinstance(event, KeyEvent) and event.key == 'c' and event.modifiers == {'ctrl'}:
        if app.notice.startswith('Copy unavailable'):
            copies.append(True)
            assert not app.loop.stopped
    return answer
with patch.object(TUI, 'run', run), patch.object(TUI, 'handle', handle):
    assert main(['--bracketed-paste', '--ascii', '--no-color', '--reduced-motion']) == 0
after = tuple(api.get_mode(h) for h in handles)
assert before == after, (before, after)
assert seen == ['/examples progress\n/home e\u0301界😀'], seen
assert copies == [True], copies
print('LEDGER_NATIVE_REPORT:OK')
'''


def probe():
    """Inject host-side VT bytes into a real pseudoconsole, without a visible window."""
    dll = C.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreatePipe': ([C.POINTER(HANDLE), C.POINTER(HANDLE), C.c_void_p, DWORD], BOOL),
        'CreatePseudoConsole': ([COORD, HANDLE, HANDLE, DWORD, C.POINTER(HANDLE)], C.c_int32),
        'ClosePseudoConsole': ([HANDLE], None),
        'InitializeProcThreadAttributeList': ([C.c_void_p, DWORD, DWORD, C.POINTER(C.c_size_t)], BOOL),
        'UpdateProcThreadAttribute': ([C.c_void_p, DWORD, C.c_size_t, C.c_void_p, C.c_size_t,
                                      C.c_void_p, C.c_void_p], BOOL),
        'DeleteProcThreadAttributeList': ([C.c_void_p], None),
        'CreateProcessW': ([C.c_wchar_p, C.c_wchar_p, C.c_void_p, C.c_void_p, BOOL, DWORD,
                            C.c_void_p, C.c_wchar_p, C.POINTER(StartupInfoEx), C.POINTER(ProcessInfo)], BOOL),
        'PeekNamedPipe': ([HANDLE, C.c_void_p, DWORD, C.c_void_p, C.POINTER(DWORD), C.c_void_p], BOOL),
        'ReadFile': ([HANDLE, C.c_void_p, DWORD, C.POINTER(DWORD), C.c_void_p], BOOL),
        'WriteFile': ([HANDLE, C.c_void_p, DWORD, C.POINTER(DWORD), C.c_void_p], BOOL),
        'WaitForSingleObject': ([HANDLE, DWORD], DWORD),
        'GetExitCodeProcess': ([HANDLE, C.POINTER(DWORD)], BOOL),
        'TerminateProcess': ([HANDLE, DWORD], BOOL),
        'CloseHandle': ([HANDLE], BOOL),
    }
    for name, (args, result) in signatures.items():
        getattr(dll, name).argtypes, getattr(dll, name).restype = args, result
    def checked(ok):
        if not ok:
            raise C.WinError(C.get_last_error())
    pipe_in, writer, reader, pipe_out, console = (HANDLE() for _ in range(5))
    process = ProcessInfo()
    attributes = None
    attributes_initialized = False
    try:
        checked(dll.CreatePipe(C.byref(pipe_in), C.byref(writer), None, 65536))
        checked(dll.CreatePipe(C.byref(reader), C.byref(pipe_out), None, 65536))
        hr = dll.CreatePseudoConsole(COORD(80, 24), pipe_in, pipe_out, 0, C.byref(console))
        if hr != 0:
            raise OSError('CreatePseudoConsole failed', hex(hr & 0xffffffff))
        size = C.c_size_t()
        dll.InitializeProcThreadAttributeList(None, 1, 0, C.byref(size))
        attributes = C.create_string_buffer(size.value)
        checked(dll.InitializeProcThreadAttributeList(attributes, 1, 0, C.byref(size)))
        attributes_initialized = True
        checked(dll.UpdateProcThreadAttribute(attributes, 0, 0x20016, console, C.sizeof(HANDLE), None, None))
        startup = StartupInfoEx()
        startup.StartupInfo.cb = C.sizeof(startup)
        startup.lpAttributeList = C.cast(attributes, C.c_void_p)
        command = C.create_unicode_buffer(subprocess.list2cmdline([sys.executable, '-B', '-S', '-c', CHILD]))
        checked(dll.CreateProcessW(sys.executable, command, None, None, False, 0x80000,
                                   None, str(Path(__file__).resolve().parents[1]), C.byref(startup), C.byref(process)))
        for handle in (pipe_in, pipe_out):
            checked(dll.CloseHandle(handle))
            handle.value = None
        received = bytearray()
        def read_available():
            available = DWORD()
            checked(dll.PeekNamedPipe(reader, None, 0, None, C.byref(available), None))
            if available.value:
                buffer = C.create_string_buffer(min(available.value, 65536))
                count = DWORD()
                checked(dll.ReadFile(reader, buffer, len(buffer), C.byref(count), None))
                received.extend(buffer.raw[:count.value])
                if len(received) > 1024 * 1024:
                    raise AssertionError('native output exceeded fixture bound')
        def until(marker):
            deadline = time.monotonic() + 10
            while marker not in received and time.monotonic() < deadline:
                read_available()
                time.sleep(.01)
            if marker not in received:
                raise AssertionError('missing native marker: ' + repr(marker) + '\n' + received.decode('utf-8', 'replace'))
        def send(data):
            count = DWORD()
            checked(dll.WriteFile(writer, data, len(data), C.byref(count), None))
            if count.value != len(data):
                raise AssertionError('incomplete fixture input')
        until(b'Cereja TUI')
        if b'\x1b[?2004h' not in received:
            raise AssertionError('bracketed paste was not enabled')
        text = '/examples progress\n/home e\u0301界😀'
        # Host writes contain complete protocol delimiters. Record-read
        # fragmentation is covered independently by the backend tests.
        for part in (b'\x1b[200~', text.encode('utf-8'), b'\x1b[201~\x01\x03'):
            send(part)
        until(b'Copy')  # ConPTY may encode spaces as cursor-forward controls.
        if dll.WaitForSingleObject(process.hProcess, 0) != 0x102:
            raise AssertionError('copy intent exited the application')
        if b'Synthetic batches' in received:
            raise AssertionError('paste executed a command')
        send(b'\x7f\x03')
        until(b'LEDGER_NATIVE_REPORT:OK')
        # Drain while waiting: ConPTY output is a pipe, not an unbounded sink.
        deadline = time.monotonic() + 10
        while dll.WaitForSingleObject(process.hProcess, 0) == 0x102 and time.monotonic() < deadline:
            read_available()
            time.sleep(.01)
        if dll.WaitForSingleObject(process.hProcess, 0) != 0:
            raise AssertionError('native Ledger child did not exit')
        read_available()
        code = DWORD()
        checked(dll.GetExitCodeProcess(process.hProcess, C.byref(code)))
        if code.value:
            raise AssertionError('native child failed: ' + received.decode('utf-8', 'replace'))
        return {'paste_verified': True, 'modes_restored': True,
                'host': 'headless native ConPTY', 'human_clipboard_checked': False}
    finally:
        if process.hProcess and dll.WaitForSingleObject(process.hProcess, 0) == 0x102:
            # Only the failed fixture's child is terminated, never an app job.
            dll.TerminateProcess(process.hProcess, 1)
            dll.WaitForSingleObject(process.hProcess, 5000)
        if console:
            dll.ClosePseudoConsole(console)
        if attributes_initialized:
            dll.DeleteProcThreadAttributeList(attributes)
        for handle in (process.hThread, process.hProcess, pipe_in, writer, reader, pipe_out):
            if handle:
                checked(dll.CloseHandle(handle))
