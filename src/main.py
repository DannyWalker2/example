"""
main.py - runs the whole job finder.

    python src/main.py            # normal run
    python src/main.py --test     # only check each firm answers (writes errors.md)

Steps: read firms.yaml -> fetch every firm in parallel -> filter + score ->
skip applied / already-seen -> write jobs.md, errors.md, new_jobs.md, seen.json.
"""
import json
import os
import re
import sys
import traceback
import concurrent.futures as cf
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import fetchers  # noqa: E402
import rules     # noqa: E402
import claude_rate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
MIN_SCORE = 30
REPO_URL = (os.environ.get("GITHUB_SERVER_URL", "https://github.com") + "/" +
            os.environ.get("GITHUB_REPOSITORY", "DannyWalker2/example"))  # jobs scoring below this are hidden as noise


# ---------------------------------------------------------------- inputs
def load_firms():
    data = yaml.safe_load((ROOT / "firms.yaml").read_text())
    return [f for f in data["firms"] if f.get("ats") and f.get("endpoint") and not f.get("disabled")]


def norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower().replace("&", " and ")).split()


STOP = set("the and of a an to in for program programme analyst full time 2027 us inc co group "
           "llc bank capital markets".split())


def load_applied():
    """
    applied.txt lines can be:
        FirmName                 -> deprioritize every role at that firm
        FirmName | Role title    -> hide roles at that firm whose title matches
        R-123456                 -> hide that exact job ID
    """
    entries = []
    for raw in (ROOT / "applied.txt").read_text().splitlines():
        line = raw.split("#")[0].strip() if raw.strip().startswith("#") else raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 1 and re.fullmatch(r"[A-Za-z]{0,4}[-_]?\d{4,}[\w-]*", parts[0]):
            entries.append({"job_id": parts[0]})
        else:
            entries.append({"firm": parts[0], "role": parts[1] if len(parts) > 1 else ""})
    return entries


def firm_matches(applied_firm, firm_name, aliases):
    a = " ".join(t for t in norm(applied_firm) if t not in {"the", "and", "co", "inc"})
    names = [firm_name] + list(aliases or [])
    for n in names:
        b = " ".join(t for t in norm(n) if t not in {"the", "and", "co", "inc"})
        if a and b and (a == b or re.search(rf"\b{re.escape(a)}\b", b) or re.search(rf"\b{re.escape(b)}\b", a)):
            return True
    return False


def applied_status(job, firm_cfg, applied):
    """Returns 'hide', 'firm', or ''."""
    status = ""
    title_words = set(norm(job["title"])) - STOP
    for e in applied:
        if e.get("job_id"):
            if e["job_id"].lower() == job["job_id"].lower():
                return "hide"
            continue
        if not firm_matches(e["firm"], job["firm"], firm_cfg.get("aliases")):
            continue
        if not e["role"]:
            status = "firm"
            continue
        role_words = set(norm(e["role"])) - STOP
        if role_words and len(role_words & title_words) / len(role_words) >= 0.6:
            return "hide"
        status = "firm"
    return status


def load_seen():
    p = ROOT / "seen.json"
    return json.loads(p.read_text()) if p.exists() and p.read_text().strip() else {}


# ---------------------------------------------------------------- outputs
def md_escape(s):
    return (s or "").replace("|", "/").replace("\n", " ").strip()


def table(jobs, with_claude):
    head = "| Score | Firm | Role | Location | Posted | Start | Exp | Job ID | Why |"
    sep = "|---|---|---|---|---|---|---|---|---|"
    if with_claude:
        head = head[:-1] + " Claude | Why apply |"
        sep += "---|---|"
    rows = [head, sep]
    for j in jobs:
        new = " **NEW**" if j.get("is_new") else ""
        row = (f"| {j['score']}{new} | {md_escape(j['firm'])} | [{md_escape(j['title'])}]({j['url']}) | "
               f"{md_escape(j['location'])[:60]} | {j['posted'] or '?'} | {j['start']} | {j['exp']} | "
               f"{md_escape(j['job_id'])} | {md_escape(j['reason'])} |")
        if with_claude:
            row += f" {j.get('claude_score', '')} | {md_escape(j.get('claude_note', ''))} |"
        rows.append(row)
    return "\n".join(rows)


def sort_key(j):
    """New this run first, then highest score, then most recently posted."""
    posted = int(j["posted"].replace("-", "")) if j.get("posted") else 0
    return (not j.get("is_new"), -j["score"], -posted)


