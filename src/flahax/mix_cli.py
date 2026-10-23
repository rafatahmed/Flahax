"""``flahax mix``: five questions, then tank A, tank B and the acid.

    flahax mix                    ask the five steps, save the answers, write the sheets
    flahax mix sessions/NAME      run a saved session again without questions

Steps: 1/5 specification (tanks, injection ratio, temperature, how stock is
prepared), 2/5 water analysis, 3/5 crop formula, 4/5 fertilizers and acids, 5/5
target pH. Defaults are shown in brackets; Enter keeps them. Typed items are saved
under ``$FLAHAX_HOME`` (else ``~/.flahax``) as files ``flahax batch`` reads, and only
once every step is answered: Ctrl+C or end of input saves nothing.
"""
import argparse
from datetime import date
import json
import math
from pathlib import Path

from . import __version__
from .batch_cli import BatchOptions, limit_entry, render, run_batch
from .composition import ION_BALANCE_WARNING_PCT, target_ion_balance
from .delivery_contracts import DeliveryError
from .engine import load_library
from .grower_report import number, render_report
from .grower_sheet import STATUS_WORDS, key_reasons, litres, render_mix_sheet  # noqa: F401 (STATUS_WORDS re-exported)
from .materials import declared_ions_check, load_identities, make_grade, resolve_material
from .mix_store import Store, slug
from .mix_water import MICROS, WATER_IONS, ask_analysis, to_elements  # noqa: F401 (re-exported)
from .stock_volumes import prepare_stocks

FORMULA_KEYS = ('N_NO3', 'N_NH4', 'P', 'K', 'Ca', 'Mg', 'S', 'Fe', 'Mn', 'Zn', 'Cu', 'B', 'Mo')
COMPOUND_KEYS = (('N_NO3', 'Nitric N'), ('N_NH4', 'Ammoniacal N'), ('N_UREA', 'Ureic N'), ('P2O5', 'P2O5'),
                 ('K2O', 'K2O'), ('CaO', 'CaO'), ('MgO', 'MgO'), ('SO3', 'SO3')) + tuple(
                     (m, m) for m in MICROS) + (('Na', 'Na'), ('Cl', 'Cl'))
CHELATES = ('EDTA', 'DTPA', 'o,o-EDDHA', None)


class Prompts:
    def __init__(self, ask, say):
        self.ask, self.say = ask, say

    def text(self, prompt, default=None):
        while True:
            shown = '' if default is None else f' [{default or "none"}]'
            answer = self.ask(f'{prompt}{shown}: ').strip()
            if answer:
                return answer
            if default is not None:
                return default
            self.say('  This one is needed.')

    def number(self, prompt, default=None, *, blank=False, low=0.0, high=None, positive=False):
        while True:
            shown = f' [{default:g}]' if default is not None else ' (Enter if blank)' if blank else ''
            answer = self.ask(f'{prompt}{shown}: ').strip()
            if not answer and (default is not None or blank):
                return default
            try:
                value = float(answer)
            except ValueError:
                self.say(f'  {answer!r} is not a number.')
                continue
            if not math.isfinite(value) or value < low or (positive and value <= low) \
                    or (high is not None and value > high):
                self.say(f'  Enter a number {"above" if positive else "from"} {low:g}'
                         + (f' up to {high:g}.' if high is not None else '.'))
                continue
            return value

    def choose(self, prompt, options, default=1):
        """0-based index of the chosen option; with ``default=None`` Enter asks again."""
        if prompt:
            self.say(prompt)
        for i, option in enumerate(options, 1):
            self.say(f'  {i}  {option}')
        while True:
            answer = self.ask(f'Number [{default}]: ' if default else 'Number: ').strip() or str(default)
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return int(answer) - 1
            self.say(f'  Choose 1 to {len(options)}.')

    def search(self, prompt, names):
        """Part of a name narrows the list; Enter shows every name to choose from by number."""
        while True:
            query = self.ask(f'{prompt} (part of the name; Enter lists all {len(names)}): ').strip().lower()
            matches = [n for n in names if query in n.lower()]
            if len(matches) == 1:
                self.say(f'  {matches[0]}')
                return matches[0]
            if matches:
                return matches[self.choose(f'{len(matches)} match:', matches)]
            self.say(f'  Nothing matches {query!r}; press Enter to see the whole list.')

    def new_name(self, store, kind, prompt, default=None):
        while True:
            name = slug(self.text(prompt, default))
            if name not in store.list(kind) or self.choose(f'A saved {kind[:-1]} named {name} exists.',
                                                           ['Use another name', 'Replace it']) == 1:
                return name

    def document(self, supplier):
        while True:
            issued = self.text('Date on the sheet (YYYY-MM-DD)')
            try:
                date.fromisoformat(issued)
                break
            except ValueError:
                self.say('  Use the form 2025-03-28.')
        return {'supplier': supplier, 'title': self.text('Sheet title'), 'issued': issued,
                'entered': date.today().isoformat()}


