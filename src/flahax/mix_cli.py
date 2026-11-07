# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""``flahax mix``: five steps, then tank A, tank B and the pH reagent.

    flahax mix                    ask the five steps, save the answers, write the sheets
    flahax mix sessions/NAME      run a saved session again without questions
    flahax mix --plain            ask line by line instead of the full-screen wizard

Steps: 1/5 specification (tanks, injection ratio, temperature, how stock is
prepared), 2/5 water analysis, 3/5 crop formula, 4/5 fertilizers, 5/5 available
acids and bases and target pH. Defaults are shown in brackets; Enter keeps them.
Typed items are saved
under ``$FLAHAX_HOME`` (else ``~/.flahax``) as files ``flahax batch`` reads, and only
once every step is answered: Ctrl+C or end of input saves nothing.
"""

import argparse
from dataclasses import asdict
from datetime import date
import math
from pathlib import Path
import sys

from . import __version__
from .batch_cli import ACID_FORMULAS, BatchOptions, limit_entry, read_json, render, run_batch
from .composition import target_ion_balance
from .delivery_contracts import DeliveryError
from .engine import load_library
from .grower_report import (
    _reagent_line,
    _review_reason,
    display_residue,
    number,
    reagent_preparation_lines,
    render_report,
)
from .grower_sheet import (
    LABEL,
    STATUS_WORDS,
    grams,
    key_reasons,
    limited_by,
    litres,
    readable,
    render_mix_sheet,
)  # noqa: F401 (STATUS_WORDS re-exported)
from .label_reconciliation import label_note
from .materials import declared_ions_check, load_identities, make_grade, resolve_material
from .mix_store import Store, slug, check_saved_state, verify_session
from .mix_water import MICROS, WATER_IONS, ask_analysis, to_elements  # noqa: F401 (re-exported)
from .stock_volumes import prepare_stocks
from .terminal import supported
from .ph_adjustment import catalogue_ph_reagents, REAGENTS

FORMULA_KEYS = ('N_NO3', 'N_NH4', 'P', 'K', 'Ca', 'Mg', 'S', 'Fe', 'Mn', 'Zn', 'Cu', 'B', 'Mo')
COMPOUND_KEYS = (
    (
        ('N_NO3', 'Nitric N'),
        ('N_NH4', 'Ammoniacal N'),
        ('N_UREA', 'Ureic N'),
        ('P2O5', 'P2O5'),
        ('K2O', 'K2O'),
        ('CaO', 'CaO'),
        ('MgO', 'MgO'),
        ('SO3', 'SO3'),
    )
    + tuple((m, m) for m in MICROS)
    + (('Na', 'Na'), ('Cl', 'Cl'))
)
CHELATES = ('EDTA', 'DTPA', 'o,o-EDDHA', None)


def number_answer(answer, default, *, blank=False, low=0.0, high=None, positive=False):
    """(value, None) for an acceptable typed number, else (None, the message to show).

    Enter gives the default, or None when ``blank`` allows it.
    """
    answer = answer.strip()
    if not answer and (default is not None or blank):
        return default, None
    try:
        value = float(answer)
    except ValueError:
        return None, f'  {answer!r} is not a number.'
    if (
        not math.isfinite(value)
        or value < low
        or (positive and value <= low)
        or (high is not None and value > high)
    ):
        return None, (
            f'  Enter a number {"above" if positive else "from"} {low:g}'
            + (f' up to {high:g}.' if high is not None else '.')
        )
    return value, None


class Prompts:
    """The questions of ``flahax mix``; ``ask`` reads an answer and ``say`` prints."""

    def __init__(self, ask, say):
        self.ask, self.say = ask, say

    def text(self, prompt, default=None):
        """A non-empty answer, or the default on Enter when there is one."""
        while True:
            shown = '' if default is None else f' [{default or "none"}]'
            answer = self.ask(f'{prompt}{shown}: ').strip()
            if answer:
                return answer
            if default is not None:
                return default
            self.say('  This one is needed.')

    def number(self, prompt, default=None, *, blank=False, low=0.0, high=None, positive=False):
        """A finite number within the limits, asked again until valid; Enter gives the default, or
        None when ``blank`` allows it.
        """
        while True:
            shown = (
                f' [{default:g}]' if default is not None else ' (Enter if blank)' if blank else ''
            )
            value, error = number_answer(
                self.ask(f'{prompt}{shown}: '),
                default,
                blank=blank,
                low=low,
                high=high,
                positive=positive,
            )
            if error is None:
                return value
            self.say(error)

    def choose(self, prompt, options, default=1):
        """0-based index of the chosen option; with ``default=None`` Enter asks again."""
        if prompt:
            self.say(prompt)
        for i, option in enumerate(options, 1):
            self.say(f'  {i}  {option}')
        while True:
            answer = self.ask(f'Number [{default}]: ' if default else 'Number: ').strip() or str(
                default
            )
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return int(answer) - 1
            self.say(f'  Choose 1 to {len(options)}.')

    def search(self, prompt, names):
        """Part of a name narrows the list; Enter shows every name to choose from by number."""
        while True:
            query = (
                self.ask(f'{prompt} (part of the name; Enter lists all {len(names)}): ')
                .strip()
                .lower()
            )
            matches = [n for n in names if query in n.lower()]
            if len(matches) == 1:
                self.say(f'  {matches[0]}')
                return matches[0]
            if matches:
                return matches[self.choose(f'{len(matches)} match:', matches)]
            self.say(f'  Nothing matches {query!r}; press Enter to see the whole list.')

    def pick_many(self, prompt, names):
        """0-based indices of the names chosen, in the order typed and without repeats."""
        for i, name in enumerate(names, 1):
            self.say(f'  {i:2}  {name}')
        while True:
            picked = (
                self.text('Numbers of the products you have, separated by spaces')
                .replace(',', ' ')
                .split()
            )
            if all(n.isdigit() and 1 <= int(n) <= len(names) for n in picked):
                return [int(n) - 1 for n in dict.fromkeys(picked)]
            self.say(f'  Use numbers 1 to {len(names)}.')

    def step(self, index, heading=None):
        """Step ``index`` of five begins; the line mode shows ``heading`` when there is one."""
        if heading:
            self.say(heading)

    def answered(self, label, value):
        """A finished step's short answer; the line mode shows nothing."""

    def progress(self, text):
        """Progress within a step, such as the lab values typed so far; the line mode is silent."""

    def new_name(self, store, kind, prompt, default=None):
        """A name for a new saved item; an existing name is used only when the user chooses to
        replace it.
        """
        while True:
            self.typed = self.text(prompt, default)
            name = slug(self.typed)
            if (
                name not in store.list(kind)
                or self.choose(
                    f'A saved {kind[:-1]} named {name} exists.', ['Use another name', 'Replace it']
                )
                == 1
            ):
                return name

    def document(self, supplier):
        """The supplier, title and issue date of a data sheet or certificate."""
        while True:
            issued = self.text('Date on the sheet (YYYY-MM-DD)')
            try:
                date.fromisoformat(issued)
                break
            except ValueError:
                self.say('  Use the form 2025-03-28.')
        return {
            'supplier': supplier,
            'title': self.text('Sheet title'),
            'issued': issued,
            'entered': date.today().isoformat(),
        }