def write_outputs(matches, new, errors, stats, with_claude):
    main = sorted([j for j in matches if j["section"] == "main" and not j["applied_firm"]], key=sort_key)
    deprior = sorted([j for j in matches if j["section"] == "main" and j["applied_firm"]], key=sort_key)
    ma = sorted([j for j in matches if j["section"] == "ma"], key=sort_key)

    parts = [f"# Job matches", "",
             f"Last run: {NOW}. Firms checked: {stats['ok']} OK, {stats['failed']} failed "
             f"(see [errors.md](errors.md)). Matches: {len(matches)}, new this run: {len(new)}.", "",
             "Sorted: new this run first, then by score. Score is 0-100 from the rules in `src/rules.py`.", "",
             "## Best matches", "", table(main, with_claude) if main else "_None right now._", ""]
    if deprior:
        parts += ["## At firms you already applied to (different roles)", "", table(deprior, with_claude), ""]
    if ma:
        parts += ["## Low priority: M&A / advisory only", "", table(ma, with_claude), ""]
    (ROOT / "jobs.md").write_text("\n".join(parts))

    # errors.md
    lines = [f"# Firms that could not be checked", "", f"Last run: {NOW}", ""]
    if errors:
        lines += ["| Firm | ATS | Problem |", "|---|---|---|"]
        lines += [f"| {e['firm']} | {e['ats']} | {md_escape(e['error'])[:200]} |" for e in errors]
    else:
        lines += ["All firms answered."]
    (ROOT / "errors.md").write_text("\n".join(lines) + "\n")

    # new_jobs.md -> body of the GitHub Issue
    new_sorted = sorted(new, key=sort_key)
    body = [f"**{len(new)} new matching job(s)** found {NOW}.", "",
            table(new_sorted, with_claude), "",
            f"Full list: [jobs.md]({REPO_URL}/blob/HEAD/jobs.md). "
            f"Firms that could not be checked: [errors.md]({REPO_URL}/blob/HEAD/errors.md).",
            "", "To hide a job, add its Job ID (or `Firm | Role`) to applied.txt."]
    (ROOT / "new_jobs.md").write_text("\n".join(body) + "\n")


# ---------------------------------------------------------------- main
def fetch_all(firms):
    results, errors = {}, []

    def one(f):
        try:
            return f, fetchers.fetch(f), None
        except Exception as e:  # any failure is logged, never fatal
            msg = f"{type(e).__name__}: {e}"
            return f, None, msg

    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for f, jobs, err in ex.map(one, firms):
            if err:
                errors.append({"firm": f["name"], "ats": f["ats"], "error": err})
                print(f"  FAIL {f['name']}: {err[:150]}")
            else:
                results[f["name"]] = jobs
                print(f"  ok   {f['name']}: {len(jobs)} postings pulled")
    return results, errors


def run(test_only=False):
    firms = load_firms()
    print(f"Checking {len(firms)} firms...")
    results, errors = fetch_all(firms)
    stats = {"ok": len(results), "failed": len(errors)}
    if test_only:
        write_outputs([], [], errors, stats, False)
        return

    applied = load_applied()
    seen = load_seen()
    by_name = {f["name"]: f for f in firms}
    matches, dropped = [], {}
    for firm_name, jobs in results.items():
        fcfg = by_name[firm_name]
        uniq = {}
        for j in jobs:
            uniq.setdefault(j["job_id"] or j["url"], j)
        for j in uniq.values():
            info = rules.check(j)
            if not info["keep"]:
                dropped[info["dropped"]] = dropped.get(info["dropped"], 0) + 1
                continue
            status = applied_status(j, fcfg, applied)
            if status == "hide":
                dropped["in applied.txt"] = dropped.get("in applied.txt", 0) + 1
                continue
            j.update(start=info["start"], exp=info["exp"], section=info["section"],
                     applied_firm=(status == "firm"))
            j["score"], j["reason"] = rules.score(j, info, j["applied_firm"])
            if j["score"] < MIN_SCORE:
                dropped["low score"] = dropped.get("low score", 0) + 1
                continue
            j["key"] = f"{firm_name}|{j['job_id'] or j['url']}"
            j["is_new"] = j["key"] not in seen
            matches.append(j)

    new = [j for j in matches if j["is_new"]]
    with_claude = claude_rate.enabled()
    if with_claude:
        claude_rate.rate(new, seen)  # only rates new jobs, re-uses saved ratings for old ones
        for j in matches:
            if not j["is_new"] and j["key"] in seen:
                j["claude_score"] = seen[j["key"]].get("claude_score", "")
                j["claude_note"] = seen[j["key"]].get("claude_note", "")

    for j in matches:
        rec = seen.setdefault(j["key"], {"first_seen": TODAY})
        rec.update(firm=j["firm"], title=j["title"], url=j["url"], job_id=j["job_id"],
                   posted=j["posted"], last_seen=TODAY, score=j["score"])
        if j.get("claude_score"):
            rec.update(claude_score=j["claude_score"], claude_note=j.get("claude_note", ""))
    (ROOT / "seen.json").write_text(json.dumps(seen, indent=1, sort_keys=True))

    write_outputs(matches, new, errors, stats, with_claude)
    print(f"\nMatches: {len(matches)}  New: {len(new)}  Firms failed: {len(errors)}")
    print("Dropped by rule:", json.dumps(dict(sorted(dropped.items(), key=lambda x: -x[1]))))
    # Tell GitHub Actions how many new jobs there are (used to decide on the Issue).
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"new_count={len(new)}\n")


if __name__ == "__main__":
    try:
        run(test_only="--test" in sys.argv)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
