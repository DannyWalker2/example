#!/usr/bin/env python3
"""Add Strong app workouts to data/strong_sets.csv (one row per set).

Accepts either:
  - a shared workout as text (the "Share" button in Strong), one or several pasted together
  - the full CSV export (Profile > Settings > Export Data)

Usage:
    python3 strong_import.py workout.txt [more files...]

Safe to rerun: sets are keyed by workout start time + exercise + set number, so nothing duplicates.
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "strong_sets.csv"
COLUMNS = ["date", "workout_start", "workout_name", "exercise", "set", "weight",
           "weight_unit", "reps", "distance", "seconds", "volume"]

DATE_RX = re.compile(r"^\w+day, (\w+ \d{1,2}, \d{4}) at (\d{1,2}:\d{2} [AP]M)$")
SET_RX = re.compile(
    r"^Set (\d+):\s*(?:(?P<w>[\d.]+)\s*(?P<u>lb|kg)\s*[×x]\s*(?P<r>\d+)"
    r"|(?P<bw>\d+)\s*reps?"
    r"|(?P<plus>\+?[\d.]+)\s*(?P<pu>lb|kg)\s*[×x]\s*(?P<pr>\d+))",
    re.IGNORECASE)


def parse_share_text(text):
    rows, name, start, exercise = [], None, None, None
    # Strong uses narrow/no-break spaces (e.g. before "PM")
    text = text.replace(" ", " ").replace(" ", " ")
    lines = [l.strip() for l in text.splitlines()]
    for i, line in enumerate(lines):
        if not line or line.startswith("http"):
            continue
        m = DATE_RX.match(line)
        if m:
            start = datetime.strptime(" ".join(m.groups()), "%B %d, %Y %I:%M %p")
            name = next((l for l in reversed(lines[:i]) if l and not l.startswith("http")), None)
            exercise = None
            continue
        if start is None:
            continue
        s = SET_RX.match(line)
        if s:
            w = s.group("w") or s.group("plus")
            reps = s.group("r") or s.group("bw") or s.group("pr")
            rows.append({
                "workout_start": start.isoformat(timespec="minutes"),
                "workout_name": name,
                "exercise": exercise,
                "set": int(s.group(1)),
                "weight": float(w) if w else None,
                "weight_unit": (s.group("u") or s.group("pu") or "").lower() or None,
                "reps": int(reps) if reps else None,
            })
        elif i + 1 < len(lines) and DATE_RX.match(lines[i + 1]):
            continue  # this line is the next workout's name
        else:
            exercise = line
    return pd.DataFrame(rows)


def parse_export_csv(path):
    df = pd.read_csv(path, sep=None, engine="python")
    df.columns = [c.strip() for c in df.columns]
    df = df[pd.to_numeric(df.get("Set Order"), errors="coerce").notna()]  # drop rest-timer rows
    return pd.DataFrame({
        "workout_start": pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%dT%H:%M"),
        "workout_name": df.get("Workout Name"),
        "exercise": df.get("Exercise Name"),
        "set": pd.to_numeric(df["Set Order"]).astype(int),
        "weight": pd.to_numeric(df.get("Weight"), errors="coerce").replace(0, pd.NA),
        "weight_unit": df.get("Weight Unit", "lb"),
        "reps": pd.to_numeric(df.get("Reps"), errors="coerce").replace(0, pd.NA),
        "distance": pd.to_numeric(df.get("Distance"), errors="coerce").replace(0, pd.NA),
        "seconds": pd.to_numeric(df.get("Seconds"), errors="coerce").replace(0, pd.NA),
    })


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()

    frames = []
    for f in map(Path, args.files):
        text = f.read_text(encoding="utf-8-sig")
        df = parse_export_csv(f) if text.lstrip().startswith(("Date", '"Date')) else parse_share_text(text)
        print(f"{f.name}: {len(df)} sets")
        frames.append(df)
    new = pd.concat(frames, ignore_index=True).reindex(columns=COLUMNS)
    if new.empty:
        sys.exit("No sets found. Is this a Strong workout share or CSV export?")

    new["date"] = new["workout_start"].str[:10]
    new["volume"] = new["weight"] * new["reps"]

    OUT.parent.mkdir(exist_ok=True)
    before = 0
    if OUT.exists():
        old = pd.read_csv(OUT)
        before = len(old)
        new = pd.concat([old, new], ignore_index=True)
    keys = ["workout_start", "exercise", "set"]
    new["set"] = new["set"].astype(int)
    new = new.drop_duplicates(subset=keys, keep="last").sort_values(keys)
    new.to_csv(OUT, index=False)
    print(f"{OUT.relative_to(HERE)}: {len(new)} sets ({len(new) - before:+d}), "
          f"{new['workout_start'].nunique()} workouts")


if __name__ == "__main__":
    main()
