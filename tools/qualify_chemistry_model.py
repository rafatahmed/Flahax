#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Read-only qualification of pinned equations, source lines and basis transforms.

This checker does not import the model builder or solver. Exact rational atom,
charge and component balances are independent of their numerical solution.
Source-line verification is not verification of the underlying experiments.
"""

import argparse
from collections import defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
# Fully deprotonated ligands; these are chemical identities, not fitted constants.
LIGANDS = dict(
    Edta='C10H12N2O8', Citrate='C6H5O7', Dtp='C14H18N3O10', Edd='C18H16N2O6', Ure='CH4N2O'
)


def composition(name):
    """Parse atoms and formal charge, including parenthesized groups and hydrates."""
    match = re.search(r'([+-])(\d*)$', name)
    charge = (1 if match[1] == '+' else -1) * int(match[2] or 1) if match else 0
    formula = name[: match.start()] if match else name
    for ligand, atoms in LIGANDS.items():
        formula = formula.replace(ligand, '(' + atoms + ')')
    total = defaultdict(Fraction)
    for part in formula.split(':'):
        leading = re.match(r'^(\d+)(.*)', part)
        scale, part = (int(leading[1]), leading[2]) if leading else (1, part)
        tokens = re.findall(r'[A-Z][a-z]?|\d+|[()]', part)
        if ''.join(tokens) != part:
            raise ValueError('unsupported formula: ' + name)
        stack = [defaultdict(Fraction)]
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token == '(':
                stack.append(defaultdict(Fraction))
                i += 1
                continue
            if token == ')':
                if len(stack) == 1:
                    raise ValueError('unmatched group: ' + name)
                item = stack.pop()
            elif token.isalpha():
                item = {token: Fraction(1)}
            else:
                raise ValueError('unexpected multiplier: ' + name)
            i += 1
            count = int(tokens[i]) if i < len(tokens) and tokens[i].isdigit() else 1
            i += int(i < len(tokens) and tokens[i].isdigit())
            for atom, value in item.items():
                stack[-1][atom] += count * value
        if len(stack) != 1:
            raise ValueError('unclosed group: ' + name)
        for atom, value in stack[0].items():
            total[atom] += scale * value
    total['charge'] = Fraction(charge)
    return {k: v for k, v in total.items() if v}


def equation(text):
    """Signed original coefficients (reactants negative, products positive)."""
    result = defaultdict(Fraction)
    left, right = text.split('=')
    for sign, side in ((-1, left), (1, right)):
        for term in side.strip().split(' + '):
            fields = term.split()
            amount, name = (Fraction(fields[0]), fields[1]) if len(fields) == 2 else (1, fields[0])
            result[name] += sign * amount
    return {k: v for k, v in result.items() if v}


def weighted(terms, lookup):
    values = defaultdict(Fraction)
    for name, coefficient in terms.items():
        for key, amount in lookup(name).items():
            values[key] += Fraction(str(coefficient)) * Fraction(str(amount))
    return {k: v for k, v in values.items() if v}


def roundoff_equal(actual, expected, terms):
    """A floating representation check, not an allowance for parameter uncertainty."""
    scale = max([abs(float(actual)), abs(float(expected)), 1.0] + [abs(float(v)) for v in terms])
    # Each stored expansion is a finite sum; bound accumulated binary rounding.
    allowance = 4 * (len(terms) + 1) * math.ulp(scale)
    return abs(float(actual) - float(expected)) <= allowance


def audit_model(data, source_texts=None):
    """Return per-reaction checks and explicit unqualified source/applicability limits."""
    source_texts = source_texts or {}
    by_name = {r['name']: r for r in data['aqueous']}
    rows = []
    errors = []
    for kind in ('aqueous', 'phases'):
        for r in data[kind]:
            checks = {}
            terms = equation(r['equation'])
            checks['original_atoms_and_charge'] = not weighted(terms, composition)
            checks['no_electron_redox'] = 'e-' not in terms
            checks['basis_names'] = set(r['powers']) <= set(data['bases']) | {'H+', 'H2O'}
            if kind == 'aqueous':
                checks['transformed_atoms_and_charge'] = weighted(
                    r['powers'], composition
                ) == composition(r['name'])
                checks['stored_charge'] = r['charge'] == composition(r['name']).get('charge', 0)
                checks['basis_transform'] = not weighted(terms, lambda n: by_name[n]['powers'])
                beta_terms = [c * Fraction(str(by_name[n]['beta'])) for n, c in terms.items()]
                checks['log_k_transform'] = roundoff_equal(sum(beta_terms), r['log_k'], beta_terms)
                if not terms:
                    checks['identity_constant'] = r['beta'] == r['log_k'] == 0
            else:
                solid = r['equation'].split('=')[0].split(' + ')[0].strip()
                aqueous_terms = {n: c for n, c in terms.items() if n != solid}
                transformed = weighted(aqueous_terms, lambda n: by_name[n]['powers'])
                checks['basis_transform'] = transformed == {
                    k: Fraction(str(v)) for k, v in r['powers'].items()
                }
                checks['transformed_atoms_and_charge'] = weighted(
                    r['powers'], composition
                ) == composition(solid)
                beta_terms = [
                    c * Fraction(str(by_name[n]['beta'])) for n, c in aqueous_terms.items()
                ]
                expected = Fraction(str(r['log_k'])) - sum(beta_terms)
                checks['log_k_transform'] = roundoff_equal(r['beta'], expected, beta_terms)
            source = source_texts.get(r['source'])
            verified = None
            if r['line'] == 0:
                verified = r['source'] == 'fixed-valence analytical basis' and not terms
                checks['synthetic_identity'] = verified
            elif source is not None:
                lines = source.splitlines()
                index = r['line'] - 1
                verified = (
                    0 <= index < len(lines) and lines[index].split('#')[0].strip() == r['equation']
                )
                checks['source_equation'] = verified
                log_k = None
                for line in lines[index + 1 :]:
                    text = line.split('#')[0].strip()
                    if '=' in text:
                        break
                    fields = text.split()
                    if fields and fields[0].lstrip('-').lower() == 'log_k':
                        log_k = float(fields[1])
                        break
                checks['source_log_k'] = log_k == r['log_k']
                verified = verified and checks['source_log_k']
            for check, passed in checks.items():
                if not passed:
                    errors.append(f'{kind}/{r["name"]}: {check}')
            rows.append(
                dict(
                    kind=kind,
                    name=r['name'],
                    source=r['source'],
                    line=r['line'],
                    source_verified=verified,
                    checks=checks,
                    parameter_status='fixed_basis_identity'
                    if r['line'] == 0
                    else 'selected_project_profile'
                    if r['source'] == 'flahax-chelates-25c.dat'
                    else 'cited_phase_extension'
                    if r['source'] == 'flahax-phases-25c.dat'
                    else 'pinned_database_compilation',
                    experimental_applicability='not independently requalified',
                )
            )
    return dict(
        status='passed' if not errors else 'failed',
        errors=errors,
        reactions=rows,
        independent_experimental_validation=False,
        scope='Exact atom/charge/component equations; floating log-K transformation; '
        'optional source-line correspondence. No database modifications or new constants.',
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    model = ROOT / 'src/flahax/data/chemistry_25c.json'
    data = json.loads(model.read_text())
    paths = {'minteq.v4.dat': args.database}
    paths.update(
        {
            n: ROOT / 'tests/fixtures/phreeqc/database' / n
            for n in ('flahax-chelates-25c.dat', 'flahax-phases-25c.dat')
        }
    )
    hashes = {n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in paths.items()}
    report = audit_model(data, {n: p.read_text() for n, p in paths.items()})
    if hashes['minteq.v4.dat'] != data['database_sha256']:
        report['errors'].append('base database hash differs from pinned model')
        report['status'] = 'failed'
    report.update(
        source_sha256=hashes, model_sha256=hashlib.sha256(model.read_bytes()).hexdigest()
    )
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(
        json.dumps(
            dict(
                status=report['status'],
                reactions=len(report['reactions']),
                errors=report['errors'],
            )
        )
    )
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