def ask_spec(p):
    p.say('1/5 Specification')
    a = p.number('Tank A capacity, L', 1000, positive=True)
    b = p.number('Tank B capacity, L', 1000, positive=True)
    tanks = {'A': a, 'B': b, 'acid': p.number('Acid container capacity, L', min(a, b), positive=True)}
    ratio = p.number('Injection ratio, litres of irrigation per litre of stock', 100, positive=True)
    temperature = p.number('Stock temperature, °C', 25, high=60)
    once = p.choose('How is stock prepared?', ['Fill the tanks full and run several irrigations from them',
                                               'Make just enough for one irrigation']) == 1
    while True:
        irrigation = p.number('Irrigation, L', positive=True) if once else None
        try:
            volumes = prepare_stocks(tank_litres=tanks, ratio=ratio, mode='once' if once else 'fill',
                                     irrigation_litres=irrigation)
            break
        except DeliveryError as exc:
            p.say(f'  {exc}')
    p.say(f'  {number(volumes.irrigation_litres, 0)} L of irrigation; prepare '
          f'{litres(volumes.prepared_litres["A"])} L in each container.')
    return dict(tank_litres=tanks, ratio=ratio, temperature_c=temperature, mode='once' if once else 'fill',
                irrigation_litres=irrigation)


def ask_water(p, store, pending):
    p.say('2/5 Water analysis')
    saved = store.list('waters')
    pick = p.choose('Water', ['RO water (no ions)'] + saved + ['A new analysis'])
    ref, share = 'ro', 100.0
    if 0 < pick <= len(saved):
        ref = saved[pick - 1]
    elif pick > len(saved):
        ref, data = ask_analysis(p, store)
        pending.append(('waters', ref, data))
    if ref != 'ro':
        share = p.number('Share of this water in the irrigation, % (the rest RO)', 100, high=100, positive=True)
    while True:
        answer = p.text('Concentration limits in the final solution, mg/L, e.g. Na=69 Cl=106', '')
        try:
            limits = dict(limit_entry(item) for item in answer.replace(',', ' ').split())
            return ref, share, limits
        except argparse.ArgumentTypeError as exc:
            p.say(f'  {exc}')


def ask_formula(p, store, pending, library):
    p.say('3/5 Crop formula: the nutrient targets in mg/L (your fertilizers come in step 4)')
    saved = store.list('formulas')
    packaged = {f['name']: f['targets'] for f in library['formulas']}
    pick = p.choose('Formula', ['A packaged formula', 'Start from a packaged formula and change it'] + saved
                    + ['Type a new one'])
    if pick < 2:
        ref = p.search('Crop formula', list(packaged))
        targets = dict(packaged[ref])
        if pick == 1:
            changed = {k: p.number(f'{k}, mg/L', v) for k, v in targets.items()}
            if changed != targets:
                targets, ref = changed, p.new_name(store, 'formulas', 'Save the changed formula as', f'{ref} changed')
                pending.append(('formulas', ref, targets))
    elif pick < 2 + len(saved):
        ref = saved[pick - 2]
        targets = store.load('formulas', ref)
    else:
        ref = p.new_name(store, 'formulas', 'Name of the new formula')
        p.say('Targets in mg/L; nitrogen as NO3-N and NH4-N. Enter leaves a nutrient untargeted.')
        targets = {k: v for k in FORMULA_KEYS if (v := p.number(f'{k}, mg/L', blank=True)) is not None}
        pending.append(('formulas', ref, targets))
    balance = target_ion_balance(targets)
    p.say(f'Formula balance: cations {balance["cationsMeqPerL"]:.2f} meq/L, anions {balance["anionsMeqPerL"]:.2f} '
          f'meq/L ({balance["imbalancePercent"]:+.1f} %).')
    if balance['exceedsWarning']:
        p.say(f'Warning (targetIonBalance): the formula is {abs(balance["imbalancePercent"]):.1f} % out of balance, '
              f'beyond {ION_BALANCE_WARNING_PCT:g} %; no set of salts meets every target, and unlisted counter-ions '
              'will make up the difference.')
    return ref, targets


