# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Small independent contract oracles, with no production chemistry imports.

These establish inventory and reporting invariants, not physical model accuracy.
The model-limitations record is a proposed acceptance contract, not an existing
runtime capability: explicit refusal is also allowed by the regression control.
"""

from collections.abc import Mapping
from fractions import Fraction


def carbon_free_phosphate_witness(alkalinity):
    """Construct a nonnegative proton-inventory witness on an H2PO4 reference.

    HPO4 contributes one equivalent relative to H2PO4, OH contributes one and H
    subtracts one. This is a prescribed species inventory, not an equilibrium
    calculation or a claim about activity coefficients at a specified pH.
    """
    total = Fraction('0.001')
    hydrogen, hydroxide = Fraction('1e-8'), Fraction('1e-6')
    hpo4 = Fraction(str(alkalinity)) - hydroxide + hydrogen
    h2po4 = total - hpo4
    if not 0 <= hpo4 <= total:
        raise ValueError('alkalinity is outside this prescribed inventory')
    sodium = h2po4 + 2 * hpo4 + hydroxide - hydrogen
    return dict(H2PO4=h2po4, HPO4=hpo4, H=hydrogen, OH=hydroxide, Na=sodium, C=Fraction(0))


def competition_is_explicitly_qualified(result, components):
    """Require a machine-readable limitation for this exact missing competition.

    A generic disclaimer, an unrelated component, or a numerical result alone
    does not qualify the omitted pair. Additional limitations are permitted.
    """
    records = getattr(result, 'model_limitations', ())
    if not isinstance(records, (list, tuple)):
        return False
    for record in records:
        if not isinstance(record, Mapping) or record.get('code') != 'omitted_competition':
            continue
        names = record.get('components', ())
        if isinstance(names, (list, tuple)) and set(components).issubset(names):
            return True
    return False
