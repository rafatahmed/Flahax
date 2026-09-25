"""Read targets and water as JSON on stdin. Write a recommendation on stdout."""

import json
import sys

from flahax import InputError, recommend


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("Expected a JSON object on stdin.", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print("Expected a JSON object on stdin.", file=sys.stderr)
        return 1
    targets = payload.get("targets")
    if "water" in payload and payload["water"] is not None and not isinstance(payload["water"], dict):
        print("water must be a map of ion symbol to ppm.", file=sys.stderr)
        return 1
    water = payload.get("water") or {}
    salts = payload.get("salts")
    if not isinstance(salts, list) or not salts:
        print("salts are required. Pass the saved fertilizer rows. The packaged library is only an example.", file=sys.stderr)
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