def ask_spec(p):
    """Step 1: tank and acid container sizes, injection ratio, stock temperature and how the stock
    is prepared, as ``prepare_stocks`` options.
    """
    p.step(1, '1/5 Specification')
    a = p.number('Tank A capacity, L', 1000, positive=True)
    b = p.number('Tank B capacity, L', 1000, positive=True)
    tanks = {
        'A': a,
        'B': b,
        'acid': p.number('Reagent container capacity, L', min(a, b), positive=True),
    }
    ratio = p.number(
        'Injection ratio, litres of irrigation per litre of stock', 100, positive=True
    )
    temperature = p.number('Stock temperature, °C', 25, high=60)
    once = (
        p.choose(
            'How is stock prepared?',
            [
                'Fill the tanks full and run several irrigations from them',
                'Make just enough for one irrigation',
            ],
        )
        == 1
    )
    while True:
        irrigation = p.number('Irrigation, L', positive=True) if once else None
        try:
            volumes = prepare_stocks(
                tank_litres=tanks,
                ratio=ratio,
                mode='once' if once else 'fill',
                irrigation_litres=irrigation,
            )
            break
        except DeliveryError as exc:
            p.say(f'  {exc}')
    p.say(
        f'  {number(volumes.irrigation_litres, 0)} L of irrigation; prepare '
        f'{litres(volumes.prepared_litres["A"])} L in each nutrient tank'
        f'{limited_by(dict(asdict(volumes), mode="once" if once else "fill"))}; '
        f'first reagent fill {litres(volumes.prepared_litres["acid"])} L '
        f'(refill as needed at the same 1:{ratio:g} ratio).'
    )
    return dict(
        tank_litres=tanks,
        ratio=ratio,
        temperature_c=temperature,
        mode='once' if once else 'fill',
        irrigation_litres=irrigation,
    )


