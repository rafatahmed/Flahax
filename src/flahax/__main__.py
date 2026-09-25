"""Read targets and water as JSON on stdin. Write a recommendation on stdout."""

import json
import sys

from flahax import load_library, recommend
from flahax.engine import _usable


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("Expected a JSON object on stdin.", file=sys.stderr)
        return 1
    targets = payload.get("targets") if isinstance(payload, dict) else None
    if not isinstance(targets, dict) or not targets:
        print("targets are required.", file=sys.stderr)
        return 1
    water = payload.get("water") if isinstance(payload.get("water"), dict) else {}
    salts = [salt for salt in load_library()["salts"] if _usable(salt)]
    result = recommend(salts, targets, water)
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
