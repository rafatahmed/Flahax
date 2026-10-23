# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The console for the ``flahax mix`` full-screen wizard, from the standard library only.

Windows uses ``msvcrt`` for keys and ``ctypes`` to switch on ANSI output; Linux and macOS use
``termios``, ``tty`` and ``select``. Keys come back as names: printable characters as
themselves, and UP, DOWN, LEFT, RIGHT, HOME, END, ENTER, ESC, TAB, SHIFT_TAB, BACKSPACE and
CTRL_U. Ctrl+C raises KeyboardInterrupt. The console is always restored on exit.
"""

import os
import shutil
import sys
import time

ENTER_SCREEN = '\x1b[?1049h\x1b[2J\x1b[?25l'
LEAVE_SCREEN = '\x1b[0m\x1b[?25h\x1b[?1049l'
UNICODE = {
    'h': '─',
    'v': '│',
    'tl': '┌',
    'tr': '┐',
    'bl': '└',
    'br': '┘',
    'tick': '✓',
    'here': '▸',
    'ellipsis': '…',
    'up': '↑',
    'down': '↓',
    'dot': '·',
    'deg': '°',
}
ASCII = {
    'h': '-',
    'v': '|',
    'tl': '+',
    'tr': '+',
    'bl': '+',
    'br': '+',
    'tick': '+',
    'here': '>',
    'ellipsis': '...',
    'up': '^',
    'down': 'v',
    'dot': '-',
    'deg': '',
}
WINDOWS_PREFIXED = {
    'H': 'UP',
    'P': 'DOWN',
    'K': 'LEFT',
    'M': 'RIGHT',
    'G': 'HOME',
    'O': 'END',
    '\x0f': 'SHIFT_TAB',
}
CONTROL = {
    '\r': 'ENTER',
    '\n': 'ENTER',
    '\x1b': 'ESC',
    '\t': 'TAB',
    '\x08': 'BACKSPACE',
    '\x7f': 'BACKSPACE',
    '\x15': 'CTRL_U',
}
POSIX_SEQUENCES = {
    b'\x1b[A': 'UP',
    b'\x1b[B': 'DOWN',
    b'\x1b[C': 'RIGHT',
    b'\x1b[D': 'LEFT',
    b'\x1b[H': 'HOME',
    b'\x1b[F': 'END',
    b'\x1bOA': 'UP',
    b'\x1bOB': 'DOWN',
    b'\x1bOC': 'RIGHT',
    b'\x1bOD': 'LEFT',
    b'\x1bOH': 'HOME',
    b'\x1bOF': 'END',
    b'\x1b[Z': 'SHIFT_TAB',
}


class TerminalUnavailable(OSError):
    """The console cannot be put in the full-screen mode; use the line-by-line questions."""


def _control(char):
    if char == '\x03':
        raise KeyboardInterrupt
    return CONTROL.get(char, char)


def decode_windows(chars):
    """The key named by ``msvcrt.getwch`` output (two characters for arrows and other keys)."""
    if chars[:1] in ('\x00', '\xe0'):
        return WINDOWS_PREFIXED.get(chars[1:2], 'OTHER')
    return _control(chars[:1])


def decode_posix(data):
    """The keys in raw bytes read from a POSIX terminal."""
    keys, i = [], 0
    while i < len(data):
        for sequence, name in POSIX_SEQUENCES.items():
            if data.startswith(sequence, i):
                keys.append(name)
                i += len(sequence)
                break
        else:
            if data[i] == 0x1B and i + 1 < len(data) and data[i + 1] in b'[O':
                end = i + 2
                while end < len(data) and not 0x40 <= data[end] <= 0x7E:
                    end += 1
                keys.append('OTHER')
                i = end + 1
                continue
            length = 1
            if data[i] >= 0xF0:
                length = 4
            elif data[i] >= 0xE0:
                length = 3
            elif data[i] >= 0xC0:
                length = 2
            keys.append(_control(data[i : i + length].decode('utf-8', 'replace')))
            i += length
    return keys


def glyphs(encoding):
    """Box lines, tick, marker and ellipsis the console encoding can print (else ASCII)."""
    try:
        ''.join(UNICODE.values()).encode(encoding or 'ascii')
    except (LookupError, UnicodeEncodeError):
        return dict(ASCII)
    return dict(UNICODE)


def supported(stdin=None, stdout=None):
    """True when both streams are a terminal whose mode the wizard can set."""
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    try:
        if not (stdin.isatty() and stdout.isatty()):
            return False
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes

            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetStdHandle.restype = wintypes.HANDLE
            mode = wintypes.DWORD()
            return all(
                kernel.GetConsoleMode(kernel.GetStdHandle(handle), ctypes.byref(mode))
                for handle in (-10, -11)
            )
        import termios

        termios.tcgetattr(stdin.fileno())
        return True
    except (AttributeError, OSError, ValueError, ImportError):
        return False


class Terminal:
    """The full-screen console: alternate screen, hidden cursor, keys one at a time."""

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self._restore = None
        self._pending = []

    def __enter__(self):
        self._restore = self._console_on()
        try:
            self.stream.write(ENTER_SCREEN)
            self.stream.flush()
        except BaseException:
            self._restore()
            self._restore = None
            raise
        return self

    def __exit__(self, *_):
        try:
            self.stream.write(LEAVE_SCREEN)
            self.stream.flush()
        finally:
            if self._restore is not None:
                self._restore()
                self._restore = None

    def _console_on(self):
        """Put the console in the wizard's mode; returns the function that restores it."""
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes

            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetStdHandle.restype = wintypes.HANDLE
            handle = kernel.GetStdHandle(-11)
            mode = wintypes.DWORD()
            if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                raise TerminalUnavailable('not a console')
            old = mode.value
            if not kernel.SetConsoleMode(handle, old | 0x0004):
                raise TerminalUnavailable('cannot switch on ANSI output in this console')
            return lambda: kernel.SetConsoleMode(handle, old)
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        return lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def read_key(self, timeout=0.1):
        """The next key, or None after ``timeout`` seconds without one (time to redraw)."""
        if self._pending:
            return self._pending.pop(0)
        if os.name == 'nt':
            import msvcrt

            deadline = time.monotonic() + timeout
            while not msvcrt.kbhit():
                if time.monotonic() >= deadline:
                    return None
                time.sleep(0.01)
            chars = msvcrt.getwch()
            if chars in ('\x00', '\xe0'):
                chars += msvcrt.getwch()
            return decode_windows(chars)
        import select

        fd = sys.stdin.fileno()
        if not select.select([fd], [], [], timeout)[0]:
            return None
        data = os.read(fd, 64)
        while select.select([fd], [], [], 0.02)[0] and len(data) < 1024:
            data += os.read(fd, 64)
        self._pending = decode_posix(data)
        return self._pending.pop(0) if self._pending else None

    def size(self):
        """(columns, rows) of the window."""
        return tuple(shutil.get_terminal_size((80, 24)))

    def draw(self, lines):
        """Replace the screen with these lines in one write."""
        text = '\x1b[H' + ''.join(f'\x1b[2K{line}\r\n' for line in lines) + '\x1b[J'
        encoding = getattr(self.stream, 'encoding', None)
        if encoding:
            text = text.encode(encoding, 'replace').decode(encoding)
        self.stream.write(text)
        self.stream.flush()

    def show_cursor(self, on):
        """Show or hide the text cursor."""
        self.stream.write('\x1b[?25h' if on else '\x1b[?25l')
        self.stream.flush()
