# Reaction qualification and model domains

Qualification recorded **2026-10-26** for the pinned 25 C model: 197 aqueous
entries and 28 phases. Every entry is checked for original atom/charge balance,
transformed component balance and log-K transformation. This qualifies the
implementation of the selected equations, not all physical mixtures that a
caller can describe.

## Sources and transformation evidence

The source database SHA-256 is
`ab0a8f7c7375e1bd997990f4bc3a9af497516f10e57f4aaa3cefb55dccac5ae7`.
The [coverage matrix](chemistry-coverage-matrix.md) retains each equation,
constant, source filename and line. `tools/qualify_chemistry_model.py` checks these
against an external pinned MINTEQ file and the unchanged project extension files:

```text
python tools/qualify_chemistry_model.py --database PATH/minteq.v4.dat --report audit.json
```

This command reads the model and databases and writes only the requested report.
It records model/source hashes, per-reaction checks, source correspondence and
parameter status. A changed base or extension hash, byte count, missing source,
or changed manifest digest fails. No solver or model-builder function
is imported by the checker. Atom, charge and basis sums use rational arithmetic;
log-K comparison allows only a bound calculated from binary floating-point ULPs
and the number of terms. That bound is not thermodynamic uncertainty.

## Reproducing the exact chemistry inputs