def ask_water(p, store, pending):
    """Step 2: the water (RO, saved or new), its share and the concentration limits; returns
    (reference, share, limits).
    """
    p.step(2, '2/5 Water analysis')
    saved = store.list('waters')
    pick = p.choose('Water', ['RO water (no ions)'] + saved + ['A new analysis'])
    ref, share = 'ro', 100.0
    if 0 < pick <= len(saved):
        ref = saved[pick - 1]
    elif pick > len(saved):
        ref, data = ask_analysis(p, store)
        pending.append(('waters', ref, data))
    if ref != 'ro':
        share = p.number(
            'Share of this water in the irrigation, % (the rest RO)', 100, high=100, positive=True
        )
    while True:
        answer = p.text('Concentration limits in the final solution, mg/L, e.g. Na=69 Cl=106', '')
        try:
            limits = dict(limit_entry(item) for item in answer.replace(',', ' ').split())
            return ref, share, limits
        except argparse.ArgumentTypeError as exc:
            p.say(f'  {exc}')


def ask_formula(p, store, pending, library):
    """Step 3: the crop formula (packaged, changed, saved or typed); returns (reference, targets,
    title).
    """
    p.step(3, '3/5 Crop formula: the nutrient targets in mg/L (your fertilizers come in step 4)')
    saved = store.list('formulas')
    packaged = {f['name']: f['targets'] for f in library['formulas']}
    pick = p.choose(
        'Formula',
        ['A packaged formula', 'Start from a packaged formula and change it']
        + saved
        + ['Type a new one'],
    )
    if pick < 2:
        ref = p.search('Crop formula', list(packaged))
        targets, title = dict(packaged[ref]), ref
        if pick == 1:
            changed = {k: p.number(f'{LABEL.get(k, k)}, mg/L', v) for k, v in targets.items()}
            if changed != targets:
                targets, ref = (
                    changed,
                    p.new_name(store, 'formulas', 'Save the changed formula as', f'{ref} changed'),
                )
                title = p.typed
                pending.append(('formulas', ref, targets))
    elif pick < 2 + len(saved):
        ref = saved[pick - 2]
        targets, title = store.load('formulas', ref), ref
    else:
        ref = p.new_name(store, 'formulas', 'Name of the new formula')
        title = p.typed
        p.say('Targets in mg/L; nitrogen as NO3-N and NH4-N. Enter leaves a nutrient untargeted.')
        targets = {
            k: v
            for k in FORMULA_KEYS
            if (v := p.number(f'{LABEL.get(k, k)}, mg/L', blank=True)) is not None
        }
        pending.append(('formulas', ref, targets))
    balance = target_ion_balance(targets)
    p.say(
        f'Formula balance: cations {balance["cationsMeqPerL"]:.2f} meq/L, anions '
        f'{balance["anionsMeqPerL"]:.2f} '
        f'meq/L ({balance["imbalancePercent"]:+.1f} %).'
    )
    return ref, targets, title


def ask_notes(p):
    """Data-sheet compatibility notes, kept with the grade for the full report; ';' separates
    several."""
    answer = p.text("Notes from the data sheet, e.g. 'tank pH above 4' (Enter = none)", '')
    return [note.strip() for note in answer.split(';') if note.strip()]


def add_single(p, catalogue):
    """A single-compound fertilizer from its label, or None when the label cannot be graded.

    A label off its compound is added with a note of the surplus no ion carries (decision G5).
    """
    names = {s['name']: s for s in catalogue}
    identities = [i for i in load_identities().values() if any(n in names for n in i['products'])]
    labels = {f'{i["name"]} ({", ".join(i["products"])})': i for i in identities}
    identity = labels[p.search('Chemical, e.g. calcium nitrate', list(labels))]
    product = (
        identity['products'][0]
        if len(identity['products']) == 1
        else identity['products'][p.choose('Catalogue product', identity['products'])]
    )
    shipped = names[product]
    brand = p.text('Brand name on the label')
    supplier = p.text('Supplier')
    document = p.document(supplier)
    p.say('Label analysis, % w/w; Enter keeps the reference value.')
    analysis = {
        k: {'typical': p.number(f'{k}, %', round(v, 3), high=100)}
        for k, v in shipped['elements'].items()
    }
    grade = {
        'grade_id': f'grd-{slug(brand)}',
        'identity_id': identity['id'],
        'supplier': supplier,
        'product': brand,
        'composition': 'single',
        'document': document,
        'analysis': analysis,
        'compatibility_notes': ask_notes(p),
    }
    try:
        material = resolve_material(product, grade=make_grade(grade))
    except DeliveryError as exc:
        p.say(f'Not added: {exc}')
        return None
    p.say(f'Added {brand} as {product}.')
    note = label_note(identity, material.record['elements'])
    if note:
        p.say(note)
    return dict(
        shipped, id=material.record['id'], elements=material.record['elements'], grade=grade
    )


