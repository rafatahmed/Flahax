"""Concentrate-tank grouping from a sourced default compatibility table (#79).

Source: Yara, "Fertilizantes para fertirrigación", page 65 mixing compatibility
table, read with page 63 ("DO NOT mix calcium content fertilizers with phosphate or
sulphate fertilizer"; "do not acidify tanks with microelement chelates"). The table
covers twelve products; its twelve "No" pairs are exactly three chemical rules,
applied here to every product from its elemental analysis:

- calcium with phosphate, and calcium with sulfate (page 63 and page 65);
- magnesium with phosphate (page 65: magnesium nitrate and magnesium sulfate with
  potassium and ammonium phosphates and phosphoric acid).

FlahaX rule (owner decision, rafatahmed/Flahax#79): micronutrients and chelates go
to tank A with the calcium products, because their doses are too small to
precipitate there, and tank A is never acidified (page 63). They are kept out of
phosphate concentrates, where manganese and iron phosphates can form (#78). Acids are dosed on
their own channel or into another tank; pH reagents always have their own channel.

The table states compatibility in concentrates, not solubility: every stock still
needs a grade- and temperature-qualified solubility check. Separation rules of your
own (``compatibilityRule`` records, as for ``plan_stocks``) are applied on top.
"""
from dataclasses import dataclass

from .delivery_contracts import DELIVERY_SCHEMA_VERSION, DeliveryError, validate_compatibility_rule
from .engine import PH_REAGENT

SOURCE = ('Yara, Fertilizantes para fertirrigación, p. 65 mixing compatibility table and p. 63 mixing rules')
MICRONUTRIENTS = frozenset({'Fe', 'Mn', 'Zn', 'Cu', 'B', 'Mo'})
# Elements a micronutrient product may carry besides its micronutrients (counter-ions).
_MICRO_COMPANIONS = frozenset({'S', 'Na', 'Cl'})
STRONG_ACIDS = frozenset({'HNO3', 'H3PO4', 'H2SO4'})

# (class, class, reason): the page 63/65 rules.
CLASS_RULES = (
    ('calcium', 'phosphate', 'calcium and phosphate precipitate as calcium phosphate in a concentrate'),
    ('calcium', 'sulfate', 'calcium and sulfate precipitate as gypsum in a concentrate'),
    ('magnesium', 'phosphate', 'magnesium and phosphate precipitate as magnesium phosphate in a concentrate'),
)

# Page 65 products, for labelling only: catalogue name -> Yara name. Grouping uses the class rules.
ANALOGUE = {
    'Urea': 'Urea', 'Ammonium Nitrate': 'AM NITRA', 'Ammonium Sulfate': 'AS',
    'Phosphoric Acid (75%)': 'Phos. acid', 'Ammonium Monobasic Phosphate': 'KRISTA-MAP',
    'Potassium Monobasic Phosphate': 'KRISTA-MKP', 'Potassium Chloride': 'KRISTA-MOP',
    'Potassium Sulfate': 'KRISTA-SOP', 'Potassium Nitrate': 'KRISTA-K',
    'Calcium Nitrate (ag grade)': 'CALCINIT', 'Mg Nitrate': 'KRISTA-MAG',
    'Magnesium Sulfate (Heptahydrate)': 'KRISTA-MgS',
}
# Page 65 footnotes on compatible pairs: (*) solubility as potassium sulfate, (**) as magnesium sulfate.
FOOTNOTES = {
    frozenset({'KRISTA-K', 'AS'}): 'mixture solubility as potassium sulfate (p. 65 *)',
    frozenset({'KRISTA-MAG', 'KRISTA-SOP'}): 'mixture solubility as magnesium sulfate (p. 65 **)',
    frozenset({'KRISTA-MAG', 'AS'}): 'mixture solubility as magnesium sulfate (p. 65 **)',
    frozenset({'KRISTA-MgS', 'KRISTA-K'}): 'mixture solubility as potassium sulfate (p. 65 *)',
    frozenset({'KRISTA-MgS', 'KRISTA-MOP'}): 'mixture solubility as potassium sulfate (p. 65 *)',
}
FLAHAX_RULE = 'FlahaX rule (owner decision, rafatahmed/Flahax#79)'
MICRO_PHOSPHATE = ('micronutrients stay out of phosphate concentrates, where manganese and iron phosphates can form '
                   '(#78); with calcium their small doses are harmless (FlahaX rule)')
TANK_A_RULE = ('Tank A holds the calcium products, micronutrients and chelates: never acidify it. '
               'Dose acid on its own channel or into another tank (Yara p. 63).')


@dataclass(frozen=True)
class TankProduct:
    product_id: str
    name: str
    grams_per_litre: float      # in the final solution
    basis: str                  # why it is in this tank


@dataclass(frozen=True)
class ConcentrateTank:
    name: str
    products: tuple
    acid_allowed: bool
    notes: tuple = ()

    def stock_grams_per_litre(self, injection_ratio):
        """Concentrate strength of each product at 1:injection_ratio (not solubility-checked)."""
        return {p.name: p.grams_per_litre * injection_ratio for p in self.products}


@dataclass(frozen=True)
class TankGrouping:
    tanks: tuple
    reagent_channel: tuple      # pH reagents: dosed on their own channel
    separations: tuple          # (product, product, reason) pairs kept apart
    source: str = SOURCE
    solubility_checked: bool = False

    def tank_of(self, name):
        return next((t.name for t in self.tanks for p in t.products if p.name == name), None)