def ask_notes(p):
    """Data-sheet compatibility notes, kept with the grade for the full report; ';' separates several."""
    answer = p.text("Notes from the data sheet, e.g. 'tank pH above 4' (Enter = none)", '')
    return [note.strip() for note in answer.split(';') if note.strip()]


def add_single(p, catalogue):
    names = {s['name']: s for s in catalogue}
    identities = [i for i in load_identities().values() if any(n in names for n in i['products'])]
    labels = {f'{i["name"]} ({", ".join(i["products"])})': i for i in identities}
    identity = labels[p.search('Chemical, e.g. calcium nitrate', list(labels))]
    product = identity['products'][0] if len(identity['products']) == 1 else \
        identity['products'][p.choose('Catalogue product', identity['products'])]
    shipped = names[product]
    brand = p.text('Brand name on the label')
    supplier = p.text('Supplier')
    document = p.document(supplier)
    p.say('Label analysis, % w/w; Enter keeps the reference value.')
    analysis = {k: {'typical': p.number(f'{k}, %', round(v, 3), high=100)} for k, v in shipped['elements'].items()}
    grade = {'grade_id': f'grd-{slug(brand)}', 'identity_id': identity['id'], 'supplier': supplier,
             'product': brand, 'composition': 'single', 'document': document, 'analysis': analysis,
             'compatibility_notes': ask_notes(p)}
    try:
        material = resolve_material(product, grade=make_grade(grade))
    except DeliveryError as exc:
        p.say(f'Not added: {exc}')
        return None
    if 'identity_inconsistent' in material.flags:
        p.say(f'Not added (identity_inconsistent): the label of {brand} does not match {identity["name"]}. '
              'Check the label values, or use the catalogue grade.')
        return None
    p.say(f'Added {brand} as {product}.')
    return dict(shipped, id=material.record['id'], elements=material.record['elements'], grade=grade)


def add_compound(p):
    name = p.text('Product name on the data sheet')
    supplier = p.text('Supplier')
    record = {'supplier': supplier, 'product': name, 'composition': 'declared_ions', 'document': p.document(supplier)}
    record['grade_id'] = f'grd-{slug(name)}-{record["document"]["issued"]}'
    p.say('Composition as printed, % w/w (oxides as oxides). Enter if the sheet does not state it.')
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
    p.say('Full chemistry: the label balances.' if check.modellable else
          f'Not modellable: {check.reason}. It can be formulated, but no pH reagent will be planned with it.')
    return {'id': material.record['id'], 'name': name, 'formula': None, 'elements': material.record['elements'],
            'grade': record}


def ask_products(p, store, pending, library):
    p.say('4/5 Fertilizers available')
    catalogue, saved = library['salts'], store.list('stores')
    pick = p.choose('Fertilizers', ['The whole catalogue'] + saved + ['Tick what I have'])
    if pick == 0:
        ref, products = 'catalogue', list(catalogue)
    elif pick <= len(saved):
        ref = saved[pick - 1]
        products = store.load('stores', ref)
    else:
        ref = None
        for i, s in enumerate(catalogue, 1):
            p.say(f'  {i:2}  {s["name"]}')
        while True:
            picked = p.text('Numbers of the products you have, separated by spaces').replace(',', ' ').split()
            if all(n.isdigit() and 1 <= int(n) <= len(catalogue) for n in picked):
                products = [catalogue[int(n) - 1] for n in dict.fromkeys(picked)]
                break
            p.say(f'  Use numbers 1 to {len(catalogue)}.')
    added = False
    while kind := p.choose('Add a product?', ['No', 'A single chemical with its label analysis',
                                              'A compound from its data sheet']):
        record = add_single(p, catalogue) if kind == 1 else add_compound(p)
        if record is not None:
            products, added = [x for x in products if x['name'] != record['name']] + [record], True
    if ref is None or added:
        ref = p.new_name(store, 'stores', 'Save this product list as', 'my fertilizers')
        pending.append(('stores', ref, products))
    return ref, products