def add_compound(p):
    """A compound fertilizer modelled from its data-sheet composition, or None when it cannot be
    resolved.
    """
    name = p.text('Product name on the data sheet')
    supplier = p.text('Supplier')
    record = {
        'supplier': supplier,
        'product': name,
        'composition': 'declared_ions',
        'document': p.document(supplier),
    }
    record['grade_id'] = f'grd-{slug(name)}-{record["document"]["issued"]}'
    p.say(
        'Composition as printed, % w/w (oxides as oxides). Enter if the sheet does not state it.'
    )
    analysis = {}
    for key, label in COMPOUND_KEYS:
        value = p.number(f'{label}, %', blank=True, high=100)
        if value is not None:
            analysis[key] = {'typical': value}
    record['analysis'] = analysis
    if any(analysis.get(m, {}).get('typical', 0) > 0 for m in MICROS):
        pick = p.choose('Chelating agent', ['EDTA', 'DTPA', 'EDDHA (o,o)', 'none', 'not stated'])
        if pick < 4:
            record['chelating_agent'] = CHELATES[pick]
    record['compatibility_notes'] = ask_notes(p)
    try:
        grade = make_grade(record)
        material = resolve_material(name, grade=grade)
    except DeliveryError as exc:
        p.say(f'Not added: {exc}')
        return None
    check = declared_ions_check(grade)
    p.say(
        'Full chemistry: the label balances.'
        if check.modellable
        else f'Not modellable: {check.reason}. It can be formulated, but no pH reagent will be '
        f'planned with it.'
    )
    return {
        'id': material.record['id'],
        'name': name,
        'formula': None,
        'elements': material.record['elements'],
        'grade': record,
    }


def ask_products(p, store, pending, library):
    """Step 4: the fertilizers available; returns (reference, products)."""
    p.step(4, '4/5 Fertilizers available')
    catalogue, saved = library['salts'], store.list('stores')
    pick = p.choose('Fertilizers', ['The whole catalogue'] + saved + ['Tick what I have'])
    if pick == 0:
        ref, products = 'catalogue', list(catalogue)
    elif pick <= len(saved):
        ref = saved[pick - 1]
        products = store.load('stores', ref)
    else:
        ref = None
        names = [s['name'] for s in catalogue]
        products = [catalogue[i] for i in p.pick_many('Fertilizers you have', names)]
    added = False
    while kind := p.choose(
        'Add a product?',
        ['No', 'A single chemical with its label analysis', 'A compound from its data sheet'],
    ):
        record = add_single(p, catalogue) if kind == 1 else add_compound(p)
        if record is not None:
            products, added = [x for x in products if x['name'] != record['name']] + [record], True
    if ref is None or added:
        ref = p.new_name(store, 'stores', 'Save this product list as', 'my fertilizers')
        pending.append(('stores', ref, products))
    return ref, products


