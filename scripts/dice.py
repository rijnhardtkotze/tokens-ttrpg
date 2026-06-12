#!/usr/bin/env python3
"""Provably fair dice: rolls derived from a merge commit SHA.

Per die i (0-based) of roll `action_id` in PR `pr_number`:
    v = uint64_be(HMAC_SHA256(key=sha_utf8, msg=f"{pr}:{action_id}:{i}:{counter}")[0:8])
with rejection sampling (rehash while v >= floor(2^64/S)*S) so there is no
modulo bias. Deterministic: anyone can re-run any roll forever.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys

EXPR_RE = re.compile(r"^(\d{1,2})d(\d{1,3})([+-]\d{1,2})?$")
ACTION_ID_RE = re.compile(r"^[a-z0-9-]{1,40}$")
ALLOWED_SIDES = {2, 4, 6, 8, 10, 12, 20, 100}
MAX_DICE = 20


class DiceError(ValueError):
    pass


def parse_expr(expr: str) -> tuple[int, int, int]:
    m = EXPR_RE.match(expr.strip())
    if not m:
        raise DiceError(f"bad expression '{expr}' (grammar: NdS[+M|-M])")
    n, sides, mod = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if not 1 <= n <= MAX_DICE:
        raise DiceError(f"'{expr}': dice count must be 1..{MAX_DICE}")
    if sides not in ALLOWED_SIDES:
        raise DiceError(f"'{expr}': sides must be one of {sorted(ALLOWED_SIDES)}")
    return n, sides, mod


def roll_die(entropy: str, pr_number: int, action_id: str, index: int, sides: int) -> int:
    limit = (2**64 // sides) * sides
    counter = 0
    while True:
        msg = f"{pr_number}:{action_id}:{index}:{counter}".encode()
        digest = hmac.new(entropy.lower().encode(), msg, hashlib.sha256).digest()
        v = int.from_bytes(digest[:8], "big")
        if v < limit:
            return v % sides + 1
        counter += 1


def roll(entropy: str, pr_number: int, action_id: str, expr: str) -> dict:
    if not ACTION_ID_RE.match(action_id):
        raise DiceError(f"bad action id '{action_id}' (must match [a-z0-9-]{{1,40}})")
    n, sides, mod = parse_expr(expr)
    dice = [roll_die(entropy, pr_number, action_id, i, sides) for i in range(n)]
    return {"action_id": action_id, "expr": expr.strip(), "dice": dice, "total": sum(dice) + mod}


def parse_rolls_block(pr_body: str) -> list[tuple[str, str, str]]:
    """Extract (action_id, expr, purpose) from the ```rolls fenced block in a PR body."""
    m = re.search(r"```rolls\s*\n(.*?)```", pr_body or "", re.DOTALL)
    if not m:
        return []
    out, seen = [], set()
    for line in m.group(1).splitlines():
        line, _, comment = line.partition("#")
        line = line.strip()
        if not line:
            continue
        action_id, sep, expr = (part.strip() for part in line.partition(":"))
        if not sep:
            raise DiceError(f"rolls line '{line}' missing ':' separator")
        if action_id in seen:
            raise DiceError(f"duplicate action id '{action_id}' in rolls block")
        seen.add(action_id)
        parse_expr(expr)  # validate early
        if not ACTION_ID_RE.match(action_id):
            raise DiceError(f"bad action id '{action_id}' (must match [a-z0-9-]{{1,40}})")
        out.append((action_id, expr, comment.strip()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entropy", required=True, help="merge commit SHA (hex)")
    ap.add_argument("--pr", required=True, type=int)
    ap.add_argument("--id", required=True, dest="action_id")
    ap.add_argument("--expr", required=True)
    args = ap.parse_args()
    try:
        print(json.dumps(roll(args.entropy, args.pr, args.action_id, args.expr)))
    except DiceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
