#!/usr/bin/env python3
"""Read-only snapshot of a MetaMask Agent Wallet, for a dashboard.

Runs a few `mm ... --json` commands and writes their output, with a timestamp
and some simple alerts, to one JSON file. Run it from cron or launchd every
15 minutes or so, and point your dashboard at the file.

It never runs anything that moves money or changes the wallet: no transfer,
swap, policy set or trading-mode set. Keep it that way.

The output holds balances and addresses, so keep it out of git.

Settings (environment variables, all optional):
  MM_BIN             path to the mm CLI (cron and launchd often have a short PATH)
  AGENTWALLET_OUT    output file (default ~/agent-wallet/agentwallet.json)
  AGENTWALLET_CHAIN  chain id for the balance (default 8453, Base)
  AGENTWALLET_CAP    the daily cap you set, in USD (default 10)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

OUT = os.path.expanduser(os.environ.get("AGENTWALLET_OUT", "~/agent-wallet/agentwallet.json"))
MM = os.environ.get("MM_BIN") or shutil.which("mm")
CHAIN = os.environ.get("AGENTWALLET_CHAIN", "8453")
CAP = float(os.environ.get("AGENTWALLET_CAP", "10"))

# Read-only commands only.
COMMANDS = {
    "balance": ["wallet", "balance", "--chain-ids", CHAIN],
    "pending": ["wallet", "requests", "list"],
    "history": ["tx", "history", "--limit", "5"],
    "mode": ["wallet", "trading-mode", "get"],
    "policy": ["wallet", "policy", "get"],
    "doctor": ["doctor"],
}


def run(args):
    proc = subprocess.run([MM, *args, "--json"], capture_output=True, text=True, timeout=90)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip() or "exit %d" % proc.returncode)
    return json.loads(proc.stdout)


def count_items(obj):
    """Count entries in a list-shaped response, whatever key it uses."""
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        for value in obj.values():
            if isinstance(value, list):
                return len(value)
    return 0


def daily_cap(policy):
    """Find rolling_24h in the policy output; None means no limit."""
    text = json.dumps(policy)
    match = re.search(r"rolling_24h\\?\"?:\s*\\?\"?(null|[0-9.]+)", text)
    if not match:
        return "unknown"
    return None if match.group(1) == "null" else float(match.group(1))


def alerts(snap):
    out = []
    if count_items(snap.get("pending")):
        out.append("approval waiting on your phone")
    if "beast" in json.dumps(snap.get("mode", "")).lower():
        out.append("wallet is in Beast Mode")
    cap = daily_cap(snap.get("policy"))
    if cap is None or (isinstance(cap, float) and cap > CAP):
        out.append("daily cap raised or removed")
    doctor = snap.get("doctor") or {}
    if isinstance(doctor, dict) and (doctor.get("authenticated") is False or doctor.get("initialized") is False):
        out.append("CLI not signed in or not initialised")
    out.extend("%s check failed" % name for name, err in snap.get("errors", {}).items())
    return out


def main():
    if not MM:
        print("mm not found; set MM_BIN", file=sys.stderr)
        return 1

    snap, errors = {}, {}
    for name, args in COMMANDS.items():
        try:
            snap[name] = run(args)
        except Exception as exc:  # one failing command shouldn't sink the rest
            errors[name] = str(exc)[:300]

    if len(errors) == len(COMMANDS):
        print("every mm command failed; keeping the old file", file=sys.stderr)
        return 1

    snap["errors"] = errors
    snap["alerts"] = alerts(snap)
    snap["generated"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    # Atomic write: the dashboard never sees a half-written file.
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(OUT), suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(snap, fh, indent=2)
    os.replace(tmp, OUT)
    print("%s: %d alert(s), %d error(s)" % (snap["generated"], len(snap["alerts"]), len(errors)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