def ask_reagents(p, store, pending):
    """Select the available pH products just like the available fertilizers."""
    from .batch_cli import acid_record

    catalogue = catalogue_ph_reagents()
    saved = [name for name in store.list('reagents') if name != 'catalogue']
    pick = p.choose(
        'pH reagents',
        ['The whole catalogue'] + saved + ['Tick what I have', 'No pH reagents available'],
    )
    if pick == 0:
        ref, products = 'catalogue', catalogue
    elif pick <= len(saved):
        ref, products = saved[pick - 1], store.load('reagents', saved[pick - 1])
    elif pick == len(saved) + 1:
        offered = list(catalogue)
        for name in store.list('acids'):
            a = store.load('acids', name)
            spec = f'{a["formula"]}:{a["fraction"]}:{a["density"]}:{a["name"]}'
            if 'solvent_fraction' in a:
                spec += f':{a["solvent_fraction"]}'
            offered.append(acid_record(spec))
        products = [
            offered[i] for i in p.pick_many('pH reagents you have', [r['name'] for r in offered])
        ]
        ref = None
    else:
        ref, products = None, []
    while p.choose('Add a pH reagent?', ['No', 'A custom reagent from its declared composition']):
        formulas = {f.upper(): f for f in REAGENTS}
        formula = None
        while formula is None:
            formula = formulas.get(p.text('Reagent formula (' + ', '.join(REAGENTS) + ')').upper())
            if formula is None:
                p.say('This reagent identity is not supported; choose a listed formula.')
        active_percent = p.number('Active ingredient, % w/w', positive=True, high=100)
        fraction = active_percent / 100
        form = ('liquid', 'solid')[p.choose('Physical form', ['Liquid', 'Solid'])]
        density = p.number('Density, kg/L', positive=True) if form == 'liquid' else None
        solvent = p.number(
            'Declared water content, % w/w (Enter if unknown)',
            blank=True,
            high=100 - active_percent,
        )
        name = p.text('Reagent name')
        record = dict(
            id='custom-' + slug(name),
            name=name,
            chemicalFormula=formula,
            massFraction=fraction,
            physicalForm=form,
            densityKgPerL=density,
            solventMassFraction=None if solvent is None else solvent / 100,
            source='user-declared composition',
            revision='1',
            recordedAt=date.today().isoformat(),
        )
        if any(r['id'] == record['id'] for r in products):
            p.say('A reagent with that name is already selected; use a distinct name.')
            continue
        products = products + [record]
        ref = None
    if ref is None:
        ref = p.new_name(store, 'reagents', 'Save this reagent list as', 'my reagents')
        while ref == 'catalogue':
            p.say('Catalogue is reserved for the built-in list. Choose another name.')
            ref = p.new_name(store, 'reagents', 'Save this reagent list as', 'my reagents')
        pending.append(('reagents', ref, products))
    return ref, products


def ask_acids(p, store, pending):
    """Names of the acids chosen for the pH plan, saved or entered from a certificate."""
    chosen, saved = [], store.list('acids')
    while True:
        offer = [s for s in saved if s not in chosen]
        options = offer + ['A new acid from its certificate', 'Done' if chosen else 'No acid']
        pick = p.choose('Acids for the pH plan', options, len(options) if chosen else 1)
        if pick < len(offer):
            chosen.append(offer[pick])
        elif pick == len(offer):
            while (
                formula := ACID_FORMULAS.get(
                    p.text(
                        'Acid formula (' + ', '.join(ACID_FORMULAS.values()) + ')', 'HNO3'
                    ).upper()
                )
            ) is None:
                p.say(
                    '  FlahaX plans with these acids only: '
                    + ', '.join(ACID_FORMULAS.values())
                    + '.'
                )
            fraction = p.number('Assay on the certificate, % w/w', positive=True, high=100) / 100
            density = p.number('Density on the certificate, kg/L', positive=True)
            while ':' in (name := p.text('Name of this acid', f'{formula} {fraction:.0%}')):
                p.say('  A name cannot contain ":".')
            ref = (
                p.new_name(store, 'acids', 'Save as', name) if slug(name) in saved else slug(name)
            )
            pending.append(
                (
                    'acids',
                    ref,
                    {'formula': formula, 'fraction': fraction, 'density': density, 'name': name},
                )
            )
            chosen.append(ref)
            p.say(f'  Added {name} for the pH plan.')
        else:
            return chosen


def options_for(store, session):
    """``BatchOptions`` from a session; every saved item it names must exist."""

    check_session(session, "saved answers")
    if 'reagent_store' not in session:
        raise DeliveryError(
            'reagent_selection_required',
            'This saved session has no available pH reagent list. '
            'Run flahax mix sessions/NAME --review-reagents '
            'to select the acids and bases you have; '
            'saved acid certificates remain available.',
        )
    verify_session(store, session)

    def path(kind, name):
        file = store.path(kind, name)
        if not file.is_file():
            raise DeliveryError(
                'unknown_item', f'the session needs the saved {kind[:-1]} {name!r} ({file})'
            )
        return str(file)

    spec, packaged = session['spec'], {f['name'] for f in load_library()['formulas']}
    acids = [store.load('acids', a) for a in session['acids']]
    return BatchOptions(
        water='ro' if session['water'] == 'ro' else path('waters', session['water']),
        formula=session['formula'] if session['formula'] in packaged else None,
        targets=None if session['formula'] in packaged else path('formulas', session['formula']),
        water_share=None if session['water_share'] >= 100 else session['water_share'],
        ph=session['ph'],
        reagents=None
        if session['reagent_store'] == 'catalogue'
        else path('reagents', session['reagent_store']),
        ratio=spec['ratio'],
        acid=[
            f'{a["formula"]}:{a["fraction"]}:{a["density"]}:{a["name"]}'
            + (f':{a["solvent_fraction"]}' if 'solvent_fraction' in a else '')
            for a in acids
        ],
        confirmed_products=session.get('confirmed_products', []),
        max_solid_reagent_grams=session.get('max_solid_reagent_grams'),
        limit=list(session['limits'].items()),
        products=None if session['store'] == 'catalogue' else path('stores', session['store']),
        tank_litres=spec['tank_litres'],
        mode=spec['mode'],
        irrigation_litres=spec['irrigation_litres'],
        temperature_c=spec['temperature_c'],
        depth=session.get('depth', 1),
        title=session.get('formula_title'),
    )


