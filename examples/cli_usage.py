#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Call the JSON CLI without shell quoting or installing a console executable."""

import json
import subprocess
import sys
from .common import catalogue, show


def run():
    salt = catalogue()['Potassium Nitrate']
    request = dict(
        salts=[salt],
        targets={'K': 100, 'N_NO3': 100 * salt['elements']['N_NO3'] / salt['elements']['K']},
        water={},
    )
    completed = subprocess.run(
        [sys.executable, '-m', 'flahax'],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        check=True,
    )
    return dict(
        assumptions=[
            'CLI formulation only; no hardware or external service calls.',
            'The source checkout must be on PYTHONPATH.',
        ],
        request=request,
        response=json.loads(completed.stdout),
    )


if __name__ == '__main__':
    show(run())
