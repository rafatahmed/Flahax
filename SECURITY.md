# Security policy

## Supported versions

Security fixes go into the next release and into `main`. Older releases are
not patched; upgrade with `python -m pip install --upgrade flahax`.

| Version | Supported |
|---|---|
| Latest release on PyPI (0.5.x today) | Yes |
| `main` | Yes |
| Earlier releases | No |

## Reporting a vulnerability

Please report security problems privately, not in a public issue:

- through GitHub's private vulnerability reporting on this repository
  (**Security** tab, then **Report a vulnerability**), or
- by email to Flaha Agri Tech at <info@flaha.org>, with "FlahaX security" in
  the subject.

Include the FlahaX version (`flahax --version`), your Python version and
operating system, the input or steps that show the problem, and what you
expected to happen. You will get an acknowledgement within 7 days and a
plan or a fix as soon as the problem is understood. You will be credited in
the changelog unless you ask not to be.

## What counts as a security problem

FlahaX is a pure-Python library and command line with no runtime
dependencies, no network access and no server. Security problems include:

- code execution, or reading or writing files outside the places FlahaX
  is asked to use, through a JSON request, a water analysis, a saved
  session or a product file (for example a session name that escapes
  `$FLAHAX_HOME`);
- a crafted input that makes FlahaX hang or use unbounded memory;
- a packaged file or release artifact that does not match the source
  (the release workflow publishes from tagged commits with pinned actions).

A wrong recipe, pH or acid volume is a correctness bug, not a security
problem: please open a normal issue with the inputs. FlahaX results are
calculations for planning, not dosing instructions; always measure pH and EC
after mixing (see the disclaimer in the README and the Apache-2.0 license,
section 7).