def review_reagents(p, store, name, session):
    """Explicitly review availability and save new answers without rewriting the old record."""
    verify_session(store, session)
    pending = []
    p.say(
        'Review available pH reagents. Other answers are retained; '
        'the result will be recalculated.'
    )
    ref, products = ask_reagents(p, store, pending)
    p.answered('pH reagents', ', '.join(r['name'] for r in products) or 'none available')
    updated = {
        k: v for k, v in session.items() if k not in ('saved_state', 'acceptance', 'accepted')
    }
    updated.update(reagent_store=ref, acids=[])
    new_name = p.new_name(store, 'sessions', 'Save reviewed answers as', name + ' reviewed')
    if new_name == name:
        raise DeliveryError(
            'invalid_session', 'Use a new session name to preserve the original answers'
        )
    for kind, item, data in pending:
        store.save(kind, item, data)
    store.save('sessions', new_name, updated)
    return new_name, updated


def interview(p, store):
    """The five steps; returns (session name, session, items to save). Nothing is written here."""
    library, pending = load_library(), []
    spec = ask_spec(p)
    tanks = spec['tank_litres']
    p.answered(
        'Tanks',
        f'A {tanks["A"]:g} L, B {tanks["B"]:g} L\n'
        f'acid {tanks["acid"]:g} L, 1:{spec["ratio"]:g}, {spec["temperature_c"]:g} °C',
    )
    water, share, limits = ask_water(p, store, pending)
    p.answered('Water', 'RO' if water == 'ro' else f'{water} ({share:g} %)')
    formula, _, formula_title = ask_formula(p, store, pending, library)
    p.answered('Formula', formula_title)
    product_store, products = ask_products(p, store, pending, library)
    p.answered('Fertilizers', f'{len(products)} products')
    p.step(5)
    reagent_store, reagents = ask_reagents(p, store, pending)
    p.answered('pH reagents', ', '.join(r['name'] for r in reagents) or 'none available')
    p.step(5, '5/5 pH requirement')
    ph = p.number('Target pH of the final solution', 5.8, high=14, positive=True)
    p.answered('Target pH', f'{ph:g}')
    depth = 1 + p.choose(
        'Output depth',
        [
            'Grower: tanks A and B, and the pH reagent',
            'Agronomist: adds the nutrient table and the pH path',
            'Full report',
        ],
    )
    name = p.new_name(store, 'sessions', 'Save these answers as', f'{formula} {water}')
    session = {
        'spec': spec,
        'water': water,
        'water_share': share,
        'limits': limits,
        'formula': formula,
        'formula_title': formula_title,
        'store': product_store,
        'acids': [],
        'reagent_store': reagent_store,
        'ph': ph,
        'depth': depth,
    }
    return name, session, pending + [('sessions', name, session)]


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and (isinstance(value, int) or math.isfinite(value))
    )


