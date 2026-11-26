# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""What a batch summary says, in words and display rows: reasons, qualifications,
reagent lines and the limit, solubility and dose rows the reports show."""

from decimal import Decimal
from fractions import Fraction

from .report_format import grams, litres, millilitres, number, text
from .requirement_fit import RELATIVE_TOLERANCE, ZERO_TARGET_TOLERANCE_MG_PER_L, met


def ph_goal(summary, digits=2):
    """The pH the batch is planned to: a point, or "low to high" for an acceptable interval."""
    interval = summary.get('target_ph_interval')
    if interval:
        return f'{number(interval[0], digits)} to {number(interval[1], digits)}'
    return number(summary['target_ph'], digits)


def nitrogen_notes(summary):
    """Plain lines for the nutrient table: the ammonium allowance when
    it applies (G23) and total N when the formula declares nitrogen
    (D1).
    """
    formulation = summary['formulation']
    notes = []
    allowance = formulation.get('ammonium_allowance')
    if allowance:
        notes.append(
            f'Incidental NH4-N allowed up to {number(allowance["mgPerL"], 2)} mg/L '
            f'({number(allowance["fractionOfTotalN"] * 100, 2)} % of total N, cap '
            f'{number(allowance["absoluteCapMgPerL"], 2)} mg/L): {allowance["basis"]}'
        )
    total = formulation.get('total_n')
    if total and total['target'] is not None:
        status = 'a declared target' if total.get('fitted') else 'reported, not a target'
        notes.append(
            f'Total N: {number(total["final"], 2)} mg/L '
            f'(sum of NO3-N, NH4-N and urea-N; {status})'
        )
    return notes


def nitrogen_paragraphs(summary):
    """``nitrogen_notes`` as small HTML paragraphs."""
    return ''.join(f'<p class="small">{text(note)}</p>' for note in nitrogen_notes(summary))


def extra_tank_note(grouping, available):
    """Say which pair, and which rule, needs a tank beyond the
    ``available`` ones.
    """
    names = [[p.name for p in t.products] for t in grouping.tanks]
    why = {frozenset((a, b)): reason for a, b, reason in grouping.separations}
    extra = names[available][0]
    ordinal = {1: 'second', 2: 'third', 3: 'fourth'}.get(available, f'{available + 1}th')
    for earlier in names[:available]:
        for name in earlier:
            if frozenset((extra, name)) in why:
                return (
                    f'Stock assignment needs a {ordinal} tank: {extra} cannot share with '
                    f'{name} ({why[frozenset((extra, name))]}). No separation is waived.'
                )
    return (
        f'Stock assignment needs {len(names)} tanks; only {available} supplied. '
        'No separation is waived.'
    )


STATUS_WORDS = {
    'ready': 'calculation complete',
    'requires_review': 'review required',
    'blocked': 'do not mix',
}


STATUS_TEXT = {
    'ready': ('ok', 'Calculation checks passed; physical validation remains separate.'),
    'requires_review': ('warn', 'Review required: unresolved qualifications remain.'),
    'blocked': ('stop', 'Not usable as planned: see the blocked stages and warnings.'),
}


_NUTRIENT_NAMES = {
    'N_NO3': 'nitrate nitrogen',
    'N_NH4': 'ammonium nitrogen',
    'N_UREA': 'urea nitrogen',
    'P': 'phosphorus',
    'K': 'potassium',
    'Ca': 'calcium',
    'Mg': 'magnesium',
    'S': 'sulfur',
    'Fe': 'iron',
    'Zn': 'zinc',
    'Mn': 'manganese',
    'B': 'boron',
    'Cu': 'copper',
    'Mo': 'molybdenum',
    'Si': 'silicon',
    'Na': 'sodium',
    'Cl': 'chloride',
}


def _magnitude(value):
    """Four significant digits, in decimal notation even for a small
    nonzero miss.
    """
    return format(Decimal(format(abs(value), '.4g')), 'f')


def miss_difference(target, final):
    """The signed gap between a final and a target concentration, in words."""
    delta = final - target
    sign = '+' if delta > 0 else '-'
    absolute = f'{sign}{_magnitude(delta)} mg/L'
    if target == 0:
        return absolute + '; relative difference undefined (zero target)'
    return f'{absolute} ({sign}{_magnitude(100 * delta / target)}%)'


def missed_rows(summary):
    """The formulation rows whose final concentration misses the target."""
    return [
        r
        for r in summary['formulation']['rows']
        if r['target'] is not None and not met(r['target'], r['final'])
    ]


def review_reason(summary):
    """Why a batch needs review, quoting the weighed recipe."""
    formulation = summary['formulation']
    misses = missed_rows(summary)
    if misses:
        row = max(misses, key=lambda r: abs(r['final'] - r['target']))
        delta = row['final'] - row['target']
        name = _NUTRIENT_NAMES.get(row['symbol'], row['symbol'])
        reasons = [
            f'{name[:1].upper() + name[1:]} is {_magnitude(delta)} mg/L '
            f'{"above" if delta > 0 else "below"} target.'
        ]
        if len(misses) > 1:
            reasons.append(f'{len(misses)} nutrient targets missed in total.')
    else:
        reasons = ['All nutrient targets met.']
    incidental = formulation.get('incidental_review')
    if incidental is None:  # Previously saved reports lack the itemized assessment.
        limited = {r['symbol'] for r in summary['limits']}
        if formulation.get('ammonium_allowance'):
            limited.add('N_NH4')
        incidental = [
            r['symbol']
            for r in formulation['rows']
            if r['target'] is None and r['final'] > 0 and r['symbol'] not in limited
        ]
    for symbol in incidental:
        name = _NUTRIENT_NAMES.get(symbol, symbol)
        reasons.append(f'{name[:1].upper() + name[1:]} has no declared maximum.')
    ph = summary.get('ph') or {}
    if ph.get('unadjusted_ph') is None:
        reasons.append('pH adjustment could not be verified.')
    chemistry = summary['stages'].get('chemistry', {})
    if chemistry.get('status') == 'requires_review' and chemistry.get('message'):
        reasons.append(chemistry['message'])
    for limit in summary['limits']:
        if limit['balancingChangesDecision']:
            reasons.append(limit['note'])
    unchecked = [
        r.get('product') or 'an unidentified product'
        for r in summary['solubility']
        if r['status'] == 'not_checked'
    ]
    if unchecked:
        reasons.append('Stock solubility was not checked for ' + ', '.join(unchecked) + '.')
    if summary['tanks'].get('mixture_approved') is False:
        reasons.append('Mixed-stock solubility is unverified.')
    return ' '.join(reasons)


def requested_ec_note(requested, ec):
    """How a requested EC (mS/cm) sits against the estimated range, or
    None without a request.
    """
    if requested is None or not ec or not ec.get('ec25_range_ms_cm'):
        return None
    low, high = ec['ec25_range_ms_cm']
    if low <= requested <= high:
        return 'compatible with the estimated range; target attainment unverified'
    distance = low - requested if requested < low else requested - high
    return f'requested {requested:.2f} mS/cm is {distance:.2f} mS/cm from the estimated range'


def status_explanations(summary):
    """Explain independent status scopes without changing calculation or
    acceptance flags.
    """
    explanations = {}
    numerical = (summary.get('statuses') or {}).get('numerical')
    if numerical == 'stationary_point':
        explanations['numerical'] = (
            'Search reached local stationarity; this is not proof of a global optimum.'
        )
    formulation = summary.get('formulation') or {}
    if 'targets_met' in formulation:
        criterion = formulation.get('match_criterion') or dict(
            relative=RELATIVE_TOLERANCE, zero_target_mg_per_l=ZERO_TARGET_TOLERANCE_MG_PER_L
        )
        rule = (
            f'A target is met within {criterion["relative"]:g} of the target '
            f'(relative), or {criterion["zero_target_mg_per_l"]:g} mg/L for a declared zero.'
        )
        explanations['formulation'] = (
            f'All nutrient targets are met. {rule} Other review reasons remain separate.'
            if formulation['targets_met']
            else f'Nutrient targets are not all met. {rule} '
            'This does not prove that no recipe can meet them.'
        )
    if any(r.get('status') == 'search_incomplete' for r in formulation.get('unmet', [])):
        explanations['nutrients'] = (
            'Nutrient-level search_incomplete describes a separate nutrient feasibility '
            'diagnosis; '
            'it is not the joint search stopping reason.'
        )
    return explanations


def qualification_lines(summary):
    """Keep model applicability and physical validation distinct from
    feasibility.
    """
    lines = [
        'Planning calculation; physical validation is not established by this report.',
    ]
    for name, status in (summary.get('statuses') or {}).items():
        lines.append(f'{name}: {status}')
    lines.extend((summary.get('status_explanations') or status_explanations(summary)).values())
    ec = summary.get('ec')
    if not ec:
        return lines + ['EC: not evaluated; no estimate or uncertainty interval available.']
    lines.append(f"EC status: {ec.get('status', 'not reported')}")
    said = summary.get('warnings') or ()
    for key in ('reason', 'qualifier'):
        if ec.get(key) and ec[key] not in said:  # a warning already states it once
            lines.append(f"EC {key}: {ec[key]}")
    if ec.get('status') == 'estimated' and ec.get('ec25_ms_cm') is not None:
        lines.append(f"EC25 calculated estimate: {ec['ec25_ms_cm']} mS/cm.")
    if ec.get('status') == 'range':
        low, high = ec['ec25_range_ms_cm']
        lines.append(f'Reported EC range: {low:.2f} to {high:.2f} mS/cm.')
    else:
        lines.append('EC uncertainty interval: not quantified.')
    lines.append(f"EC uncertainty components: {ec.get('uncertainty_components', 'not reported')}")
    audit = ec.get('audit') or {}
    for key in ('model', 'chemistrySha256', 'coefficientsSha256'):
        lines.append(f"EC {key}: {audit.get(key, 'not reported')}")
    if ec.get('missing_species'):
        lines.append(f"Uncovered EC species: {ec['missing_species']}")
    return lines


def reagent_amount(candidate):
    """Display a supported liquid volume, otherwise retain the reagent
    mass.
    """
    if candidate['volume_ml_per_batch'] is None:
        if candidate['mass_g_per_batch'] is None:
            return 'Not available'
        return grams(candidate['mass_g_per_batch'])
    return f"{millilitres(candidate['volume_ml_per_batch'])} mL"


def joint_verdict(summary):
    """The joint pH optimizer verdict as one sentence."""
    ph = summary.get('ph') or {}
    joint = (ph.get('selected') or {}).get('joint') or {}
    if not ph.get('selected') and ph.get('unadjusted_ph') is not None:
        return ph.get('message') or ''
    if joint.get('status') == 'sequential':
        return joint['reason']
    if 'chargeTolerance' not in joint:
        return ''
    counts = (
        f' ({joint["iterations"]} iterations, {joint["evaluations"]} evaluations)'
        if 'iterations' in joint and 'evaluations' in joint
        else ''
    )
    return (
        f'Before adjustment: pH {number(ph["unadjusted_ph"], 2)}, '
        f'target {number(ph["target_ph"], 2)}. '
        f'Search result: {joint["reason"].replace("_", " ")}{counts}. '
        f'Final pH check passed at {number(joint["finalPh"], 5)}. '
        f'Charge check passed: residual {joint["chargeResidual"]:.3g}, '
        f'limit {joint["chargeTolerance"]:.3g}. '
        f'Nutrient targets met: {"yes" if summary["formulation"]["targets_met"] else "no"}.'
    )


def reagent_preparation(summary):
    """Split the total liquid reagent dose into refills at the shared
    injection ratio.
    """
    ph, volumes = summary.get('ph') or {}, summary.get('volumes')
    chosen = ph.get('selected') or {}
    dose = chosen.get('volume_ml_per_batch')
    if (
        summary.get('status') == 'blocked'
        or not volumes
        or dose is None
        or ph.get('direction') == 'none'
    ):
        return None
    total = Fraction(str(volumes['prepared_litres']['A']))
    fill = Fraction(str(volumes['prepared_litres']['acid']))
    if Fraction(str(dose)) > total * 1000:
        return dict(
            status='blocked',
            message='The liquid reagent amount exceeds the available reagent stock volume '
            'at this injection ratio. Do not prepare this stock; use a suitable injection '
            'ratio or reagent and recalculate.',
        )
    fills = -(-total // fill)
    last = total - fill * (fills - 1)
    return dict(
        status='planned',
        injection_ratio=summary['tanks']['injection_ratio'],
        total_stock_litres=float(total),
        fill_litres=float(fill),
        last_fill_litres=float(last),
        fills=fills,
        refills=fills - 1,
        total_dose_ml=dose,
        dose_ml_per_fill=dose * float(fill / total),
        dose_ml_last_fill=dose * float(last / total),
    )


def reagent_preparation_lines(summary):
    """Describe per-fill quantities separately from the total batch
    reagent quantity.
    """
    if summary.get('status') == 'blocked':
        return []
    plan = reagent_preparation(summary)
    if plan is None:
        return []
    if plan['status'] == 'blocked':
        return [plan['message']]
    lines = [
        f'Total reagent for this batch: {millilitres(plan["total_dose_ml"])} mL.',
        f'Each full fill: add {millilitres(plan["dose_ml_per_fill"])} mL to water '
        f'and make up to {litres(plan["fill_litres"])} L.',
        f'Use {plan["fills"]} {"fill" if plan["fills"] == 1 else "fills"} total '
        f'({plan["refills"]} refills) '
        f'at 1:{number(plan["injection_ratio"])} injection.',
    ]
    if plan['last_fill_litres'] != plan['fill_litres']:
        lines.append(
            f'Final partial fill: add {millilitres(plan["dose_ml_last_fill"])} mL to water '
            f'and make up to {litres(plan["last_fill_litres"])} L.'
        )
    return lines


def reagent_line(summary):
    """The pH reagent line of a report or sheet."""
    ph = summary['ph']
    if summary.get('status') == 'blocked':
        return (
            'Blocked calculation: any reagent quantities are diagnostic only. '
            'Do not prepare this batch; resolve the recorded reasons and recalculate.'
        )
    if ph is None:
        return 'pH was not planned: supply complete water chemistry and pH reagents to plan it.'
    preparation = reagent_preparation(summary)
    if preparation and preparation['status'] == 'blocked':
        return preparation['message']
    chosen = ph['selected']
    if ph.get('direction') == 'none':
        return (
            f'The feed mixes at pH {number(ph["unadjusted_ph"], 2)}, '
            + (
                f'inside the acceptable interval {number(ph["interval"]["low"], 2)} to '
                f'{number(ph["interval"]["high"], 2)}. '
                if ph.get('interval')
                else f'within tolerance of {number(ph["target_ph"], 2)}. '
            )
            + 'No pH reagent is needed.'
        )
    if chosen is None and ph['unadjusted_ph'] is None:
        return (
            f'No pH reagent was planned. {ph["message"]}. Measure the pH after mixing and '
            f'adjust before use.'
        )
    if chosen is None:
        return (
            f'No acceptable pH reagent: the feed mixes at pH {number(ph["unadjusted_ph"], 2)} '
            f'and needs '
            f'{"an acid" if ph["direction"] == "acid" else "a base"} to reach '
            f'{number(ph["target_ph"], 2)}. '
            'See the candidates and their reasons.'
        )
    return (
        f'Add {reagent_amount(chosen)} of {chosen["product"]} '
        f'({chosen["formula"]}) per '
        f'{number(summary["batch_litres"], 0)} L to go from pH {number(ph["mixed_ph"], 2)} to '
        f'{number(ph["target_ph"], 2)}. Add it in steps and measure.'
    )


def limit_rows(s):
    """The declared maximum concentrations as table rows."""
    return [
        (
            row['symbol'],
            number(row['maximumPpm'], 2),
            number(row['analyticalPpm'], 2),
            'n/a' if row['modelledPpm'] is None else number(row['modelledPpm'], 2),
            ('exceeds' if row['decision'] == 'exceeds_limit' else 'within')
            + (' (balancing would change it: review)' if row['balancingChangesDecision'] else ''),
        )
        for row in s['limits']
    ]


def limits_text(s):
    """How the declared maximum concentrations were judged."""
    if not s['limits']:
        return 'No maximum concentrations were declared, so none were checked.'
    return (
        'Limits are decided on the laboratory analysis plus everything added, at the final '
        'volume. '
        'The charge-balanced value is shown for comparison only.'
    )


SOLUBILITY_TEXT = {
    'ok': 'within single-product limit',
    'exceeds': 'above single-product limit',
    'not_checked': 'not checked: no solubility data',
}


def _solubility_source(row):
    if row['limit_g_per_l'] is None:
        return 'no solubility data'
    source_t = row['source_temperature_c']
    return (
        f'{row["source"]}; {row["basis"]}; '
        + ('source temperature not stated' if source_t is None else f'{source_t:g} °C source')
        + f'; tank {row["tank_temperature_c"]:g} °C'
    )


def solubility_rows(s):
    """The single-product solubility results as table rows."""
    return [
        (
            f'Tank {r["tank"]}',
            r['product'],
            number(r['stock_g_per_l'], 1),
            number(r['limit_g_per_l'], 1),
            SOLUBILITY_TEXT[r['status']],
            _solubility_source(r),
        )
        for r in s['solubility']
    ]


def unchecked_line(s):
    """The products whose solubility could not be checked, as one line."""
    names = [r['product'] for r in s['solubility'] if r['status'] not in {'ok', 'exceeds'}]
    return (
        (
            'Solubility not checked (no solubility data): ' + ', '.join(names) + '. '
            'Confirm these dissolve with your supplier.'
        )
        if names
        else ''
    )


def rounded_dose_rows(delivered):
    """Product, dose and units shared by the rounded sheet and
    terminal.
    """
    rows = [
        (name, number(mass, 6), 'g dry product')
        for name, mass in delivered['dry_product_grams'].items()
    ]
    rows += [
        (
            row['name'],
            number(row['dose_ml'], 6),
            f'mL stock at {number(row["concentration_g_l"], 6)} g/L',
        )
        for row in delivered['stocks']
    ]
    reagent = delivered['reagent']
    liquid = reagent['volume_ml'] is not None
    rows.append(
        (
            reagent['formula'],
            number(reagent['volume_ml'] if liquid else reagent['grams'], 6),
            'mL liquid reagent' if liquid else 'g dry reagent',
        )
    )
    return rows
