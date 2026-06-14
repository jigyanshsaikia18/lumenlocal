#!/usr/bin/env python3
"""PostToolUse hook for Write|Edit: auto-format the touched file.

Reads the tool-call JSON from stdin, extracts the file path, and runs:
  - black            on .py
  - prettier         on .ts / .tsx

Formatting is best-effort: if the formatter isn't installed or fails, the
hook prints a note and still exits 0 so it never blocks the workflow.
The tool has already run by the time PostToolUse fires.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path


def find_cmd(*candidates: list[str]) -> list[str] | None:
    """Return the first runnable command from a list of candidate argv lists."""
    for argv in candidates:
        if shutil.which(argv[0]):
            return argv
    return None


def run(argv: list[str], target: str) -> None:
    try:
        result = subprocess.run(
            argv + [target],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print(f"[format-files] formatted {target} with {argv[0]}", file=sys.stderr)
        else:
            print(
                f"[format-files] {argv[0]} exited {result.returncode} on {target}:\n"
                f"{result.stderr.strip()}",
                file=sys.stderr,
            )
    except Exception as exc:  # noqa: BLE001 - best-effort, never block
        print(f"[format-files] skipped {target}: {exc}", file=sys.stderr)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    file_path = payload.get("tool_input", {}).get("file_path", "") or ""
    if not file_path:
        return 0

    suffix = Path(file_path).suffix.lower()

    if suffix == ".py":
        cmd = find_cmd(["black"], [sys.executable, "-m", "black"])
        if cmd:
            run(cmd, file_path)
        else:
            print("[format-files] black not installed; skipping .py format", file=sys.stderr)

    elif suffix in (".ts", ".tsx"):
        # Prefer a local/global prettier binary, fall back to npx.
        cmd = find_cmd(["prettier", "--write"], ["npx", "--no-install", "prettier", "--write"])
        if cmd:
            run(cmd, file_path)
        else:
            print("[format-files] prettier not available; skipping .ts/.tsx format", file=sys.stderr)

    # Always succeed — formatting must never block the edit.
    return 0


if __name__ == "__main__":
    sys.exit(main())