def check_session(data, path):
    """The session read from ``path`` if it has the fields ``flahax mix`` writes, each of the
    right type; raises DeliveryError ``invalid_session`` naming the file and the field.
    """

    def bad(problem):
        raise DeliveryError('invalid_session', f'session file {path}: {problem}')

    if not isinstance(data, dict):
        bad('not a JSON object')
    for key in ('spec', 'water', 'water_share', 'limits', 'formula', 'store', 'acids', 'ph'):
        if key not in data:
            bad(f'{key!r} is missing')
    spec = data['spec']
    if not isinstance(spec, dict):
        bad("'spec' must be an object")
    for key in ('tank_litres', 'ratio', 'temperature_c', 'mode'):
        if key not in spec:
            bad(f"'spec.{key}' is missing")
    tanks = spec['tank_litres']
    if not isinstance(tanks, dict) or not all(_is_number(v) for v in tanks.values()):
        bad("'spec.tank_litres' must be an object of tank: litres")
    for key in ('ratio', 'temperature_c'):
        if not _is_number(spec[key]):
            bad(f"'spec.{key}' must be a number")
    if spec.get('irrigation_litres') is not None and not _is_number(spec['irrigation_litres']):
        bad("'spec.irrigation_litres' must be a number or null")
    for key in ('water', 'formula', 'store', 'mode'):
        value = spec[key] if key == 'mode' else data[key]
        if not isinstance(value, str):
            bad(f"'{'spec.' if key == 'mode' else ''}{key}' must be text")
    for key in ('water_share', 'ph'):
        if not _is_number(data[key]):
            bad(f'{key!r} must be a number')
    limits = data['limits']
    if not isinstance(limits, dict) or not all(_is_number(v) for v in limits.values()):
        bad("'limits' must be an object of ion: mg/L")
    acids = data['acids']
    if 'reagent_store' in data and (
        not isinstance(data['reagent_store'], str) or not data['reagent_store'].strip()
    ):
        bad("'reagent_store' must name an available reagent list or catalogue")
    if not isinstance(acids, list) or not all(isinstance(a, str) for a in acids):
        bad("'acids' must be a list of names")
    if 'depth' in data and (type(data['depth']) is not int or data['depth'] not in (1, 2, 3)):
        bad("'depth' must be 1, 2 or 3")
    if not isinstance(data.get('formula_title', ''), str):
        bad("'formula_title' must be text")
    confirmed = data.get('confirmed_products', [])
    if not isinstance(confirmed, list) or not all(isinstance(i, str) and i for i in confirmed):
        bad("'confirmed_products' must be a list of catalogue IDs")
    cap = data.get('max_solid_reagent_grams')
    if cap is not None and (not _is_number(cap) or cap < 0):
        bad("'max_solid_reagent_grams' must be nonnegative")
    check_saved_state(data)
    return data


def load_session(path):
    """A checked session from its file."""
    return check_session(read_json(path, 'session'), path)


def find_session(store, spec):
    """A session file by path, or by its saved name typed any way ('Tomato Stage.1' finds
    tomato-stage-1)."""
    for candidate in (
        Path(spec),
        Path(spec + '.json'),
        store.root / spec,
        store.root / (spec + '.json'),
    ):
        if candidate.is_file():
            return candidate
    name = spec.replace('\\', '/').split('sessions/', 1)[-1]
    try:
        candidate = store.path('sessions', slug(name))
    except DeliveryError:
        candidate = None
    if candidate is not None and candidate.is_file():
        return candidate
    saved = store.list('sessions')
    raise DeliveryError(
        'unknown_item',
        f'no saved session {spec!r}. '
        + ('Saved: ' + ', '.join(saved) if saved else 'Nothing is saved yet: run flahax mix'),
    )


def summarize(summary, say):
    """The grower depth in the terminal: status and reasons, tanks, grams and the acid."""
    from .canonical_result import verify_summary

    verify_summary(summary)
    identity = summary.get('calculation_identity') or {}
    if identity.get('result_id'):
        say('Calculation reference: ' + identity['result_id'])
    volumes, ratio = summary['volumes'], summary['tanks']['injection_ratio']
    blocked = summary['status'] == 'blocked'
    say(f'FlahaX {__version__}: {summary["title"]} - {STATUS_WORDS[summary["status"]]}')
    if summary['status'] == 'requires_review' and 'formulation' in summary:
        say(_review_reason(summary))
    for reason in map(readable, key_reasons(summary)):
        if len(reason) > 160:
            reason = reason[:150].rstrip() + ' ... (full text on the batch sheet)'
        say(f'  ! {reason}')
    if len(summary['warnings']) > 3:
        say(
            f'  ... {len(summary["warnings"]) - 3} more notes: choose output 2 or 3 to see them '
            f'all'
        )
    say(f'Irrigation supplied: {number(volumes["irrigation_litres"], 0)} L at 1:{ratio:g}')
    for tank in summary['tanks']['tanks']:
        name = tank['name']
        say(
            f'Tank {name}: '
            + (
                'not to be prepared (do not mix)'
                if blocked
                else f'prepare {litres(volumes["prepared_litres"][name])} L in your '
                f'{litres(volumes["capacity_litres"][name])} L tank{limited_by(volumes)}'
                + ('' if tank['acid_allowed'] else '; no acid')
            )
        )
        for product in tank['products']:
            say(
                f'  {"-" if blocked or display_residue(product["gramsPerBatch"]) else "[ ]"} '
                f'{product["name"]}: '
                f'{grams(product["gramsPerBatch"])}'
            )
    selected = summary['ph'] and summary['ph']['selected']
    if (
        selected
        and not blocked
        and (summary['ph'].get('direction') == 'none' or selected['volume_ml_per_batch'] is None)
    ):
        say(_reagent_line(summary))
    elif selected and not blocked:
        acid = selected.get('direction') == 'acid'
        say(f'pH reagent: {selected["product"]}')
        for line in reagent_preparation_lines(summary):
            say(line)
        if acid:
            say('Add acid to water, never water to acid.')
    elif not blocked:
        say(
            'pH reagent: none planned'
            + (
                f'. {summary["ph"]["message"]}'
                if summary['ph'] and summary['ph'].get('message')
                else '; measure pH after mixing.'
            )
        )


