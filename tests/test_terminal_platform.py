# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Native console witnesses and controlled terminal lifecycle regressions (#182)."""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from flahax.terminal import Terminal, ENTER_SCREEN, LEAVE_SCREEN, supported
from tests.test_terminal import RecordingTerminal


class LifecycleTests(unittest.TestCase):
    def test_eof_terminates_without_repeated_empty_reads(self):
        selector = types.SimpleNamespace(select=lambda *args: ([0], [], []))
        with (
            patch('flahax.terminal.os.name', 'posix'),
            patch('sys.stdin', types.SimpleNamespace(fileno=lambda: 0)),
            patch.dict('sys.modules', {'select': selector}),
            patch('flahax.terminal.os.read', return_value=b'') as read,
        ):
            with self.assertRaises(EOFError):
                Terminal(io.StringIO()).read_key()
            read.assert_called_once_with(0, 64)

    def test_buffered_input_is_delivered_before_eof(self):
        selector = types.SimpleNamespace(select=lambda *args: ([0], [], []))
        with (
            patch('flahax.terminal.os.name', 'posix'),
            patch('sys.stdin', types.SimpleNamespace(fileno=lambda: 0)),
            patch.dict('sys.modules', {'select': selector}),
            patch('flahax.terminal.os.read', side_effect=[b'ab', b'', b'']),
        ):
            term = Terminal(io.StringIO())
            self.assertEqual(term.read_key(), 'a')
            self.assertEqual(term.read_key(), 'b')
            with self.assertRaises(EOFError):
                term.read_key()

    def test_partial_screen_entry_flush_failure_cleans_screen_and_mode(self):
        class FailOnce(io.StringIO):
            calls = 0

            def flush(self):
                self.calls += 1
                if self.calls == 1:
                    raise OSError('entry flush')

        term = RecordingTerminal()
        term.stream = FailOnce()
        with self.assertRaisesRegex(OSError, 'entry flush'):
            term.__enter__()
        self.assertEqual(term.stream.getvalue(), ENTER_SCREEN + LEAVE_SCREEN)
        self.assertEqual(term.modes, ['on', 'off'])
        self.assertIsNone(term._restore)

    def test_entry_error_is_not_replaced_by_cleanup_failure(self):
        class Broken(io.StringIO):
            def write(self, value):
                raise OSError('entry write')

        term = RecordingTerminal()
        term.stream = Broken()
        with self.assertRaisesRegex(OSError, 'entry write'):
            term.__enter__()
        self.assertEqual(term.modes, ['on', 'off'])

    def test_exit_flush_failure_still_restores_mode(self):
        term = RecordingTerminal()
        term.__enter__()
        with patch.object(term.stream, 'flush', side_effect=OSError('exit flush')):
            with self.assertRaisesRegex(OSError, 'exit flush'):
                term.__exit__()
        self.assertEqual(term.modes, ['on', 'off'])
        self.assertIsNone(term._restore)

    def test_restore_callback_is_cleared_even_if_it_fails(self):
        term = Terminal(io.StringIO())
        with patch.object(term, '_restore', side_effect=OSError('restore')) as restore:
            with self.assertRaisesRegex(OSError, 'restore'):
                term.__exit__()
            self.assertIsNone(term._restore)
            term.__exit__()
            restore.assert_called_once()

    def test_posix_timeout_and_multichunk_unicode(self):
        selector = types.SimpleNamespace(select=lambda *args: ([], [], []))
        with (
            patch('flahax.terminal.os.name', 'posix'),
            patch('sys.stdin', types.SimpleNamespace(fileno=lambda: 0)),
            patch.dict('sys.modules', {'select': selector}),
        ):
            term = Terminal(io.StringIO())
            self.assertIsNone(term.read_key(0))
            selector.select = unittest.mock.Mock(side_effect=[([0], [], [])] * 3 + [([], [], [])])
            with patch('flahax.terminal.os.read', side_effect=[b'\x1b', b'[A', 'م'.encode()]):
                self.assertEqual(term.read_key(), 'UP')
                self.assertEqual(term.read_key(), 'م')