def ask_acids(p, store, pending):
    chosen, saved = [], store.list('acids')
    while True:
        offer = [s for s in saved if s not in chosen]
        options = offer + ['A new acid from its certificate', 'Done' if chosen else 'No acid']
        pick = p.choose('Acids for the pH plan', options, len(options) if chosen else 1)
        if pick < len(offer):
            chosen.append(offer[pick])
        elif pick == len(offer):
            formula = p.text('Acid formula (HNO3, H3PO4, H2SO4)', 'HNO3')
            fraction = p.number('Assay on the certificate, % w/w', positive=True, high=100) / 100
            density = p.number('Density on the certificate, kg/L', positive=True)
            while ':' in (name := p.text('Name', f'{formula} {fraction:.0%}')):
                p.say('  A name cannot contain ":".')
            ref = p.new_name(store, 'acids', 'Save as', name) if slug(name) in saved else slug(name)
            pending.append(('acids', ref, {'formula': formula, 'fraction': fraction, 'density': density,
                                           'name': name}))
            chosen.append(ref)
        else:
            return chosen


def options_for(store, session):
    """``BatchOptions`` from a session; every saved item it names must exist."""
    def path(kind, name):
        file = store.path(kind, name)
        if not file.is_file():
            raise DeliveryError('unknown_item', f'the session needs the saved {kind[:-1]} {name!r} ({file})')
        return str(file)
    spec, packaged = session['spec'], {f['name'] for f in load_library()['formulas']}
    acids = [store.load('acids', a) for a in session['acids']]
    return BatchOptions(
        water='ro' if session['water'] == 'ro' else path('waters', session['water']),
        formula=session['formula'] if session['formula'] in packaged else None,
        targets=None if session['formula'] in packaged else path('formulas', session['formula']),
        water_share=None if session['water_share'] >= 100 else session['water_share'],
        ph=session['ph'], ratio=spec['ratio'],
        acid=[f'{a["formula"]}:{a["fraction"]}:{a["density"]}:{a["name"]}' for a in acids],
        limit=list(session['limits'].items()),
        products=None if session['store'] == 'catalogue' else path('stores', session['store']),
        tank_litres=spec['tank_litres'], mode=spec['mode'], irrigation_litres=spec['irrigation_litres'],
        temperature_c=spec['temperature_c'], depth=session.get('depth', 1))


def interview(p, store):
    """The five steps; returns (session name, session, items to save). Nothing is written here."""
    library, pending = load_library(), []
    spec = ask_spec(p)
    water, share, limits = ask_water(p, store, pending)
    formula, _ = ask_formula(p, store, pending, library)
    product_store, _ = ask_products(p, store, pending, library)
    acids = ask_acids(p, store, pending)
    p.say('5/5 pH requirement')
    ph = p.number('Target pH of the final solution', 5.8, high=14, positive=True)
    depth = 1 + p.choose('Output depth', ['Grower: tanks A and B, and the acid',
                                          'Agronomist: adds the nutrient table and the pH path', 'Full report'])
    name = p.new_name(store, 'sessions', 'Save these answers as', f'{formula} {water}')
    session = {'spec': spec, 'water': water, 'water_share': share, 'limits': limits, 'formula': formula,
               'store': product_store, 'acids': acids, 'ph': ph, 'depth': depth}
    return name, session, pending + [('sessions', name, session)]


