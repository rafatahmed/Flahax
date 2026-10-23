# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Which positive saturation indices block a plan, and which need review only (#78).

A positive saturation index is a thermodynamic statement, not a rate. FlahaX and
live PHREEQC 3.8.6 agree on every sign at the coupled target states (#78), so the
classification below is about the phases, not the solver. Phases listed in REVIEW
are supersaturated in typical feeds but are either kinetically inhibited at feed
conditions, or rest on a doubtful constant, or arise from the fixed oxidation state
the model uses; each carries its reason and sources (owner decision and research
summary on rafatahmed/Flahax#78, 2026-10-22). Every other positive index,
and any allocated solid, still blocks. The indices are always reported.
"""

from collections.abc import Mapping

# Index below which a phase counts as undersaturated (same threshold as before #78).
SI_THRESHOLD = 1e-7

REVIEW = {
    'Hydroxylapatite': (
        'Hydroxylapatite does not form directly from feed-like solutions: calcium phosphate precipitates through '
        'amorphous, octacalcium-phosphate and brushite precursors, and magnesium slows the transformation. Brushite '
        '(CaHPO4:2H2O), the precursor that does form, stays a hard gate.',
        'Nancollas, Tomazic & Tomson (1976) Croat. Chem. Acta 48(4), 431-438.',
    ),
    'Goethite': (
        'Crystalline goethite forms slowly from ferrihydrite (months to years at 24 C); ferrihydrite, the Fe(III) '
        'phase that precipitates quickly, stays a hard gate.',
        'Schwertmann & Murad (1983) Clays Clay Miner. 31(4), 277-284, doi:10.1346/CCMN.1983.0310405.',
    ),
    'MnHPO4': (
        'The database constant for anhydrous MnHPO4 (log K -25.4) traces only to the 1976 WATEQF program data, with '
        'no measurement behind it; the anhydrous phase is not reported to form in water at 25 C, and no Mn phosphate '
        'precipitation is reported in dilute nutrient feeds. Keep micronutrients and phosphate in separate '
        'concentrate tanks, where the real risk is.',
        'Ball & Nordstrom (1991) USGS OFR 91-183, Table 2 (after Plummer, Jones & Truesdell 1976, USGS WRI 76-13); '
        'Pedas et al. (2011) Front. Plant Sci. 2:37, doi:10.3389/fpls.2011.00037.',
    ),
    'Vivianite': (
        'Vivianite is an Fe(II) phosphate of reducing environments; the model holds Fe(II) at a fixed oxidation '
        'state, but in an aerated feed Fe(II) oxidizes and vivianite itself oxidizes in oxic water. See the iron(II) '
        'advisory for what does precipitate.',
        'Metz et al. (2024) Environ. Sci. Technol. 58, 15321; Rothe, Kleeberg & Hupfer (2016) Earth-Sci. Rev. 158, 51.',
    ),
}

FERROUS_IRON_ADVISORY = (
    'Iron supplied as iron(II) oxidizes in an aerated feed (half-life about hours at pH 6, days at pH 5.5, faster '
    'with phosphate) and precipitates as amorphous Fe(III) phosphate, taking some phosphate with it. Prefer a '
    'chelated iron source, or re-dose iron. Sources: Stumm & Lee (1961) Ind. Eng. Chem. 53, 143; Voegelin et al. '
    '(2010) Geochim. Cosmochim. Acta 74, 164; Hoagland & Arnon (1950) Calif. Agric. Exp. Stn. Circ. 347; '
    'Jacobson (1951) Plant Physiol. 26, 411.'
)


def assess_saturation(state):
    """Classify a state's positive saturation indices and solids.

    Returns {'blocking': [(phase, si)], 'review': [(phase, si, reason, sources)],
    'advisories': [text], 'solids': {phase: molal}}; ``blocks`` is True when a hard
    phase is supersaturated or any solid is allocated.
    """
    indices = state.saturation_indices
    positive = sorted(
        ((p, si) for p, si in indices.items() if si > SI_THRESHOLD), key=lambda item: -item[1]
    )
    solids = {p: v for p, v in state.precipitated.items() if v > 1e-12}
    blocking = [(p, si) for p, si in positive if p not in REVIEW]
    review = [(p, si, *REVIEW[p]) for p, si in positive if p in REVIEW]
    advisories = []
    totals = getattr(state, 'totals', None)
    if isinstance(totals, Mapping) and totals.get('Fe+2', 0) > 0:
        advisories.append(FERROUS_IRON_ADVISORY)
    return {
        'blocking': blocking,
        'review': review,
        'advisories': advisories,
        'solids': solids,
        'blocks': bool(blocking or solids),
    }


def describe(assessment):
    """One line per finding, for messages and warnings."""
    lines = [f'{p} SI {si:.2f} (blocks)' for p, si in assessment['blocking']]
    lines += [f'solid {p} allocated' for p in assessment['solids']]
    lines += [f'{p} SI {si:.2f} (review: {reason})' for p, si, reason, _ in assessment['review']]
    return lines
