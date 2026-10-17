# The fertigation math every agronomist needs, now open to everyone

<!--
DRAFT story piece (LinkedIn long-form or agri-trade outlet). Publish together
with the field article, after the first field results. Publish only once a
release of FlahaX under Apache-2.0 is on PyPI. ~900 words.
Placeholders are marked PLACEHOLDER or TODO.
-->

Every fertigation recipe starts as arithmetic. The crop needs so much
nitrogen, phosphorus, potassium, calcium and magnesium. The water already
brings some of them. Subtract, choose the salts, weigh the grams.

Then the recipe meets the tank, and the arithmetic stops being the whole
story. In hard water, calcium finds phosphate and sulfate and settles out as
sediment. Bicarbonate holds the pH up, so the acid dose you guessed is too
small or too large, and the acid you add brings nitrogen or phosphorus you
didn't count. A recipe that was right on paper can block drippers, starve
the crop of the nutrient it was meant to deliver, or push the pH where roots
can't use what's there.

Specialists handle this with chemistry most of us never see. Everyone else
handles it with experience, rules of thumb and a lot of trial and error.

## Why I built FlahaX

I trained as an agronomist at Jordan University of Science and Technology
and have spent more than twenty years in agriculture across the Middle East:
running fertilizer field trials in six countries, providing technical
support for specialty plant nutrition, and later leading fertilizer
marketing in Qatar. Throughout, I saw the same gap. The calculations behind a
good nutrient recipe (the water, the chemistry, the tanks) were within reach
of large operations and specialists, and rarely of the mid-size grower or the
agronomist advising them. FlahaX is my attempt to close that gap, in the
open.

## What it does

FlahaX is a free, open-source Python engine (Apache-2.0). You give it a
crop's nutrient targets, an analysis of your actual irrigation water, and the
fertilizers you have. It gives you back:

- **The recipe.** Which salts, and how many grams of each, so the solution
  matches the targets after what the water already carries.
- **What happens in the tank.** Which ions pair up, whether anything
  precipitates, and what the pH of the mixed solution will be.
- **The acid dose** to reach your target pH, using your acid's actual
  strength and density.
- **The stock tanks and injection.** How the recipe splits into A and B
  tanks, and the volumes and flows for your injectors.

Every result carries its units, the model it came from and a fingerprint of
the data it used, so another agronomist, a researcher or you next season can
check exactly how it was calculated. That is the point: not a black box that
says "trust me", but a calculation anyone can open and verify.

It also knows its limits. If an input is missing, it asks for it instead of
guessing. If your water is outside the range its chemistry model is built
for, it says so instead of giving you a confident wrong number.

## How it compares

Good tools already exist, and FlahaX owes a lot to the people who built
them. HydroBuddy has helped growers calculate nutrient solutions for years.
hydrosolver and research code from TU Chemnitz solve the recipe arithmetic in
Python. NUTRISENSE, from the Agricultural University of Athens, has shown in
the field how much a decision support system can do for closed hydroponics.
PHREEQC, from the U.S. Geological Survey, is the reference for water
chemistry.

What FlahaX adds is the whole path in one open package: from the water
analysis through the recipe and the chemistry to the stock tanks, with the
chemistry checked against PHREEQC. To my knowledge it is the first open
Python package that goes from water analysis to stock tanks with verified
chemistry.

## What it doesn't do yet

I would rather you hear this from me:

- **It hasn't been proven in the field yet.** All its evidence so far is
  computational: 153 automated tests and checks against PHREEQC. That is
  what the field trials below are for.
- **Its EC estimate is not yet accurate enough to rely on.** Treat it as a
  rough screen until it is validated.
- **Its chemistry has a stated range**: 25 °C and dilute solutions. Very
  saline water and concentrated stock tanks are outside it, and FlahaX will
  tell you so.

FlahaX is a planning tool. Before you apply a new recipe to a crop, check it
with a lab test of your water and your final solution.

## The field trials

<!-- PLACEHOLDER: replace this section with a short, plain summary of the
results once the field article's Results are final. Keep the numbers
identical to the paper. Suggested shape:

We tested FlahaX on two tomato farms in Qatar: one open-field on well water,
one hydroponic greenhouse on delivered water. Before taking a single
measurement, we wrote down what "close enough" would mean: pH within 0.3,
acid dose within 15%, nutrients within 10%, and precipitation predicted
correctly. Here is how it did: ...

Then one honest line on what failed or surprised us, and a link to the
paper. -->

## Try it

If you use Python:

```bash
python -m pip install flahax
```

Then run the worked example from the repository. It takes a published Qatar
well (Shomar et al., 2024) and a standard tomato solution (De Kreij, Voogt
and Baas, 1999), and shows the whole story in a few lines of output:

- The well water alone already carries more calcium and sulfate than tomato
  needs. No recipe can fix that, and FlahaX says so.
- Blended 1:3 with desalinated water, a pure mass balance hits every
  nutrient within 0.25%. It also drops the tank to pH 3.3, because it used
  phosphoric acid for phosphorus. The arithmetic looked perfect; the
  chemistry didn't.
- With monopotassium phosphate instead, the mix sits at pH 6.2, and
  43 mL of 60% nitric acid per 1,000 L brings it to pH 5.5, supplying the
  last bit of nitrate on the way.

<!-- TODO: replace with the exact command and output from the released
version; every number must match docs/publication/example/qatar_tomato.py. -->

The user manual ships inside the package, and the documentation is at
[github.com/rafatahmed/Flahax](https://github.com/rafatahmed/Flahax).

## Help it grow

- **Contribute.** Add a fertilizer to the library, report a wrong result,
  improve the documentation. Issues and pull requests are welcome.
- **Cite it** if you use it in research. The repository shows how.
- **If you advise growers** and want to test FlahaX on real water, get in
  touch.

FlahaX is also the planned engine for FlahaFAST, an app for growers who don't
write code.

*Parts of FlahaX and of this article were developed with AI assistants;
every result is checked against PHREEQC and the test suite, and I am
responsible for all of it.*
