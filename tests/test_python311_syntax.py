# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Code must run on the oldest supported Python (3.11): no f-string reusing its own quote inside a field.

Python 3.12 (PEP 701) allows f'{x.strip(' ')}'; 3.11 rejects it, so a module written on a newer Python
would fail to import on 3.11. Runs where tokenize reports f-string parts (Python 3.12 and later); on 3.11
the import of every module already catches it.
"""

from pathlib import Path
import tokenize
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'rRfFbBuU'


def reused_quotes(file):
    found, quotes = [], []
    with open(file, 'rb') as handle:
        for tok in tokenize.tokenize(handle.readline):
            if tok.type == tokenize.FSTRING_START:
                body = tok.string.lstrip(PREFIX)
                quote = body[:3] if body[:3] in ('"""', "'''") else body[:1]
                if quotes and len(quotes[-1]) == 1 and quote[0] == quotes[-1]:
                    found.append(tok.start[0])
                quotes.append(quote)
            elif tok.type == tokenize.FSTRING_END and quotes:
                quotes.pop()
            elif (
                quotes
                and tok.type == tokenize.STRING
                and len(quotes[-1]) == 1
                and tok.string.lstrip(PREFIX)[:1] == quotes[-1]
            ):
                found.append(tok.start[0])
    return found


@unittest.skipUnless(hasattr(tokenize, 'FSTRING_START'), 'needs Python 3.12+ tokenize')
class Python311SyntaxTests(unittest.TestCase):
    def test_no_f_string_reuses_its_quote(self):
        for folder in ('src', 'tests', 'tools', 'examples', 'benchmarks'):
            for file in sorted((ROOT / folder).rglob('*.py')):
                with self.subTest(file=str(file.relative_to(ROOT))):
                    self.assertEqual(
                        reused_quotes(file),
                        [],
                        'f-string reuses its quote: invalid on Python 3.11',
                    )


if __name__ == '__main__':
    unittest.main()
