# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The ``flahax`` command. Growers start with ``flahax mix``; with JSON piped in, it writes a
recommendation."""

import json
import sys
import argparse

from flahax import InputError, __version__

DOCS = 'https://flahax.readthedocs.io/'
ISSUES = 'https://github.com/rafatahmed/Flahax/issues'
WELCOME = f"""FlahaX {__version__}: fertilizer recipe, pH and A/B stock tanks from your water and crop formula.

  flahax mix              answer five questions and get the batch sheet (growers and agronomists)
  flahax mix sessions/X   repeat a saved batch without questions
  flahax batch --help     the same in one command, for scripts
  flahax --help           every command; developers can also pipe JSON into flahax

Documentation: {DOCS}
"""  # noqa: E501
DESCRIPTION = """FlahaX: fertilizer recipe, pH and A/B stock tanks from your water and crop formula.

commands:
  mix        answer five questions and get tank A, tank B and the acid (growers, agronomists)
  batch      the same from files in one command, for scripts (flahax batch --help)
  recommend  read a JSON request on stdin and write a fertilizer recipe (the default)
  workflow   plan a full workflow from a JSON request on stdin, or with --interactive
  ec         screen the EC of supported products before acid (JSON on stdin or --interactive)
  size       size injector channel volumes and flows (JSON on stdin or --interactive)
"""  # noqa: E501
EPILOG = f"""Examples:
  flahax mix                        start a new batch, full screen in a terminal
  flahax mix sessions/tomato-ro     repeat a saved batch without questions
  flahax mix --plain                ask the questions line by line
  flahax batch --formula "Tomato (Howard Resh)" --water ro --ph 5.8 --acid HNO3:0.60:1.37 --output out
  flahax < request.json             write a recipe from a JSON request

Documentation: {DOCS}
Report a problem: {ISSUES}
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
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--version', action='version', version=f'FlahaX {__version__}')
    parser.add_argument(
        'command',
        nargs='?',
        default='recommend',
        choices=('recommend', 'workflow', 'ec', 'size', 'batch', 'mix'),
        metavar='COMMAND',
        help='one of the commands above (default: recommend)',
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='ask for the inputs of workflow, ec or size instead of reading JSON',
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
    from .planning_cli import recommend_request, serializable

    try:
        result = recommend_request(payload)
    except InputError as exc:
        print(exc, file=sys.stderr)
        return 1
    json.dump(serializable(result), sys.stdout, allow_nan=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