def find_session(store, spec):
    for candidate in (Path(spec), Path(spec + '.json'), store.root / spec, store.root / (spec + '.json')):
        if candidate.is_file():
            return candidate
    raise DeliveryError('unknown_item', f'no session file {spec!r} (looked here and in {store.root / "sessions"})')




def summarize(summary, say):
    """The grower depth in the terminal: status and reasons, tanks, grams and the acid."""
    volumes, ratio = summary['volumes'], summary['tanks']['injection_ratio']
    blocked = summary['status'] == 'blocked'
    say(f'FlahaX {__version__}: {summary["title"]} - {STATUS_WORDS[summary["status"]]}')
    for reason in key_reasons(summary):
        say(f'  ! {reason if len(reason) <= 160 else reason[:150].rstrip() + " ... (full text on the batch sheet)"}')
    if len(summary['warnings']) > 3:
        say(f'  ... {len(summary["warnings"]) - 3} more notes: choose output 2 or 3 to see them all')
    say(f'Irrigation supplied: {number(volumes["irrigation_litres"], 0)} L at 1:{ratio:g}')
    for tank in summary['tanks']['tanks']:
        name = tank['name']
        say(f'Tank {name}: ' + ('not to be prepared (do not mix)' if blocked else
            f'prepare {litres(volumes["prepared_litres"][name])} L in your '
            f'{litres(volumes["capacity_litres"][name])} L tank' + ('' if tank['acid_allowed'] else '; no acid')))
        for product in tank['products']:
            say(f'  {"-" if blocked else "[ ]"} {product["name"]}: {number(product["gramsPerBatch"], 1)} g')
    selected = summary['ph'] and summary['ph']['selected']
    if selected and not blocked:
        say(f'Acid container: {number(selected["volume_ml_per_batch"], 0)} mL {selected["product"]}, added to water '
            f'and made up to {litres(volumes["prepared_litres"]["acid"])} L (acid to water, never water to acid)')
    elif not blocked:
        say('pH reagent: none planned' + (f'. {summary["ph"]["message"]}' if summary['ph'] and
                                          summary['ph'].get('message') else '; measure pH after mixing.'))


def main(argv=None, *, ask=input, say=print, store=None):
    parser = argparse.ArgumentParser(prog='flahax mix', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('session', nargs='?', help='a saved session file, e.g. sessions/tomato-ro')
    parser.add_argument('--output', help='new directory for the sheets (default: ./flahax-mix-<session>)')
    args = parser.parse_args(argv)
    if args.output and Path(args.output).exists():
        say(f'flahax mix: {args.output} already exists; choose a new directory')
        return 1
    store = store or Store()
    p = Prompts(ask, say)
    try:
        if args.session:
            path = find_session(store, args.session)
            name, session = path.stem, json.loads(path.read_text(encoding='utf-8-sig'))
        else:
            say(f'FlahaX {__version__} mix: five steps. Enter keeps the value in brackets; Ctrl+C stops.')
            name, session, pending = interview(p, store)
            for kind, item, data in pending:
                store.save(kind, item, data)
            say(f'Saved the answers as {store.path("sessions", name)}; next time: flahax mix sessions/{name}')
    except (KeyboardInterrupt, EOFError):
        say('Stopped; nothing saved.')
        return 1
    except (DeliveryError, ValueError, OSError) as exc:
        say(f'flahax mix: {exc}')
        return 1
    output = Path(args.output) if args.output else Path.cwd() / f'flahax-mix-{name}'
    stem, n = output, 1
    while output.exists():
        n += 1
        output = stem.with_name(f'{stem.name}-{n}')
    try:
        summary = run_batch(options_for(store, session))
    except (DeliveryError, ValueError, OSError, KeyError) as exc:
        say(f'flahax mix: {exc}')
        return 1
    depth = session.get('depth', 1)
    files = {'batch-sheet.html': render_mix_sheet(summary, depth), 'summary.json': render(summary)['summary.json']}
    if depth >= 3:
        files['report.html'] = render_report(summary)
    output.mkdir(parents=True)
    for file, content in files.items():
        (output / file).write_bytes(content.encode('utf-8'))
    summarize(summary, say)
    say(f'Wrote {", ".join(files)} to {output}')
    return 3 if summary['status'] == 'blocked' else 0
