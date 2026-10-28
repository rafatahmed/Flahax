#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Reproduce phosphate fitting with Decimal QR and independent coefficient transcription.

Shares the aqueous speciation model, but neither the production normal-equation
solver nor its design-row/equation implementation. This verifies numerical fitting,
not independent chemistry or measured fertilizer-mixture accuracy. No files are edited.
"""

from decimal import Decimal, localcontext
import json
from pathlib import Path

from flahax.calculated_ph import calculate_equilibrium_ph

FIXTURES = Path(__file__).resolve().parents[1] / 'tests/fixtures/conductivity'


def phosphate_refit():
    """Return four fitted coefficients from a 50-digit QR least-squares calculation."""
    fixture = json.loads((FIXTURES / 'pethybridge2006_table3_independent.json').read_text())
    table = json.loads((FIXTURES / 'mccleskey2012_table1_independent.json').read_text())['ions']
    # The reference fixture uses conductivity ion names for these non-fitted species.
    rows, targets = [], []
    with localcontext() as ctx:
        ctx.prec = 50

        def d(value):
            return Decimal(str(value))

        for salt, divisor in (('KH2PO4', 1), ('K2HPO4_half', 2)):
            for concentration, molar in fixture[salt]:
                m = d(concentration) / 1000 / d('0.997047')
                state = calculate_equilibrium_ph(
                    {'K+': float(m), 'PO4-3': float(m / divisor)},
                    complete_analysis=True,
                    carbon_boundary='closed',
                    phases=[],
                )
                root = d(state.ionic_strength).sqrt()
                damp = root / (1 + d('1.5') * root)
                observed = d(concentration) * d(molar) / 1000
                known = Decimal(0)
                for ion in ('K+', 'H+', 'OH-'):
                    row = table[ion]

                    def polynomial(values):
                        return sum(d(v) * Decimal(25) ** (2 - i) for i, v in enumerate(values))

                    value = polynomial(row['lambda0']) - polynomial(row['A']) * root / (
                        1 + d(row['B']) * root
                    )
                    known += value * d(state.species.get(ion, 0))
                row = []
                for ion in ('H2PO4-', 'HPO4-2'):
                    amount = d(state.species.get(ion, 0))
                    row.extend((amount / observed, -amount * damp / observed))
                rows.append(row)
                targets.append((observed - known) / observed)
        # Modified Gram-Schmidt, without forming A-transpose A.
        columns = [list(column) for column in zip(*rows)]
        q, r = [], [[Decimal(0)] * 4 for _ in range(4)]
        for j, column in enumerate(columns):
            v = column[:]
            for i in range(j):
                r[i][j] = sum(a * b for a, b in zip(q[i], v))
                v = [a - r[i][j] * b for a, b in zip(v, q[i])]
            r[j][j] = sum(a * a for a in v).sqrt()
            q.append([a / r[j][j] for a in v])
        rhs = [sum(a * b for a, b in zip(column, targets)) for column in q]
        x = [Decimal(0)] * 4
        for i in reversed(range(4)):
            x[i] = (rhs[i] - sum(r[i][j] * x[j] for j in range(i + 1, 4))) / r[i][i]
        return [float(value) for value in x]


def withheld_kcl():
    """Report reference differences; no empirical acceptance tolerance is invented."""
    from flahax.irrigation_ec import calculate_ec_from_totals, ionic_molal_conductivity

    fixture = json.loads((FIXTURES / 'iupac2001_kcl_table1.json').read_text())
    results = []
    for point in fixture['kcl']:
        m = point['molality']
        result = calculate_ec_from_totals(
            {'K+': m, 'Cl-': m},
            solution_id='withheld-kcl',
            ph_mode='calculated',
            phase_policy='dissolved',
        )
        # Algebraic Table 1 check, distinct from a qualified public mixture result.
        algebraic = m * sum(ionic_molal_conductivity(ion, m) for ion in ('K+', 'Cl-'))
        results.append(
            {
                **point,
                'table1_ms_cm': algebraic,
                'table1_gap_percent': 100 * (algebraic * 1000 / point['kappa'] - 1),
                'public_status': result.status,
                'public_reason': result.reason,
                'public_ec25_ms_cm': result.ec25_ms_cm,
            }
        )
    return results


if __name__ == '__main__':
    print(
        json.dumps(
            {
                'method': '50-digit Decimal QR',
                'coefficients': phosphate_refit(),
                'withheld_kcl': withheld_kcl(),
            },
            indent=2,
        )
    )
