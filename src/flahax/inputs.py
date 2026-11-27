# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The one place a caller-supplied number is checked, and a caller-supplied JSON
file is read.

A number is accepted when it is an ``int`` or ``float`` (never a ``bool``,
a string or ``None``) that is finite and inside the bounds the caller
declares. Nothing else blocks: a limit the model cannot guarantee is
reported with the result, never added here as a gate (ADR 0001).
"""

from __future__ import annotations

import json
import math

from .composition import InputError


class DeliveryError(InputError):
    """A delivery-planning input failure with a stable machine-readable
    code.

    ``details`` holds optional machine-readable facts about the failure, for example the stage,
    iteration count and residual of a solver that did not converge (#348).
    """

    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


def number(
    value,
    name: str,
    *,
    minimum: float | None = 0.0,
    positive: bool = False,
    maximum: float | None = None,
    code: str | None = None,
    type_code: str = "invalid_value",
) -> float:
    """Return ``value`` as a float, or raise ``DeliveryError``.

    ``minimum`` is inclusive and ``None`` allows any finite value;
    ``positive`` additionally excludes zero; ``maximum`` is inclusive.
    ``code`` replaces every failure code (a domain's own code); without
    it a missing value is ``missing_field``, a wrong type is
    ``type_code``, a non-finite value is ``invalid_value`` and a value
    outside its bounds is ``out_of_range``.
    """
    if value is None:
        raise DeliveryError(code or "missing_field", f"{name} is required")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DeliveryError(code or type_code, f"{name} must be a number")
    if not math.isfinite(value):
        raise DeliveryError(code or "invalid_value", f"{name} must be finite")
    if (
        (minimum is not None and value < minimum)
        or (positive and value <= 0)
        or (maximum is not None and value > maximum)
    ):
        raise DeliveryError(code or "out_of_range", f"{name} is outside its permitted range")
    return float(value)


def read_json(path, what):
    """A JSON file's content, or a DeliveryError that names the file and
    the line (#117).
    """
    # Imported here: only commands that read a file need pathlib (#342).
    from pathlib import Path

    try:
        text = Path(path).read_text(encoding='utf-8-sig')
    except FileNotFoundError:
        raise DeliveryError('missing_file', f'{what} file {path} was not found') from None
    except OSError as exc:
        raise DeliveryError(
            'missing_file', f'{what} file {path} cannot be read: {exc.strerror}'
        ) from None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise DeliveryError(
            'invalid_json',
            f'{what} file {path} is not valid JSON: {exc.msg.removesuffix(" at")} at line '
            f'{exc.lineno}, '
            f'column {exc.colno}',
        ) from None