The original base is **334,121 bytes**, including its CRLF line endings, from the
**PHREEQC 3.8.6-17100 Windows release distribution**. It is not the current MINTEQ
file on upstream `master`. The versioned [USGS installer](https://water.usgs.gov/water-resources/software/PHREEQC/phreeqc-3.8.6-17100-x64.msi)
is 16,846,848 bytes with SHA-256
`6e5f6697fa727f919eb4e7c1c2bc20e8c2717378aaf77731efd831ef66578243`.
Administrative extraction with `msiexec /a` yields
`phreeqc-3.8.6-17100-x64/database/minteq.v4.dat`, whose SHA-256 is the base hash above.
No edits or newline conversion are applied. This extraction was reproduced on
12 November 2026 from the hash-verified release archive. It does not replace a
database or require a system-wide installation. `tools/provision_phreeqc.ps1`
already documents the pinned download/extraction procedure; running it is an
explicit reference-provisioning action, not part of the model builder.

`tools/chemistry_sources.json` records the three build inputs, their byte lengths,
SHA-256 hashes, UTF-8 decoding policy and origins. The two extension URLs are pinned
to repository revision `de50f8963a65a9f0f99462ffc731350de64472fc`; their bytes also
remain in the source distribution under `tests/fixtures/phreeqc/database/`.
The phase extension attributes kieserite and sylvite to `pitzer.dat` in the same
release archive (lines 357 and 433, respectively). Only their 25 C reactions and
log K values are selected; temperature expressions are not imported. The Pitzer
file is attribution evidence, not an additional input consumed during regeneration.
The manifest also distinguishes the cited struvite constant, fixed urea identity,
and selected project chelate profile.

The generated `chemistry_25c.json` schema 2 contains this manifest as `sources`.
`database_sha256` remains a compatibility field for **the base alone**.
`source_url` identifies the versioned release archive, not a raw database file;
the archive member and hashes are in the base source record.
`sources_sha256` covers the complete manifest: sort records by `filename`, serialize
with Python JSON `sort_keys=True`, `separators=(',', ':')`, `ensure_ascii=True`,
`allow_nan=False`, encode UTF-8 without a trailing newline, then SHA-256.
No build timestamp or machine path participates. The builder hashes and decodes
the same bytes and refuses inputs that differ from the pinned source manifest.

With the original base already extracted, regeneration and qualification are offline:

```text
python tools/build_chemistry_model.py PATH/minteq.v4.dat --output regenerated.json
python tools/qualify_chemistry_model.py --database PATH/minteq.v4.dat --model regenerated.json --report audit.json
python -c "from pathlib import Path; assert Path('regenerated.json').read_bytes() == Path('src/flahax/data/chemistry_25c.json').read_bytes()"
```

`--output` writes only the requested JSON; it does not rewrite the source model or
coverage documentation. Repeated regeneration from identical inputs must be
byte-identical. Provenance-only changes preserve every reaction, constant, species,
phase, basis and alias. Hash agreement establishes identity, not thermodynamic accuracy.

An optional retrieval test downloads the versioned installer and pinned extension
files into memory, checks byte counts and hashes, and never installs or executes them:

```text
# Set FLAHAX_VERIFY_SOURCE_DOWNLOADS=1 in your shell, then:
python -m unittest tests.test_chemistry_source_downloads
```

This is independent of `FLAHAX_REQUIRE_PHREEQC`. With the download flag unset it is
explicitly skipped; offline integrity checks still run. When enabled, retrieval
unavailability and content mismatch are distinct failures. The installer checksum
and member identity remain necessary even if a versioned server URL is later replaced.

| Parameter origin | What is established | What is not established |
|---|---|---|
| Pinned MINTEQ compilation | Equation/log-K correspondence and basis conversion | Independent revalidation of every underlying measurement |
| DTPA/EDDHA extension | Exact implementation of the selected project profile | New infinite-dilution calibration, electrolyte transfer or commercial isomer composition |
| Phase extension | Declared reaction and constant, preserved source identity | Kinetics, mixing compatibility or general high-salinity validity |
| Fixed-valence master/urea identity | Conserved input and zero identity constant | Redox equilibration or urea hydrolysis |

PHREEQC defines aqueous association reactions and 25 C log K in
[SOLUTION_SPECIES](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-50.htm),
and mineral dissolution reactions in
[PHASES](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-36.htm).
Its [input description](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-5.htm)
describes internal conversion to molality and rewriting reactions to master species.
FlahaX retains its own documented activity/water approximations; matching source
constants does not make those approximations identical to PHREEQC.

## Returned qualification

Every solver-produced `AqueousResult` carries `model_domain` and
`model_limitations`. Direct fixed-pH and calculated-pH entry points retain them,
as do result objects nested in reagent/mixture calculations. Inspect these fields
before treating numerical convergence as evidence of model coverage.

For each positive EDTA, citrate, DTPA or EDDHA input, the selected reaction set is
checked for complexes with positive Ca, Mg, Fe(II), Fe(III), Mn, Zn and Cu inputs.
A missing pair yields `omitted_competition` with the exact component names. Zero
inputs do not activate a pair. This inventory is explicitly limited to those
ligands/metals; an empty list is not proof that all possible reactions are present.
DTPA/EDDHA inputs also carry `selected_chelate_profile`. No missing complex or
constant is invented, and no numerical result is altered to suppress a warning.
Downstream report/acceptance propagation remains a separate contract from these
raw solver result fields.

## Admitted numerical and chemical conventions

| Boundary | Current behavior and limitation |
|---|---|
| Temperature | Only 25 C; no temperature extrapolation |
| Ionic strength | Computed and supplied values must stay at or below 0.1 mol/kg water |
| pH | Numerical interval [0,14]; another boundary may reject a point inside it |
| Activity | Charged Davies expression; neutral log10(gamma) = 0.1 I |
| Standard state | Dimensionless molal activities; pure solid activity is unity |
| Water | `max(0.9, 1 - sum(aqueous molalities)/55.5084)`; inherited dilute approximation |
| Carbon | Closed analytical inventory, no imposed gas reservoir |
| Valence | Separate conserved oxidation states, no electron equilibration |
| Urea | Neutral conserved inventory, no hydrolysis |
| Precipitation | Equilibrium allocation for selected phases, no kinetic prediction |

Numerical bounds do not certify every parameter across that entire domain.
All 225 reactions are evaluated in a complete synthetic inventory; independent
mass-action and saturation equations check the returned activities. Tests also
check domain edges, fixed-valence and urea conservation, water activity, all 28
selected ligand/metal pairs, and in-memory parameter sensitivity. Perturbations
are test copies only; reference/database bytes are preserved.

A database citation does not establish that a phase constant has no measurement
behind it. In particular, the full MnHPO4 source chain remains unverified here;
phase-decision wording and kinetics require their separate review. Agreement
between solvers sharing a constant is implementation evidence, not independent
constant validation. Physical validation remains a later stage.
