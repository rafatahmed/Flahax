---
title: 'FlahaX: a Python engine for fertilizer formulation, aqueous equilibrium chemistry and auditable delivery planning'
tags:
  - Python
  - plant nutrition
  - fertigation
  - hydroponics
  - aqueous chemistry
  - fertilizer formulation
authors:
  - given-names: Rafat A.
    surname: Al Khashan
    orcid: 0000-0000-0000-0000  # TODO: author's ORCID iD
    affiliation: 1
affiliations:
  - index: 1
    name: Flaha Agri Tech, Qatar  # TODO: confirm exact affiliation name
date: 26 March 2027  # TODO: set on submission (earliest eligible date)
bibliography: paper.bib
---

<!--
DRAFT. Do not submit before:
  1. an Apache-2.0 release of FlahaX is on PyPI, and
  2. 2027-03-26 (JOSS requires more than six months of public history;
     the repository was created on 2026-09-25).
Placeholders are marked TODO. Word count target: 750-1,750.
-->

# Summary

Growers who irrigate with dissolved fertilizers (fertigation and hydroponics)
need a recipe: which fertilizer salts to dissolve, and how many grams of each,
so that the water the plant receives matches a crop's nutrient targets. The
recipe depends on the irrigation water itself, which already carries calcium,
magnesium, sulfate, bicarbonate and other ions. And a recipe that is right on
paper can still fail in the tank: salts can precipitate, the pH can drift out
of range, and an acid dose chosen by rule of thumb can over- or undershoot.

FlahaX is a dependency-free Python library and command-line tool that takes
a crop's nutrient targets and an analysis of the actual irrigation water, and
returns a fertilizer recipe together with what that recipe does in solution.
It predicts ion pairs and complexes, saturation and precipitation of
fertilizer phases, and the pH of the mixed solution. It plans the acid dose
to reach a target pH and splits the recipe into stock tanks and injector
flows. Every plan records its units, model identifiers and source-data
hashes, so that a result can be reviewed and reproduced. Where an input is
missing or a condition lies outside the model's stated validity range,
FlahaX returns an explicit "needs input" or "not supported" status instead
of a plausible-looking number.

# Statement of need

Nutrient-solution recipes are usually calculated in spreadsheets, in
desktop calculators, or with vendor tools tied to one company's product
catalogue. Most of these treat a recipe as a mass balance: grams of salt in,
milligrams per litre of each element out. That arithmetic is necessary, but
it says nothing about what happens when the salts meet the water. With hard
or alkaline irrigation water, common in arid regions, calcium phosphates and
sulfates can precipitate, bicarbonate buffers the pH, and the acid needed to
correct it changes the nitrogen or phosphorus actually delivered.

General geochemical codes such as PHREEQC [@parkhurst2013] can model this
chemistry, but they are not built around fertilizers, recipes or stock
tanks, and setting up a fertilizer problem by hand is slow and error-prone.
Researchers who study nutrient solutions, agronomists who design recipes
against real water analyses, and developers who build fertigation software
therefore lack an open, scriptable tool that joins formulation to solution
chemistry and delivery, and that states where its predictions stop being
valid.

FlahaX is intended for these three groups: for reproducible
nutrient-solution chemistry in research, for recipe design against a real
water analysis and real commercial products, and as a tested engine that
other software can embed.

# State of the field

Several open tools address parts of this problem. hydrosolver
[@hydrosolver] is a Python package that solves for salt masses by least
squares. NutrientMixingAlgorithm [@kobelski2024] optimises water sources and
fertilizer masses for a mixing tank in aquaponics. HydroBuddy
[@hydrobuddy] is a widely used free desktop calculator with A/B stock
planning and an empirical conductivity estimate. NUTRISENSE [@nutrisense]
is a field-validated decision support system that calculates and readjusts
nutrient solutions in closed hydroponic systems, a function FlahaX does not
provide. PHREEQC and its Python bindings [@phreeqpy] model aqueous
equilibrium in general, without fertilizer formulation.

To our knowledge, none of these combines fertilizer formulation against the
source water, fertilizer-specific aqueous equilibrium with precipitation,
acid planning to a target pH, and stock-tank and injector planning with an
audit trail in one installable package. FlahaX was built as a new package
rather than as an extension of an existing one because the end-to-end audit
trail and the shared chemistry model run through every layer, from salt
selection to injector flow, and could not be added to a mass-balance solver
without redesigning it.

# Software design

FlahaX has four layers that share one data model.

**Formulation.** The recipe is the non-negative least-squares solution
[@lawson1974] that minimises the relative error of each requested element
after the source water is subtracted. Each element's residual is scaled by
its target, unrequested elements carry a light penalty, and a salt is removed
only if a refit keeps every requested element within the tolerance already
reached. The crop formula is never altered to make the fit look better.

**Equilibrium chemistry.** A single mixed aqueous model covers all 28
fertilizer products in the shipped catalogue, with 197 aqueous species and 28
solid phases. Activities use the Davies equation [@davies1962]. The stated
validity range is 25 °C, ionic strength up to 0.1 mol/kg, fixed oxidation
states and closed inorganic carbon. Outside that range the model refuses
rather than extrapolates.

**pH and acid.** FlahaX calculates the initial pH of the mixed solution
and the nitric acid dose to reach a target pH, using the supplied acid assay
and density. A standard workflow covers nitric and phosphoric acid.

**Delivery planning.** The recipe is split into stock tanks using
caller-supplied compatibility and solubility records, and then converted
into reagent volumes and pump or injector flows.

Two design choices run through all layers. First, there are no runtime
dependencies: FlahaX uses only the Python standard library (3.11 to 3.13),
so it installs anywhere and can be embedded without dependency conflicts.
Second, units are explicit types (for example grams per litre of final
solution versus grams per kilogram of water), and every result carries model
identifiers and source hashes.

Verification uses 153 automated tests, including live replay of every
catalogue product, solid phase and acid case against a pinned build of
PHREEQC 3.8.6, with stored reference outputs. This evidence is
computational. Field evaluation is under way (see below).

<!-- TODO: once the example water is chosen, add a short worked example here:
     tomato targets + published Gulf groundwater -> recipe, saturation
     indices, initial pH, nitric acid dose, A/B split. Run it on the
     released Apache-2.0 version and paste the output, with the source of
     the water analysis cited. Keep it under ~150 words. -->

# Research impact statement

FlahaX is on PyPI and is being prepared for a two-site field evaluation in
Qatar, on open-field and greenhouse hydroponic tomato, with irrigation waters
of contrasting hardness. The evaluation will compare FlahaX's predicted pH,
acid dose, precipitation and nutrient concentrations with meter readings and
laboratory analyses, against acceptance thresholds fixed before any
measurement. FlahaX is also planned as the chemistry engine of FlahaFAST, a
fertigation application for growers who do not write code.

<!-- TODO at submission: update with whatever exists by then, e.g. first
     trial measurements, users, citations, teaching use. Do not overstate. -->

# AI usage disclosure

Generative AI coding assistants were used during development of FlahaX and
the preparation of this paper. <!-- TODO: list each tool and version, e.g.
Claude Code (Anthropic, model ...) and Cursor (agent, model ...), and where
each was used. --> They assisted with code generation, test scaffolding,
documentation and drafting of this manuscript. The author made the
architectural, scientific and design decisions, reviewed and revised all
AI-assisted output, and verified the chemistry against PHREEQC reference
calculations and the automated test suite. The author takes full
responsibility for the software and this paper.

# Acknowledgements

<!-- TODO: financial support, if any. If none, state "This work received no
     specific funding." -->

# References
