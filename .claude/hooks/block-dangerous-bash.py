#!/usr/bin/env python3
"""PreToolUse hook for Bash: deny destructive commands.

Reads the tool-call JSON from stdin. If the proposed command matches a
dangerous pattern (rm -rf, DROP TABLE, git force-push), it prints an
explanation to stderr and exits 2, which tells Claude Code to BLOCK the
call and feed stderr back to the model. Any other exit code allows it.
"""
import json
import re
import sys

# (label, compiled regex) — matched case-insensitively against the command.
PATTERNS = [
    # rm -rf / rm -fr / rm -r -f, in any flag order
    ("rm -rf (recursive force delete)",
     re.compile(r"\brm\b[^\n|;&]*\s-[a-z]*r[a-z]*f|\brm\b[^\n|;&]*\s-[a-z]*f[a-z]*r", re.I)),
    # DROP TABLE (also catches DROP TABLE IF EXISTS)
    ("DROP TABLE (destructive SQL)",
     re.compile(r"\bdrop\s+table\b", re.I)),
    # git force push: --force, --force-with-lease, or -f on a push
    ("git force push",
     re.compile(r"\bgit\b[^\n|;&]*\bpush\b[^\n|;&]*(--force|--force-with-lease|\s-f\b)|"
                r"\bgit\b[^\n|;&]*(--force|--force-with-lease|\s-f\b)[^\n|;&]*\bpush\b", re.I)),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # If we can't parse input, don't block — fail open.
        return 0

    command = payload.get("tool_input", {}).get("command", "") or ""

    for label, rx in PATTERNS:
        if rx.search(command):
            print(
                f"BLOCKED by block-dangerous-bash hook: command matches "
                f"\"{label}\".\n"
                f"Command: {command}\n"
                f"This pattern is denied by project policy (see CLAUDE.md). "
                f"If this is genuinely required, ask the user to run it manually.",
                file=sys.stderr,
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