def product_classes(record):
    """Chemical classes of a product record from its elemental analysis and formula."""
    elements = {k for k, v in (record.get('elements') or {}).items() if v}
    classes = set()
    for element, label in (('Ca', 'calcium'), ('Mg', 'magnesium'), ('P', 'phosphate'), ('S', 'sulfate')):
        if element in elements:
            classes.add(label)
    if elements & MICRONUTRIENTS and not elements - MICRONUTRIENTS - _MICRO_COMPANIONS:
        classes.add('micronutrient')
    if str(record.get('formula', '')).replace(' ', '') in STRONG_ACIDS:
        classes.add('acid')
    return frozenset(classes)


def _class_conflict(a, b):
    if 'micronutrient' in a | b:
        # FlahaX rule: the page 63/65 rules are waived for micronutrients (small doses), but they stay
        # out of phosphate concentrates (manganese and iron phosphates, #78).
        return MICRO_PHOSPHATE if 'phosphate' in a | b else None
    for x, y, reason in CLASS_RULES:
        if (x in a and y in b) or (y in a and x in b):
            return reason
    return None


def default_compatibility_rules(products, *, recorded_at='2026-10-22T00:00:00Z'):
    """The default table as ``compatibilityRule`` records for ``plan_stocks``.

    One "separate" record per incompatible pair among ``products`` (catalogue or
    grade records with ``id``, ``elements`` and optional ``formula``). Micronutrient
    products are kept only from phosphate (FlahaX rule).
    """
    records = [p for p in products if p.get('role') != PH_REAGENT]
    rules = []
    for i, a in enumerate(records):
        for b in records[i + 1:]:
            ca, cb = product_classes(a), product_classes(b)
            reason = _class_conflict(ca, cb)
            if reason:
                rules.append(validate_compatibility_rule(dict(
                    schemaVersion=DELIVERY_SCHEMA_VERSION, id=f'default-{a["id"]}-{b["id"]}',
                    source=FLAHAX_RULE if reason == MICRO_PHOSPHATE else SOURCE,
                    revision='1', recordedAt=recorded_at, productIds=[a['id'], b['id']], constraint='separate',
                    reason=reason, temperatureMinC=0, temperatureMaxC=50)))
    return rules


def group_tanks(salts, products, *, rules=()):
    """Group a recipe's products into concentrate tanks.

    ``salts`` are recipe rows with ``id``, ``name`` and ``gramsPerLitre`` (as in
    ``recommend(...)['salts']``); ``products`` are the records they came from.
    Tank A takes the calcium products, then every micronutrient product; the others
    follow by descending dose into the first tank without a conflict; acids never
    join a tank holding calcium or micronutrients. pH reagents are returned apart, for
    their own channel. ``rules`` are extra ``compatibilityRule`` records that
    separate products by id; they also override the micronutrient rule.
    """
    by_id = {p['id']: p for p in products}
    extra = [validate_compatibility_rule(r) for r in rules]
    rows = []
    for salt in salts:
        record = by_id.get(salt['id'])
        if record is None:
            raise DeliveryError('unknown_product', f'{salt["name"]} is not among the supplied product records')
        rows.append((salt, record, product_classes(record)))
    reagents = tuple(s['name'] for s, r, _ in rows if r.get('role') == PH_REAGENT)
    rows = [row for row in rows if row[1].get('role') != PH_REAGENT]

    def user_rule(a, b):
        for rule in extra:
            if a['id'] in rule['productIds'] and b['id'] in rule['productIds']:
                return f'{rule["reason"]} ({rule["source"]})'
        return None

    def reason(row, other):
        return user_rule(row[0], other[0]) or _class_conflict(row[2], other[2])

    def holds_a(tank):
        return any('calcium' in r[2] or 'micronutrient' in r[2] for r in tank)

    calcium = sorted((r for r in rows if 'calcium' in r[2] and 'micronutrient' not in r[2]),
                     key=lambda r: -r[0]['gramsPerLitre'])
    micros = [r for r in rows if 'micronutrient' in r[2]]
    others = sorted((r for r in rows if r not in calcium and r not in micros), key=lambda r: -r[0]['gramsPerLitre'])
    tanks, basis = [[]], {}
    for row in calcium + micros:
        micro = 'micronutrient' in row[2]
        if any(reason(row, other) for other in tanks[0]):
            others.append(row)
            continue
        tanks[0].append(row)
        basis[row[0]['name']] = ('micronutrient or chelate: tank A (FlahaX rule, small doses)' if micro
                                 else 'calcium product: tank A')
    for row in others:
        acid = 'acid' in row[2]
        for tank in tanks:
            if (acid and holds_a(tank)) or any(reason(row, other) for other in tank):
                continue
            tank.append(row)
            break
        else:
            tanks.append([row])
        basis.setdefault(row[0]['name'], 'acid: never with calcium or chelates' if acid else 'first tank without a conflict')
    tanks = [t for t in tanks if t]
    separations = []
    for i, tank in enumerate(tanks):
        for later in tanks[i + 1:]:
            for row in tank:
                for other in later:
                    why = reason(row, other)
                    if why:
                        separations.append((row[0]['name'], other[0]['name'], why))

    def notes(tank):
        names = {ANALOGUE.get(r[0]['name']) for r in tank} - {None}
        found = sorted({n for pair, n in FOOTNOTES.items() if pair <= names})
        if holds_a(tank):
            found.insert(0, TANK_A_RULE)
        return tuple(found)

    built = []
    for index, tank in enumerate(tanks):
        built.append(ConcentrateTank(
            name='ABCDEFGH'[index],
            products=tuple(TankProduct(s['id'], s['name'], s['gramsPerLitre'], basis[s['name']]) for s, _, _ in tank),
            acid_allowed=not holds_a(tank), notes=notes(tank)))
    return TankGrouping(tuple(built), reagents, tuple(separations))
