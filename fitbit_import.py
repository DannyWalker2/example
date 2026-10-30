#!/usr/bin/env python3
"""Turn a Google Takeout Fitbit export (.zip) into clean CSVs in ./data.

Usage:
    python3 fitbit_import.py                    # uses the newest .zip in this folder
    python3 fitbit_import.py path/to/takeout.zip
    python3 fitbit_import.py --days 90          # only keep the last 90 days

Safe to rerun on newer exports: rows are merged by date (or log id), never duplicated.
"""

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"


# ---------- helpers ----------

def parse_dt(s):
    """Fitbit exports use '10/28/26 23:15:00' or ISO '2026-10-28T23:15:00.000'."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%m/%d/%y %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s.replace("Z", "").split("+")[0], fmt)
        except ValueError:
            pass
    return None


def files_matching(zf, pattern):
    rx = re.compile(pattern, re.IGNORECASE)
    return sorted(n for n in zf.namelist() if rx.search(n.rsplit("/", 1)[-1]))


def read_json(zf, name):
    with zf.open(name) as f:
        return json.load(f)


def read_csv(zf, name):
    with zf.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))


def ms_to_min(v):
    return round(float(v) / 60000, 1) if v not in (None, "") else None


# ---------- parsers ----------

def parse_sleep(zf):
    rows = []
    for name in files_matching(zf, r"^sleep-\d{4}-\d{2}-\d{2}\.json$"):
        for s in read_json(zf, name):
            summary = (s.get("levels") or {}).get("summary") or {}
            stage = lambda k: (summary.get(k) or {}).get("minutes")
            rows.append({
                "log_id": s.get("logId"),
                "date": s.get("dateOfSleep"),
                "start_time": s.get("startTime"),
                "end_time": s.get("endTime"),
                "is_main_sleep": s.get("mainSleep"),
                "type": s.get("type"),
                "minutes_asleep": s.get("minutesAsleep"),
                "minutes_awake": s.get("minutesAwake"),
                "time_in_bed": s.get("timeInBed"),
                "minutes_to_fall_asleep": s.get("minutesToFallAsleep"),
                "efficiency": s.get("efficiency"),
                # "stages" logs have deep/light/rem/wake; older "classic" logs have asleep/restless/awake
                "deep_min": stage("deep"),
                "light_min": stage("light"),
                "rem_min": stage("rem"),
                "wake_min": stage("wake") if stage("wake") is not None else stage("awake"),
                "restless_min": stage("restless"),
            })
    df = pd.DataFrame(rows)

    scores = []
    for name in files_matching(zf, r"^sleep_score.*\.csv$"):
        for r in read_csv(zf, name):
            scores.append({
                "log_id": pd.to_numeric(r.get("sleep_log_entry_id"), errors="coerce"),
                "sleep_score": pd.to_numeric(r.get("overall_score"), errors="coerce"),
                "composition_score": pd.to_numeric(r.get("composition_score"), errors="coerce"),
                "revitalization_score": pd.to_numeric(r.get("revitalization_score"), errors="coerce"),
                "duration_score": pd.to_numeric(r.get("duration_score"), errors="coerce"),
            })
    if not df.empty and scores:
        sc = pd.DataFrame(scores).dropna(subset=["log_id"]).drop_duplicates("log_id")
        df["log_id"] = pd.to_numeric(df["log_id"], errors="coerce")
        df = df.merge(sc, on="log_id", how="left")
    return df, ["log_id"]


def parse_steps(zf):
    daily = {}
    for name in files_matching(zf, r"^steps-\d{4}-\d{2}-\d{2}\.json$"):
        for p in read_json(zf, name):
            dt = parse_dt(p.get("dateTime"))
            if dt:
                d = dt.date().isoformat()
                daily[d] = daily.get(d, 0) + int(float(p.get("value", 0)))
    df = pd.DataFrame([{"date": d, "steps": v} for d, v in daily.items()])
    return df, ["date"]


def parse_resting_hr(zf):
    rows = []
    for name in files_matching(zf, r"^resting_heart_rate-\d{4}-\d{2}-\d{2}\.json$"):
        for p in read_json(zf, name):
            v = p.get("value") or {}
            bpm = v.get("value") if isinstance(v, dict) else v
            dt = parse_dt((v.get("date") if isinstance(v, dict) else None) or p.get("dateTime"))
            if dt and bpm:  # Fitbit writes 0 on days it could not compute RHR
                rows.append({"date": dt.date().isoformat(), "resting_hr": round(float(bpm), 1)})
    return pd.DataFrame(rows), ["date"]


def parse_hrv(zf):
    rows = []
    for name in files_matching(zf, r"^Daily Heart Rate Variability Summary.*\.csv$"):
        for r in read_csv(zf, name):
            dt = parse_dt(r.get("timestamp"))
            if dt:
                rows.append({
                    "date": dt.date().isoformat(),
                    "hrv_rmssd_ms": pd.to_numeric(r.get("rmssd"), errors="coerce"),
                    "nrem_hr": pd.to_numeric(r.get("nremhr"), errors="coerce"),
                    "entropy": pd.to_numeric(r.get("entropy"), errors="coerce"),
                })
    return pd.DataFrame(rows), ["date"]


def parse_workouts(zf):
    rows = []
    for name in files_matching(zf, r"^exercise-\d+\.json$"):
        for e in read_json(zf, name):
            start = parse_dt(e.get("startTime"))
            rows.append({
                "log_id": e.get("logId"),
                "date": start.date().isoformat() if start else None,
                "start_time": start.isoformat() if start else e.get("startTime"),
                "activity": e.get("activityName"),
                "duration_min": ms_to_min(e.get("activeDuration") or e.get("duration")),
                "calories": e.get("calories"),
                "avg_hr": e.get("averageHeartRate"),
                "steps": e.get("steps"),
                "distance": e.get("distance"),
                "distance_unit": e.get("distanceUnit"),
                "elevation_gain": e.get("elevationGain"),
                "log_type": e.get("logType"),  # auto_detected / manual / tracker
            })
    return pd.DataFrame(rows), ["log_id"]


PARSERS = {
    "sleep": parse_sleep,
    "steps": parse_steps,
    "resting_heart_rate": parse_resting_hr,
    "hrv": parse_hrv,
    "workouts": parse_workouts,
}


# ---------- merge + save ----------

def merge_and_save(name, new, keys, since):
    path = DATA_DIR / f"{name}.csv"
    if new.empty:
        print(f"  {name:20s} no data found in export")
        return
    if since and "date" in new:
        new = new[new["date"] >= since]
    before = 0
    if path.exists():
        old = pd.read_csv(path)
        before = len(old)
        # Newer export wins when the same day/log appears twice
        new = pd.concat([old, new], ignore_index=True)
    for k in keys:
        new[k] = new[k].astype(str)
    new = new.drop_duplicates(subset=keys, keep="last").sort_values(
        ["date"] + [k for k in keys if k != "date"] if "date" in new else keys)
    new.to_csv(path, index=False)
    print(f"  {name:20s} {len(new):6d} rows ({len(new) - before:+d})  "
          f"{new['date'].min()} to {new['date'].max()}" if "date" in new else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zip", nargs="?", help="Takeout zip (default: newest .zip in this folder)")
    ap.add_argument("--days", type=int, help="only keep the last N days")
    args = ap.parse_args()

    if args.zip:
        zips = [Path(args.zip)]
    else:
        zips = sorted(HERE.glob("*.zip"), key=lambda p: p.stat().st_mtime)[-1:]
    if not zips or not zips[0].exists():
        sys.exit("No Takeout .zip found. Drop it into this folder or pass its path.")

    since = (date.today() - timedelta(days=args.days)).isoformat() if args.days else None
    DATA_DIR.mkdir(exist_ok=True)
    print(f"Reading {zips[0].name}")
    with zipfile.ZipFile(zips[0]) as zf:
        if not any("fitbit" in n.lower() for n in zf.namelist()):
            print("  Warning: no 'Fitbit' folder in this zip; is it the right export?")
        for name, parser in PARSERS.items():
            df, keys = parser(zf)
            merge_and_save(name, df, keys, since)
    print(f"Done. CSVs are in {DATA_DIR}")


if __name__ == "__main__":
    main()