class PlatformInterfaceTests(unittest.TestCase):
    def test_posix_mode_capture_restore_and_unavailable_stream(self):
        attributes = [1, 2, 3, 4, 5, 6, []]
        termios = types.SimpleNamespace(
            tcgetattr=unittest.mock.Mock(return_value=attributes),
            tcsetattr=unittest.mock.Mock(),
            error=RuntimeError,
            TCSADRAIN=1,
        )
        tty = types.SimpleNamespace(setcbreak=unittest.mock.Mock())
        stream = types.SimpleNamespace(isatty=lambda: True, fileno=lambda: 7)
        with (
            patch('flahax.terminal.os.name', 'posix'),
            patch('sys.stdin', stream),
            patch.dict('sys.modules', {'termios': termios, 'tty': tty}),
        ):
            self.assertTrue(supported(stream, stream))
            with Terminal(io.StringIO()):
                tty.setcbreak.assert_called_once_with(7)
            termios.tcsetattr.assert_called_once_with(7, 1, attributes)
            termios.tcgetattr.side_effect = OSError('closed descriptor')
            self.assertFalse(supported(stream, stream))

    def test_posix_distinct_mode_errors_probe_setup_rollback_and_restore(self):
        from flahax.terminal import TerminalUnavailable

        class ModeError(Exception):
            pass

        termios = types.SimpleNamespace(
            error=ModeError,
            TCSADRAIN=1,
            tcgetattr=unittest.mock.Mock(return_value=['old']),
            tcsetattr=unittest.mock.Mock(),
        )
        tty = types.SimpleNamespace(setcbreak=unittest.mock.Mock())
        stream = types.SimpleNamespace(isatty=lambda: True, fileno=lambda: 7)
        with (
            patch('flahax.terminal.os.name', 'posix'),
            patch('sys.stdin', stream),
            patch.dict('sys.modules', {'termios': termios, 'tty': tty}),
        ):
            termios.tcgetattr.side_effect = ModeError('get')
            self.assertFalse(supported(stream, stream))
            with self.assertRaisesRegex(TerminalUnavailable, 'cannot read terminal mode'):
                Terminal(io.StringIO()).__enter__()
            termios.tcgetattr.side_effect = None
            tty.setcbreak.side_effect = ModeError('set')
            for rollback in (None, ModeError('rollback')):
                termios.tcsetattr.side_effect = rollback
                with self.assertRaisesRegex(TerminalUnavailable, 'cannot enable') as raised:
                    Terminal(io.StringIO()).__enter__()
                self.assertEqual(str(raised.exception.__cause__), 'set')
            self.assertEqual(termios.tcsetattr.call_count, 2)
            tty.setcbreak.side_effect = None
            term = Terminal(io.StringIO())
            term.__enter__()
            with self.assertRaisesRegex(OSError, 'cannot restore'):
                term.__exit__()
            self.assertIsNone(term._restore)

    def test_windows_console_mode_failures_are_explicit(self):
        # Import under the real OS before simulating the Windows adapter branch.
        import ctypes.wintypes  # noqa: F401
        from flahax.terminal import TerminalUnavailable

        kernel = types.SimpleNamespace(
            GetStdHandle=lambda _: 1,
            GetConsoleMode=unittest.mock.Mock(return_value=False),
            SetConsoleMode=unittest.mock.Mock(return_value=False),
        )
        with (
            patch('flahax.terminal.os.name', 'nt'),
            patch('flahax.terminal._kernel32', return_value=kernel),
        ):
            with self.assertRaisesRegex(TerminalUnavailable, 'not a console'):
                Terminal(io.StringIO()).__enter__()
            kernel.GetConsoleMode.return_value = True
            with self.assertRaisesRegex(TerminalUnavailable, 'cannot switch on ANSI'):
                Terminal(io.StringIO()).__enter__()

    def test_windows_poll_timeout_yields_without_input(self):
        keys = types.SimpleNamespace(kbhit=lambda: False)
        with (
            patch('flahax.terminal.os.name', 'nt'),
            patch.dict('sys.modules', {'msvcrt': keys}),
            patch('flahax.terminal.time.monotonic', side_effect=[0, 0.01, 0.2]),
            patch('flahax.terminal.time.sleep') as sleep,
        ):
            self.assertIsNone(Terminal(io.StringIO()).read_key(0.1))
            sleep.assert_called_once_with(0.01)

    def test_unicode_unknown_escape_resize_and_cursor(self):
        from flahax.terminal import decode_posix

        self.assertEqual(decode_posix('中🙂'.encode()), ['中', '🙂'])
        self.assertEqual(decode_posix(b'\x1b[99~'), ['OTHER'])
        self.assertEqual(decode_posix(b'\x1b['), ['OTHER'])
        term = Terminal(io.StringIO())
        with patch('flahax.terminal.shutil.get_terminal_size', side_effect=[(80, 24), (40, 10)]):
            self.assertEqual(term.size(), (80, 24))
            self.assertEqual(term.size(), (40, 10))
        term.show_cursor(True)
        term.show_cursor(False)
        self.assertEqual(term.stream.getvalue(), '\x1b[?25h\x1b[?25l')


class NativePlatformTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'requires a native Windows console')
    def test_hidden_windows_console_keyboard_mode_and_restore(self):
        result = subprocess.run(
            [sys.executable, '-m', 'tests.test_terminal_platform', '--windows-console-child'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=20,
            cwd=Path(__file__).resolve().parents[1],
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['platform'], 'native_windows_console')

    @unittest.skipUnless(os.name == 'posix', 'requires native termios')
    def test_posix_real_pipe_is_unavailable_without_raw_termios_error(self):
        from flahax.terminal import TerminalUnavailable

        read_fd, write_fd = os.pipe()
        stream = types.SimpleNamespace(isatty=lambda: True, fileno=lambda: read_fd)
        try:
            self.assertFalse(supported(stream, stream))
            with patch('sys.stdin', stream):
                with self.assertRaises(TerminalUnavailable):
                    Terminal(io.StringIO()).__enter__()
        finally:
            os.close(read_fd)
            os.close(write_fd)

    @unittest.skipUnless(os.name == 'posix', 'requires a native POSIX PTY')
    def test_posix_pty_keyboard_cbreak_and_restore(self):
        result = subprocess.run(
            [sys.executable, '-m', 'tests.test_terminal_platform', '--posix-pty-child'],
            capture_output=True,
            text=True,
            start_new_session=True,
            timeout=20,
            cwd=Path(__file__).resolve().parents[1],
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['platform'], sys.platform)


def assert_restored_termios(case, before, after, platform, pendin):
    """Compare configuration, allowing only Darwin's kernel-owned pending-input bit."""
    expected, actual = list(before), list(after)
    if platform == 'darwin':
        # XNU tty.c sets PENDIN when ICANON is restored, even for an empty queue.
        # Do not flush input or change production cleanup to satisfy this witness.
        expected[3] &= ~pendin
        actual[3] &= ~pendin
    case.assertEqual(actual, expected)


class TermiosRestorationWitnessTests(unittest.TestCase):
    def test_darwin_pending_input_is_the_only_allowed_difference(self):
        before = [11010, 3, 19200, 1483, 9600, 9600, [b'\x04']]
        after = list(before)
        pendin = 0x20000000  # Darwin termios.h; matches the hosted failure.
        after[3] |= pendin
        self.assertNotEqual(before, after)
        assert_restored_termios(self, before, after, 'darwin', pendin)
        for platform in ('linux', 'cygwin'):
            with self.subTest(platform=platform), self.assertRaises(AssertionError):
                assert_restored_termios(self, before, after, platform, pendin)
        for index, value in (
            (0, 0),
            (1, 0),
            (2, 0),
            (3, after[3] ^ 2),
            (3, after[3] ^ 8),
            (4, 4800),
            (5, 4800),
            (6, [b'X']),
        ):
            changed = list(after)
            changed[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(AssertionError):
                assert_restored_termios(self, before, changed, 'darwin', pendin)
        self.assertEqual(before[3], 1483)
        self.assertEqual(after[3], 536872395)
        assert_restored_termios(self, before, before, 'linux', pendin)


def posix_pty_witness():
    """Exercise a real PTY in an isolated session, ignoring its teardown hangup."""
    import signal

    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    case = unittest.TestCase()
    import pty
    import termios

    master, slave = pty.openpty()
    try:
        before = termios.tcgetattr(slave)
        with os.fdopen(os.dup(slave), 'r') as stdin:
            with os.fdopen(os.dup(slave), 'w') as stdout:
                case.assertTrue(supported(stdin, stdout))
            with patch('sys.stdin', stdin):
                with case.assertRaisesRegex(RuntimeError, 'restore witness'):
                    with Terminal(io.StringIO()) as term:
                        case.assertFalse(termios.tcgetattr(slave)[3] & termios.ICANON)
                        case.assertIsNone(term.read_key(0))
                        os.write(master, b'\x1b[A' + 'م'.encode())
                        case.assertEqual(term.read_key(), 'UP')
                        case.assertEqual(term.read_key(), 'م')
                        raise RuntimeError('restore witness')
        assert_restored_termios(
            case, before, termios.tcgetattr(slave), sys.platform, getattr(termios, 'PENDIN', 0)
        )
    finally:
        os.close(master)
        os.close(slave)
    print(
        json.dumps(
            dict(
                platform=sys.platform,
                unicode_key=True,
                arrow_key=True,
                cbreak_mode=True,
                exception_restore=True,
            )
        )
    )


def windows_console_witness():
    """Exercise real Win32 console handles in an isolated hidden child console."""
    import ctypes
    from ctypes import wintypes
    from flahax.terminal import _kernel32

    kernel = _kernel32()
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.SetStdHandle.argtypes = [wintypes.DWORD, wintypes.HANDLE]
    kernel.SetStdHandle.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handles = [
        kernel.CreateFileW(name, 0xC0000000, 3, None, 3, 0, None) for name in ('CONIN$', 'CONOUT$')
    ]
    assert all(handle not in (None, ctypes.c_void_p(-1).value) for handle in handles)
    old_handles = [kernel.GetStdHandle(n & 0xFFFFFFFF) for n in (-10, -11)]
    try:
        for number, handle in zip((-10, -11), handles):
            assert kernel.SetStdHandle(number & 0xFFFFFFFF, handle)
        mode = wintypes.DWORD()
        assert kernel.GetConsoleMode(handles[1], ctypes.byref(mode))
        before = mode.value

        class Key(ctypes.Structure):
            _fields_ = [
                ('down', wintypes.BOOL),
                ('repeat', wintypes.WORD),
                ('virtual', wintypes.WORD),
                ('scan', wintypes.WORD),
                ('char', wintypes.WCHAR),
                ('state', wintypes.DWORD),
            ]

        class Event(ctypes.Union):
            _fields_ = [('key', Key), ('padding', ctypes.c_byte * 16)]

        class Input(ctypes.Structure):
            _fields_ = [('kind', wintypes.WORD), ('event', Event)]

        kernel.WriteConsoleInputW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Input),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel.WriteConsoleInputW.restype = wintypes.BOOL
        with (
            open('CONIN$', encoding='utf-8') as cin,
            open('CONOUT$', 'w', encoding='utf-8') as cout,
        ):
            assert supported(cin, cout)
            try:
                with Terminal(cout) as term:
                    assert kernel.GetConsoleMode(handles[1], ctypes.byref(mode))
                    assert mode.value & 4
                    assert term.read_key(0) is None
                    event = Input(1, Event(key=Key(True, 1, 0, 0, 'م', 0)))
                    written = wintypes.DWORD()
                    assert kernel.WriteConsoleInputW(
                        handles[0], ctypes.byref(event), 1, ctypes.byref(written)
                    )
                    assert written.value == 1
                    assert term.read_key(0.5) == 'م'
                    term.draw(['native console restore witness'])
                    raise RuntimeError('restore witness')
            except RuntimeError as exc:
                assert str(exc) == 'restore witness'
        assert kernel.GetConsoleMode(handles[1], ctypes.byref(mode))
        assert mode.value == before
        print(
            json.dumps(
                dict(
                    platform='native_windows_console',
                    unicode_key=True,
                    ansi_mode=True,
                    exception_restore=True,
                )
            )
        )
    finally:
        for number, handle in zip((-10, -11), old_handles):
            kernel.SetStdHandle(number & 0xFFFFFFFF, handle)
        for handle in handles:
            kernel.CloseHandle(handle)


if __name__ == '__main__':
    if sys.argv[1:] == ['--windows-console-child']:
        windows_console_witness()
    elif sys.argv[1:] == ['--posix-pty-child']:
        posix_pty_witness()
    else:
        unittest.main()
