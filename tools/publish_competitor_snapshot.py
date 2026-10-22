"""Package a #40 competitor run as a static evidence snapshot for the docs site.

No benchmark is run here. The three track outputs (formulation.json, chemistry.json,
ec.json) are copied byte for byte, an environment record is added, and everything is
bundled in evidence.zip with SHA-256 checksums. Run it with the competitor
environment's Python on the machine that measured, so the environment record is true.
"""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKS = ("formulation.json", "chemistry.json", "ec.json")
MEASURED_PATHS = ("src", "benchmarks", "tools/competitors")


def git(*args):
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def measured_commit(commit):
    """Full hash of `commit`, refusing it unless HEAD still runs the same measured code."""
    full = git("rev-parse", commit)
    subprocess.run(("git", "merge-base", "--is-ancestor", full, "HEAD"), cwd=ROOT, check=True)
    if git("diff", "--name-only", full, "HEAD", "--", *MEASURED_PATHS):
        raise ValueError(f"{' or '.join(MEASURED_PATHS)} changed since {commit}; rerun the tracks")
    if git("status", "--porcelain", "--", *MEASURED_PATHS):
        raise ValueError("uncommitted changes under the measured paths")
    return full


def environment(commit, freeze):
    return {
        "measured_commit": commit,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": sorted(line.strip() for line in freeze.read_text().splitlines()
                           if line.strip() and not line.startswith("#")),
    }


def readme(env):
    return (
        "FlahaX competitor comparison (#40)\n\n"
        f"Measured commit: {env['measured_commit']}\n"
        f"Python {env['python']} on {env['platform']}\n\n"
        "formulation.json  FlahaX vs Horticalc v0.6.7 vs Irriblend-DSW (a046d5c) and an LP after its method\n"
        "chemistry.json    FlahaX vs live PHREEQC (PhreeqPython 1.6.2) on the golden fixtures\n"
        "ec.json           EC25 against IUPAC KCl primary standards, and catalogue agreement\n"
        "environment.json  interpreter, platform and the full package list of the run\n\n"
        "Protocol: tools/competitors/README.md in the repository at the measured commit\n"
        "(benchmarks/competitors/README.md before #64).\n"
        "Timings are best of three on one machine; compare them only within this snapshot.\n")


def publish(run, commit, freeze, destination):
    env = environment(measured_commit(commit), freeze)
    files = {name: (run / name).read_bytes() for name in TRACKS}
    files["environment.json"] = (json.dumps(env, indent=2) + "\n").encode()
    files["README.txt"] = readme(env).encode()
    files["CHECKSUMS.sha256"] = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n"
                                        for name, data in sorted(files.items())).encode()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination / "evidence.zip", "w") as bundle:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))  # fixed time: reproducible bytes
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, data)
    for name, data in files.items():
        (destination / name).write_bytes(data)
    return hashlib.sha256((destination / "evidence.zip").read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="folder with the three track outputs")
    parser.add_argument("--commit", required=True, help="commit the tracks were measured at")
    parser.add_argument("--freeze", type=Path, required=True, help="pip freeze of the competitor environment")
    parser.add_argument("--snapshot", required=True, help="snapshot name, e.g. 2026-10-21-competitors-ed568c5")
    args = parser.parse_args()
    digest = publish(args.run, args.commit, args.freeze, ROOT / "docs/site/_static/benchmarks" / args.snapshot)
    print(f"evidence.zip {digest}")


if __name__ == "__main__":
    sys.exit(main())
