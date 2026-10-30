# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Conservative automatic separation assignments, never mixture-solubility approval.

Sourced pair prohibitions remain hard constraints. Equipment cannot waive them.
Element classes are conservative screens, not evidence that a mixture dissolves.
Caller rules add separations; reagent products retain their own channel.
"""

from dataclasses import dataclass
import math

from .delivery_contracts import DELIVERY_SCHEMA_VERSION, DeliveryError, validate_compatibility_rule
from .engine import PH_REAGENT

SOURCE = (
    'Yara, Fertilizantes para fertirrigación, p. 65 mixing compatibility table and p. 63 '
    'mixing rules'
)
MICRONUTRIENTS = frozenset({'Fe', 'Mn', 'Zn', 'Cu', 'B', 'Mo'})
# Elements a micronutrient product may carry besides its micronutrients (counter-ions).
_MICRO_COMPANIONS = frozenset({'S', 'Na', 'Cl'})
STRONG_ACIDS = frozenset({'HNO3', 'H3PO4', 'H2SO4'})

# (class, class, reason): the page 63/65 rules.
CLASS_RULES = (
    (
        'calcium',
        'phosphate',
        'calcium and phosphate precipitate as calcium phosphate in a concentrate',
    ),
    ('calcium', 'sulfate', 'calcium and sulfate precipitate as gypsum in a concentrate'),
)

# Retained historical text of the retired waiver, not an active policy.
RETIRED_TWO_TANKS = 'Retired two-tank waiver; equipment cannot establish compatibility'
CLASS_RULES += (
    (
        'magnesium',
        'phosphate',
        'magnesium and phosphate require separation without mixture evidence',
    ),
)
WAIVED_RULES = ()
MAX_TANKS = 2  # Legacy equipment default for callers that explicitly request it.

# Page 65 products, for labelling only: catalogue name -> Yara name. Grouping uses the class rules.
ANALOGUE = {
    'Urea': 'Urea',
    'Ammonium Nitrate': 'AM NITRA',
    'Ammonium Sulfate': 'AS',
    'Phosphoric Acid (75%)': 'Phos. acid',
    'Ammonium Monobasic Phosphate': 'KRISTA-MAP',
    'Potassium Monobasic Phosphate': 'KRISTA-MKP',
    'Potassium Chloride': 'KRISTA-MOP',
    'Potassium Sulfate': 'KRISTA-SOP',
    'Potassium Nitrate': 'KRISTA-K',
    'Calcium Nitrate (ag grade)': 'CALCINIT',
    'Mg Nitrate': 'KRISTA-MAG',
    'Magnesium Sulfate (Heptahydrate)': 'KRISTA-MgS',
}
# Page 65 footnotes on compatible pairs: (*) solubility as potassium sulfate, (**) as magnesium
# sulfate.
FOOTNOTES = {
    frozenset({'KRISTA-K', 'AS'}): 'mixture solubility as potassium sulfate (p. 65 *)',
    frozenset({'KRISTA-MAG', 'KRISTA-SOP'}): 'mixture solubility as magnesium sulfate (p. 65 **)',
    frozenset({'KRISTA-MAG', 'AS'}): 'mixture solubility as magnesium sulfate (p. 65 **)',
    frozenset({'KRISTA-MgS', 'KRISTA-K'}): 'mixture solubility as potassium sulfate (p. 65 *)',
    frozenset({'KRISTA-MgS', 'KRISTA-MOP'}): 'mixture solubility as potassium sulfate (p. 65 *)',
}
FLAHAX_RULE = 'FlahaX rule (decision rafatahmed/Flahax#79)'
MICRO_PHOSPHATE = (
    'micronutrients stay out of phosphate concentrates, where manganese and iron phosphates can '
    'form '
    '(#78); no small-dose compatibility exemption is inferred'
)
TANK_A_RULE = (
    'Tank A holds the calcium products, micronutrients and chelates: never acidify it. '
    'Dose acid on its own channel or into another tank (Yara p. 63).'
)


@dataclass(frozen=True)
class TankProduct:
    """A product placed in a tank: its final-solution dose and why it is there."""

    product_id: str
    name: str
    grams_per_litre: float  # in the final solution
    basis: str  # why it is in this tank


@dataclass(frozen=True)
class ConcentrateTank:
    """One concentrate tank: its products, whether acid may go in, and notes."""

    name: str
    products: tuple
    acid_allowed: bool
    notes: tuple = ()

    def stock_grams_per_litre(self, injection_ratio):
        """Concentrate strength of each product at 1:injection_ratio (not solubility-checked)."""
        return {p.name: p.grams_per_litre * injection_ratio for p in self.products}


@dataclass(frozen=True)
class TankGrouping:
    """Products grouped into tanks, the pH reagent channel, the pairs kept apart and the pairs a
    waived rule lets share a tank.
    """

    tanks: tuple
    reagent_channel: tuple  # pH reagents: dosed on their own channel
    separations: tuple  # (product, product, reason) pairs kept apart
    waived: tuple = ()  # (product, product, reason) pairs a waived rule lets share a tank
    source: str = SOURCE
    solubility_checked: bool = False

    def tank_of(self, name):
        """The name of the tank that holds a product, or None."""
        return next((t.name for t in self.tanks for p in t.products if p.name == name), None)


def product_classes(record):
    """Chemical classes of a product record from its elemental analysis and formula."""
    elements = {k for k, v in (record.get('elements') or {}).items() if v}
    classes = set()
    for element, label in (
        ('Ca', 'calcium'),
        ('Mg', 'magnesium'),
        ('P', 'phosphate'),
        ('S', 'sulfate'),
    ):
        if element in elements:
            classes.add(label)
    if elements & MICRONUTRIENTS and not elements - MICRONUTRIENTS - _MICRO_COMPANIONS:
        classes.add('micronutrient')
    if str(record.get('formula', '')).replace(' ', '') in STRONG_ACIDS:
        classes.add('acid')
    return frozenset(classes)


def _class_conflict(a, b, rules=CLASS_RULES):
    if 'micronutrient' in a | b and 'phosphate' in a | b:
        return MICRO_PHOSPHATE
    for x, y, reason, *_ in rules:
        if (x in a and y in b) or (y in a and x in b):
            return reason
    return None


def default_compatibility_rules(products, *, recorded_at='2026-10-22T00:00:00Z'):
    """The default table as ``compatibilityRule`` records for ``plan_stocks``.

    One "separate" record per incompatible pair among ``products`` (catalogue or
    grade records with ``id``, ``elements`` and optional ``formula``). Micronutrient
    products retain elemental separation screens; no small-dose waiver applies.
    """
    records = [p for p in products if p.get('role') != PH_REAGENT]
    rules = []
    for i, a in enumerate(records):
        for b in records[i + 1 :]:
            ca, cb = product_classes(a), product_classes(b)
            reason = _class_conflict(ca, cb)
            if reason:
                rules.append(
                    validate_compatibility_rule(
                        dict(
                            schemaVersion=DELIVERY_SCHEMA_VERSION,
                            id=f'default-{a["id"]}-{b["id"]}',
                            source=FLAHAX_RULE if reason == MICRO_PHOSPHATE else SOURCE,
                            revision='1',
                            recordedAt=recorded_at,
                            productIds=[a['id'], b['id']],
                            constraint='separate',
                            reason=reason,
                            temperatureMinC=0,
                            temperatureMaxC=50,
                        )
                    )
                )
    return rules


def group_tanks(salts, products, *, rules=(), max_tanks=None, max_search_nodes=100000):
    """Find a minimum-tank separation assignment; no mixture approval is implied.

    With max_tanks=None, report the required equipment rather than waive a rule.
    An explicit tank count is a hard equipment limit. Search is deterministic and
    bounded; exhaustion is reported separately from proven incompatibility.
    Reagent products use a separate channel. Every separation is conservative
    even outside its source temperature envelope; it never becomes permission.
    """
    if (max_tanks is not None and (type(max_tanks) is not int or max_tanks < 1)) or (
        type(max_search_nodes) is not int or max_search_nodes < 1
    ):
        raise DeliveryError('invalid_value', 'tank and search limits must be positive integers')
    by_id = {p['id']: p for p in products}
    extra = [validate_compatibility_rule(r) for r in rules]
    rows, seen = [], set()
    for salt in salts:
        if salt['id'] in seen:
            raise DeliveryError('invalid_value', 'recipe product ids must be unique')
        seen.add(salt['id'])
        record = by_id.get(salt['id'])
        if record is None:
            raise DeliveryError('unknown_product', f'{salt["name"]} is not supplied')
        dose = salt['gramsPerLitre']
        if (
            isinstance(dose, bool)
            or not isinstance(dose, (int, float))
            or not math.isfinite(dose)
            or dose < 0
        ):
            raise DeliveryError('invalid_value', 'recipe dose must be finite and nonnegative')
        if dose > 0:
            rows.append((salt, record, product_classes(record)))
    reagents = tuple(s['name'] for s, r, _ in rows if r.get('role') == PH_REAGENT)
    rows = [r for r in rows if r[1].get('role') != PH_REAGENT]
    rows.sort(
        key=lambda r: (
            'calcium' not in r[2],
            'micronutrient' not in r[2],
            -r[0]['gramsPerLitre'],
            r[0]['id'],
        )
    )

    def reason(a, b):
        for rule in extra:
            if a[0]['id'] in rule['productIds'] and b[0]['id'] in rule['productIds']:
                return f'{rule["reason"]} ({rule["source"]})'
        if ('acid' in a[2] and b[2] & {'calcium', 'micronutrient'}) or (
            'acid' in b[2] and a[2] & {'calcium', 'micronutrient'}
        ):
            return 'acid separated from calcium and micronutrients'
        return _class_conflict(a[2], b[2])

    conflicts = {
        (i, j): reason(a, b) for i, a in enumerate(rows) for j, b in enumerate(rows) if i < j
    }
    nodes = 0

    def assign(index, groups, count):
        nonlocal nodes
        nodes += 1
        if nodes > max_search_nodes:
            raise DeliveryError('stock_search_limit', 'assignment search budget exhausted')
        if index == len(rows):
            return [g[:] for g in groups]
        for group in groups:
            if all(not conflicts[(j, index)] for j in group):
                group.append(index)
                found = assign(index + 1, groups, count)
                group.pop()
                if found is not None:
                    return found
        if len(groups) < count:
            groups.append([index])
            found = assign(index + 1, groups, count)
            groups.pop()
            if found is not None:
                return found
        return None

    selected = [] if not rows else None
    for count in range(1, min(len(rows), max_tanks or len(rows)) + 1):
        selected = assign(0, [], count)
        if selected is not None:
            break
    if selected is None:
        raise DeliveryError(
            'too_many_tanks',
            f'No separation assignment fits {max_tanks} tanks: '
            + ', '.join(r[0]['name'] for r in rows),
        )
    built = []
    for index, group in enumerate(selected):
        contents = [rows[i] for i in group]
        protected = any(r[2] & {'calcium', 'micronutrient'} for r in contents)
        names = {ANALOGUE.get(r[0]['name']) for r in contents} - {None}
        notes = sorted({n for pair, n in FOOTNOTES.items() if pair <= names})
        notes.append('Separation assignment only; mixture solubility is unqualified.')
        if protected:
            notes.append('Never acidify a tank holding calcium or micronutrients.')
        built.append(
            ConcentrateTank(
                chr(65 + index) if index < 26 else f'Tank-{index + 1}',
                tuple(
                    TankProduct(
                        r[0]['id'],
                        r[0]['name'],
                        r[0]['gramsPerLitre'],
                        'automatic separation assignment; not mixture approval',
                    )
                    for r in contents
                ),
                not protected,
                tuple(notes),
            )
        )
    separations = tuple(
        (rows[i][0]['name'], rows[j][0]['name'], why) for (i, j), why in conflicts.items() if why
    )
    return TankGrouping(tuple(built), reagents, separations)
