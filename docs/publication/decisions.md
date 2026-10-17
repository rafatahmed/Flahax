# Publication decisions

Decisions made by the author on 2026-10-17, while planning how to publish
FlahaX. They apply to the drafts in this folder. Open items are listed at
the end.

## The pieces

| Piece | Venue | Language | When |
|---|---|---|---|
| Software paper | Journal of Open Source Software (JOSS) | English | Earliest submission 2027-03-26 (see below), after an Apache-2.0 release is on PyPI |
| Field article | A field-trial journal: *Computers and Electronics in Agriculture*, *Agricultural Water Management* or *Horticulturae* | English | After the first field results |
| Story piece | LinkedIn long-form or an agri-trade outlet | English, plus a Standard Arabic version | Together with the field article |

## Decisions

1. **Readers.** The story piece is for agronomists, fertilizer producers and
   growers' advisers. The JOSS paper and field article are for researchers.
2. **Claim.** No "complete solution" or "once for all". The claim is that the
   calculations behind a good recipe are now open, checkable and reproducible.
3. **Licence.** FlahaX moves to Apache-2.0 (rafatahmed/Flahax PR 13). Say
   "open source" only once a release under Apache-2.0 is on PyPI.
4. **No "first" in any headline.** Peers (hydrosolver, HydroBuddy,
   NutrientMixingAlgorithm, NUTRISENSE, PHREEQC) are compared fairly in the
   body. The only priority wording allowed is the cautious one: "to our
   knowledge, the first open Python package that goes from water analysis to
   stock tanks with verified chemistry".
5. **Order.** The JOSS paper is submitted as soon as it is eligible. The field
   article and story piece wait for field results.
6. **Tone.** The articles attack no one. No company or person is named as a
   problem. Fertilizer producers are welcome users.
7. **Career history** is context for the author's credibility only, not a
   memoir. Nothing about former employers' internal tools or methods.
8. **Personal paragraph.** One paragraph, as drafted in the story piece, is
   the only personal part.
9. **Reproducible example water.** A published, citable analysis of Gulf
   groundwater, named in the text. Source still to be chosen (open item 1).
10. **Crop.** Tomato, for the example and both trial sites.
11. **Call to action.** Main: try it (install, run the example, get the same
    numbers). Smaller: contribute or cite; advisers who want to test it on
    real water can get in touch.
12. **Limits upfront.** A "What it doesn't do yet" section: no lab or field
    validation so far, EC accuracy unknown, bounded chemistry that refuses
    rather than guesses. Recipes must be checked by lab test before use.
13. **Wait for field results.** Results, Discussion and Conclusion are
    placeholders until measured data exist.
14. **JOSS independently of the trials.**
15. **Trial sites.** Two farms in Qatar, both anonymised: open-field tomato on
    well water, and greenhouse hydroponic tomato on delivered irrigation water.
    The JOSS and "try it" example uses the published water.
16. **Both trial waters** need a full lab analysis that includes bicarbonate
    before any trial starts.
17. **Success thresholds**, fixed before any measurement:

    | Prediction | Measurement | Threshold |
    |---|---|---|
    | pH of the drip solution | pH meter at the dripper | ±0.3 pH units |
    | Acid to reach target pH | Measured titration | ±15% |
    | Precipitation in each stock tank (yes/no) | Sediment, cloudiness or clogging after 24 h | Prediction matches observation |
    | N, P, K, Ca, Mg, S in the drip solution | Lab analysis | ±10% of target |
    | EC of the drip solution | EC meter | Reported, not pass/fail |

18. **Authors and AI.** JOSS paper: the author alone, Flaha as affiliation,
    with ORCID. Field article co-authors and acknowledgements are decided
    before the trial. Every paper carries an AI usage disclosure (required by
    JOSS). AI tools are never listed as authors.
19. **Titles.**
    - Field article: *Predicting nutrient-solution chemistry from irrigation
      water analysis: field evaluation of an open-source Python engine for
      tomato in Qatar*
    - Story piece: *The fertigation math every agronomist needs, now open to
      everyone*
    - JOSS: *FlahaX: a Python engine for fertilizer formulation, aqueous
      equilibrium chemistry and auditable delivery planning*

    One-sentence summary: FlahaX turns an irrigation water analysis and a
    crop target into a fertilizer recipe and predicts what that recipe does
    in the tank. Tested on two Qatar tomato farms, this is how well those
    predictions held.
20. **Arabic.** Written directly in Standard Arabic (فصحى), not translated
    line by line. Technical terms keep their Latin form with an Arabic gloss
    the first time, for example التسميد مع الري (fertigation). The author
    reviews it.
21. **This folder** holds drafts only. Publishing a release, submitting to
    JOSS and posting anything are the author's actions.

## Found while compiling

- **JOSS eligibility date.** JOSS requires the repository to have been public
  for more than six months. `rafatahmed/Flahax` was created on 2026-09-25,
  so the earliest submission is **2027-03-26**. JOSS also requires an
  OSI-approved licence, so the Apache-2.0 release must be on PyPI first.
- **JOSS paper sections.** Summary, Statement of need, State of the field,
  Software design, Research impact statement and AI usage disclosure.
  750–1,750 words.
- **Typical Qatar groundwater is outside FlahaX's model.** A 205-well survey
  (Shomar 2024) reports average TDS of about 4,600 mg/L, with Ca 345,
  Mg 127, Na 923, Cl 1,472 and SO₄ 1,064 mg/L. Those ions alone give an ionic
  strength of about 0.09 mol/L before bicarbonate and fertilizer are added.
  FlahaX's equilibrium model is valid up to 0.1 mol/kg, so a tomato recipe on
  that water would be refused. This affects decision 9 and the open-field
  trial site.

## Open items

1. **Example water.** Choose between the options in the compile report
   (a lower-salinity published sample, or the survey average as a
   demonstration that FlahaX refuses out-of-range water).
2. **Open-field well.** If its lab analysis puts the recipe above ionic
   strength 0.1, FlahaX will refuse it. Decide before the trial whether that
   site still tests in-scope predictions.
3. Lab analyses of both trial waters (with bicarbonate), the meter models and
   calibration, and the trial season.
4. Field article co-authors and acknowledgements.
5. Ask Prof. Khalid Hameed before naming him anywhere (he is not named in
   the current drafts).
6. ORCID iD to insert in the JOSS paper.
