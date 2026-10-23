# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The ``flahax`` command. Growers start with ``flahax mix``; with JSON piped in, it writes a
recommendation."""

import json
import sys
import argparse

from flahax import InputError, __version__, recommend

WELCOME = f"""FlahaX {__version__}: fertilizer recipe, pH and A/B stock tanks from your water and crop formula.

  flahax mix              answer five questions and get the batch sheet (growers and agronomists)
  flahax mix sessions/X   repeat a saved batch without questions
  flahax batch --help     the same in one command, for scripts
  flahax --help           every command; developers can also pipe JSON into flahax
"""  # noqa: E501


def main() -> int:
    """The ``flahax`` console entry point; Ctrl+C prints "Stopped." and exits with 130."""
    try:
        return _main()
    except KeyboardInterrupt:
        print('Stopped.', file=sys.stderr)
        return 130


def _main() -> int:
    if not sys.argv[1:] and sys.stdin.isatty():
        print(WELCOME, end='')
        return 0
    if sys.argv[1:2] == ['batch']:
        from .batch_cli import main as batch

        return batch(sys.argv[2:])
    if sys.argv[1:2] == ['mix']:
        from .mix_cli import main as mix

        return mix(sys.argv[2:])
    parser = argparse.ArgumentParser(
        prog='flahax',
        description='FlahaX nutrient recommendation and site planning. '
        'Growers: flahax mix. Without a command, a JSON request is read from stdin.',
    )
    parser.add_argument('--version', action='version', version=f'FlahaX {__version__}')
    parser.add_argument(
        'command',
        nargs='?',
        default='recommend',
        choices=('recommend', 'workflow', 'ec', 'size', 'batch', 'mix'),
        help='batch: report and batch sheet (flahax batch --help); mix: interactive five-step '
        'entry',
    )
    parser.add_argument(
        '--interactive', action='store_true', help='Request site inputs (workflow, ec or size)'
    )
    args = parser.parse_args()
    if args.command != 'recommend':
        from .planning_cli import execute, interactive, serializable

        try:
            payload = interactive(args.command) if args.interactive else json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            print(
                f'Invalid planning input: stdin is not valid JSON: '
                f'{exc.msg.removesuffix(" at")} at line {exc.lineno}, '
                f'column {exc.colno}',
                file=sys.stderr,
            )
            return 1
        except (ValueError, TypeError, KeyError, OSError, EOFError) as exc:
            print(f'Invalid planning input: {exc}', file=sys.stderr)
            return 1
        try:
            result = execute(args.command, payload)
            json.dump(serializable(result), sys.stdout, allow_nan=False)
            sys.stdout.write('\n')
            return 0
        except (ValueError, TypeError, KeyError, OSError, EOFError) as exc:
            print(f'Invalid planning input: {exc}', file=sys.stderr)
            return 1
    if args.interactive:
        parser.error('Use workflow --interactive to request site-specific inputs')
    if sys.stdin.isatty():
        print(
            'Reading a JSON request from the keyboard; end it with Ctrl+Z then Enter (Windows) '
            'or Ctrl+D. '
            'Growers: use flahax mix.',
            file=sys.stderr,
        )
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(
            f'Expected a JSON object on stdin: {exc.msg.removesuffix(" at")} at line '
            f'{exc.lineno}, column {exc.colno}.',
            file=sys.stderr,
        )
        return 1
    if not isinstance(payload, dict):
        print("Expected a JSON object on stdin.", file=sys.stderr)
        return 1
    targets = payload.get("targets")
    if (
        "water" in payload
        and payload["water"] is not None
        and not isinstance(payload["water"], dict)
    ):
        print("water must be a map of ion symbol to ppm.", file=sys.stderr)
        return 1
    water = payload.get("water") or {}
    salts = payload.get("salts")
    if not isinstance(salts, list) or not salts:
        print(
            "salts are required. Pass the saved fertilizer rows. The packaged library is only "
            "an example.",
            file=sys.stderr,
        )
        return 1
    allow = payload.get("allowIons") or []
    if not isinstance(allow, list):
        print("allowIons must be a list of ion symbols.", file=sys.stderr)
        return 1
    try:
        result = recommend(
            salts,
            targets,
            water,
            allow_ions=set(allow),
            allow_carbonates=bool(payload.get("allowCarbonates")),
        )
    except InputError as exc:
        print(exc, file=sys.stderr)
        return 1
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
