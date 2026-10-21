"""Concentrate-tank grouping from a cited compatibility table (example code, not a FlahaX API).

Source: Yara, "Fertilizantes para fertirrigación" (examples/README: 04_Fertilizer.pdf,
SHA-256 3ba275fa...242e), page 65 "Mixing compatibility table", read with page 63
("DO NOT mix calcium content fertilizers with phosphate or sulphate fertilizer";
"do not acidify tanks with microelement chelates"). The table covers twelve Yara
products; each catalogue product below is mapped to its analogue by chemical
identity. Grades differ from Yara's, and the table states compatibility, not
solubility: a concentrate still needs grade- and temperature-qualified limits.
Products the table does not cover are reported as not covered, never guessed.
"""

# Page 65, symmetric pairs. "No" pairs; every other pair among these products is "Yes".
# * mixture solubility as SOP's, ** as MgS's (footnotes on the same page).
INCOMPATIBLE = {
    frozenset({'CALCINIT', 'SOP'}), frozenset({'CALCINIT', 'MKP'}), frozenset({'CALCINIT', 'MAP'}),
    frozenset({'CALCINIT', 'PHOS'}), frozenset({'CALCINIT', 'AS'}), frozenset({'CALCINIT', 'MGS'}),
    frozenset({'MAG', 'MKP'}), frozenset({'MAG', 'MAP'}), frozenset({'MAG', 'PHOS'}),
    frozenset({'MGS', 'MKP'}), frozenset({'MGS', 'MAP'}), frozenset({'MGS', 'PHOS'}),
}
FOOTNOTES = {
    frozenset({'K', 'AS'}): 'mixture solubility as potassium sulfate (*)',
    frozenset({'MAG', 'SOP'}): 'mixture solubility as magnesium sulfate (**)',
    frozenset({'MAG', 'AS'}): 'mixture solubility as magnesium sulfate (**)',
    frozenset({'MGS', 'K'}): 'mixture solubility as potassium sulfate (*)',
    frozenset({'MGS', 'MOP'}): 'mixture solubility as potassium sulfate (*)',
}
# Catalogue name -> page 65 product (Yara name in brackets).
ANALOGUE = {
    'Urea': ('UREA', 'Urea'),
    'Ammonium Nitrate': ('AMNITRA', 'AM NITRA'),
    'Ammonium Sulfate': ('AS', 'AS'),
    'Phosphoric Acid (75%)': ('PHOS', 'Phos. acid'),
    'Ammonium Monobasic Phosphate': ('MAP', 'KRISTA-MAP'),
    'Potassium Monobasic Phosphate': ('MKP', 'KRISTA-MKP'),
    'Potassium Chloride': ('MOP', 'KRISTA-MOP'),
    'Potassium Sulfate': ('SOP', 'KRISTA-SOP'),
    'Potassium Nitrate': ('K', 'KRISTA-K'),
    'Calcium Nitrate (ag grade)': ('CALCINIT', 'CALCINIT'),
    'Mg Nitrate': ('MAG', 'KRISTA-MAG'),
    'Magnesium Sulfate (Heptahydrate)': ('MGS', 'KRISTA-MgS'),
}
SOURCE = ('Yara, Fertilizantes para fertirrigación (04_Fertilizer.pdf), p. 65 mixing compatibility '
          'table and p. 63 mixing rules')


def group_tanks(salts):
    """Fewest tanks in which every pair of covered products is compatible on page 65.

    Calcium nitrate is placed first (tank A), then the remaining covered products by
    descending dose; each joins the first tank it is compatible with. Products the
    table does not cover (micronutrients, chelates, other salts) are returned apart.
    """
    covered = [s for s in salts if s['name'] in ANALOGUE]
    covered.sort(key=lambda s: (ANALOGUE[s['name']][0] != 'CALCINIT', -s['gramsPerLitre']))
    tanks = []
    for salt in covered:
        code = ANALOGUE[salt['name']][0]
        for tank in tanks:
            if all(frozenset({code, ANALOGUE[o['name']][0]}) not in INCOMPATIBLE for o in tank):
                tank.append(salt)
                break
        else:
            tanks.append([salt])
    labelled = {}
    for index, tank in enumerate(tanks):
        codes = [ANALOGUE[s['name']][0] for s in tank]
        notes = sorted({note for pair, note in FOOTNOTES.items() if pair <= set(codes)})
        labelled['ABCDEF'[index]] = dict(
            products=[dict(name=s['name'], analogue=ANALOGUE[s['name']][1], gramsPerLitre=s['gramsPerLitre'])
                      for s in tank], notes=notes)
    not_covered = [s['name'] for s in salts if s['name'] not in ANALOGUE]
    return dict(source=SOURCE, tanks=labelled, not_covered=not_covered,
                rule='Page 65 lists compatibility only; solubility at stock strength is not established.',
                micronutrients='Not in the page 65 table. Page 63: do not acidify tanks holding chelates. '
                               'Keep them out of the acid channel and confirm their tank with the supplier.')
