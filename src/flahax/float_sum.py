# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""``float_sum``: the same float sums on every supported Python.

Python 3.12 changed the built-in ``sum`` to compensated (Neumaier)
summation for floats; 3.11 adds left to right, so the same inputs gave
results that differ in the last digits (#334). On 3.12 and later
``float_sum`` is the built-in ``sum``; on 3.11 it repeats the 3.12
algorithm step by step, so results are identical everywhere.
"""

import math
import sys


def _compensated_sum(iterable, start=0):
    """The built-in ``sum`` of Python 3.12 and later, in pure Python."""
    items = iter(iterable)
    result = start
    if type(result) is int:
        for item in items:
            if type(item) is int or type(item) is bool:
                result += item
            else:
                result = result + item
                break
        else:
            return result
    if type(result) is float:
        compensation = 0.0
        for item in items:
            if type(item) is float:
                total = result + item
                if abs(result) >= abs(item):
                    compensation += (result - total) + item
                else:
                    compensation += (item - total) + result
                result = total
            elif isinstance(item, int) and -(2**63) <= item < 2**63:
                result += float(item)
            else:
                if compensation and math.isfinite(compensation):
                    result += compensation
                result = result + item
                break
        else:
            if compensation and math.isfinite(compensation):
                result += compensation
            return result
    for item in items:
        result = result + item
    return result


float_sum = sum if sys.version_info >= (3, 12) else _compensated_sum
