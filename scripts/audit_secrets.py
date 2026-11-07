"""Scan current tracked files and every reachable Git tree with detect-secrets.

Never print candidates or hashes. Network verification is disabled. Reports only
revision, path, line and detector type. Binary database contents need a separate
schema/count review; this detector is not an assurance of absence of secrets.
Run: backend/.venv/Scripts/python scripts/audit_secrets.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def scan_tree(revision):
    with tempfile.TemporaryDirectory(prefix="pricelurk-audit-") as folder:
        target = Path(folder)
        if revision == "WORKTREE":
            paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
            for name in paths:
                source = ROOT / name
                if not name or not source.is_file():
                    continue
                dest = target / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
        else:
            entries = git("ls-tree", "-r", "--full-tree", revision).decode().splitlines()
            for entry in entries:
                metadata, name = entry.split("\t", 1)
                blob = metadata.split()[2]
                dest = target / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(git("cat-file", "blob", blob))
        result = subprocess.run([sys.executable, "-m", "detect_secrets", "scan", "--all-files", "--no-verify", "."],
                                cwd=target, capture_output=True, check=True)
        data = json.loads(result.stdout)
        return [{"revision": revision, "path": name, "line": finding["line_number"], "type": finding["type"]}
                for name, findings in data["results"].items() for finding in findings]


def main():
    revisions = git("rev-list", "--all").decode().splitlines()
    findings = []
    for revision in ["WORKTREE", *revisions]:
        findings.extend(scan_tree(revision))
    print(json.dumps({"tool": "detect-secrets", "network_verification": False,
                      "revisions_scanned": len(revisions), "findings": findings}, indent=2))


if __name__ == "__main__":
    main()