def output_folder(output, name):
    """The folder for the sheets: ``output`` or ./flahax-mix-<name>, numbered if it exists."""
    folder = Path(output) if output else Path.cwd() / f'flahax-mix-{name}'
    stem, n = folder, 1
    while folder.exists():
        n += 1
        folder = stem.with_name(f'{stem.name}-{n}')
    return folder


def write_sheets(summary, session, output):
    """Write the batch sheet, the summary and (full depth) the report; returns the file names."""
    depth = session.get('depth', 1)
    files = {
        'batch-sheet.html': render_mix_sheet(summary, depth),
        'summary.json': render(summary)['summary.json'],
    }
    if depth >= 3:
        files['report.html'] = render_report(summary)
    output.mkdir(parents=True)
    for file, content in files.items():
        (output / file).write_bytes(content.encode('utf-8'))
    return list(files)


def saved_line(store, name):
    """The line that says where the answers were saved and how to run them again."""
    return (
        f'Saved the answers as {store.path("sessions", name)}; next time: flahax mix '
        f'sessions/{name}'
    )


def use_tui(plain, ask, say, stdin=None, stdout=None):
    """True when ``flahax mix`` should open the full-screen wizard instead of the line mode."""
    if plain or ask is not input or say is not print:
        return False
    return supported(stdin or sys.stdin, stdout or sys.stdout)


def main(argv=None, *, ask=input, say=print, store=None):
    """The ``flahax mix`` command: interview or saved session, then the sheets; returns the process
    exit code.
    """
    parser = argparse.ArgumentParser(
        prog='flahax mix',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'session',
        nargs='*',
        help='a saved session, e.g. tomato-ro (flahax mix sessions lists them)',
    )
    parser.add_argument(
        '--output', help='new directory for the sheets (default: ./flahax-mix-<session>)'
    )
    parser.add_argument(
        '--plain',
        action='store_true',
        help='line-by-line questions instead of the full-screen wizard',
    )
    parser.add_argument(
        '--review-reagents',
        action='store_true',
        help='review a saved session\'s available acids and bases and save new answers',
    )
    args = parser.parse_args(argv)
    if args.output and Path(args.output).exists():
        say(f'flahax mix: {args.output} already exists; choose a new directory')
        return 1
    store = store or Store()
    p = Prompts(ask, say)
    args.session = ' '.join(args.session)
    if args.review_reagents and not args.session:
        parser.error('--review-reagents requires a saved session')
    if args.session.strip('/\\') == 'sessions':
        saved = store.list('sessions')
        say(
            'Saved sessions: ' + ', '.join(saved)
            if saved
            else 'Nothing is saved yet: run flahax mix'
        )
        return 0
    if use_tui(args.plain, ask, say):
        from .mix_tui import run_tui  # mix_tui imports this module

        code, lines = run_tui(
            store, args.session or None, args.output, review_availability=args.review_reagents
        )
        if code is not None:
            for line in lines:
                say(line)
            return code
    try:
        if args.session:
            path = find_session(store, args.session)
            name, session = path.stem, load_session(path)
            if args.review_reagents:
                name, session = review_reagents(p, store, name, session)
        else:
            say(
                f'FlahaX {__version__} mix: five steps. Enter keeps the value in brackets; '
                f'Ctrl+C stops.'
            )
            name, session, pending = interview(p, store)
            for kind, item, data in pending:
                store.save(kind, item, data)
            say(saved_line(store, name))
    except (KeyboardInterrupt, EOFError):
        say('Stopped; nothing saved.')
        return 1
    except (DeliveryError, ValueError, OSError) as exc:
        say(f'flahax mix: {exc}')
        return 1
    output = output_folder(args.output, name)
    try:
        summary = run_batch(options_for(store, session))
    except (DeliveryError, ValueError, OSError, KeyError) as exc:
        say(f'flahax mix: {exc}')
        return 1
    files = write_sheets(summary, session, output)
    summarize(summary, say)
    say(f'Wrote {", ".join(files)} to {output}')
    return 3 if summary['status'] == 'blocked' else 0
