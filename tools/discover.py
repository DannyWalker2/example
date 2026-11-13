"""
discover.py - helper that figures out which job system (ATS) a firm uses.

Usage:  python tools/discover.py "Firm Name" https://careers.firm.com [tenant-guess ...]

It (1) downloads the careers page and looks for links to known job systems,
and (2) tries common Workday / Greenhouse / Lever / Ashby / SmartRecruiters
addresses built from the guesses. Anything that answers with real jobs is printed.
Run it in GitHub Actions or on your own computer (it needs normal internet).
"""
import json, re, sys, concurrent.futures as cf
import requests

UA = {"User-Agent": "Mozilla/5.0 (job-finder discovery)", "Accept": "application/json,text/html"}
ATS_PATTERNS = [
    r"https?://[\w.-]+\.myworkdayjobs\.com/[\w/-]+",
    r"https?://[\w.-]+\.myworkdaysite\.com/[\w/-]+",
    r"https?://(?:boards|job-boards)\.greenhouse\.io/[\w-]+",
    r"https?://jobs\.lever\.co/[\w-]+",
    r"https?://jobs\.ashbyhq\.com/[\w-]+",
    r"https?://(?:careers|jobs)\.smartrecruiters\.com/[\w-]+",
    r"https?://[\w.-]+\.icims\.com",
    r"https?://[\w.-]+\.eightfold\.ai",
    r"https?://[\w.-]+\.oraclecloud\.com/hcmUI/CandidateExperience/[\w/-]+",
    r"https?://[\w.-]+\.taleo\.net/[\w/.-]+",
    r"https?://[\w.-]+\.successfactors\.com/[\w/.-]*",
    r"https?://[\w.-]+\.avature\.net/[\w/-]*",
    r"https?://cdn\.phenompeople\.com/[\w/-]+",
    r"phApp\.ddo|\"refNum\":\"[\w]+\"",
]
WD_SITES = ["External", "Careers", "careers", "External_Careers", "Search", "jobs", "Campus",
            "University", "Early_Careers", "ExternalCareerSite", "External_Career_Site"]


def scan_page(url):
    try:
        r = requests.get(url, headers=UA, timeout=20)
        found = set()
        for p in ATS_PATTERNS:
            found.update(m[:140] for m in re.findall(p, r.text))
        return f"page {url} -> {r.status_code}, final={r.url[:120]}, ats_links={sorted(found)[:15]}"
    except Exception as e:
        return f"page {url} -> ERROR {type(e).__name__}"


def try_workday(tenant, wd, site):
    url = f"https://{tenant}.wd{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    try:
        r = requests.post(url, json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
                          headers=UA, timeout=15)
        if r.ok and "total" in r.text:
            return f"WORKDAY OK {url} total={r.json().get('total')}"
    except Exception:
        pass
    return None


def try_simple(kind, slug):
    urls = {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        "lever": f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
        "smartrecruiters": f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1",
    }
    url = urls[kind]
    try:
        r = requests.get(url, headers=UA, timeout=15)
        if r.ok:
            d = r.json()
            n = len(d.get("jobs", [])) if isinstance(d, dict) and "jobs" in d else (
                d.get("totalFound") if isinstance(d, dict) else len(d))
            if n:
                return f"{kind.upper()} OK {url} count={n}"
    except Exception:
        pass
    return None


def workday_root(tenant, wd):
    """The bare Workday host often redirects to the firm's default career site."""
    try:
        r = requests.get(f"https://{tenant}.wd{wd}.myworkdayjobs.com/", headers=UA, timeout=15)
        if r.ok and r.url.rstrip("/") != f"https://{tenant}.wd{wd}.myworkdayjobs.com":
            return f"workday root {tenant}.wd{wd} -> {r.url}"
    except Exception:
        pass
    return None


def discover(name, page, guesses, wd_sites=None):
    out = [f"### {name}", scan_page(page) if page else "page -> (none)"]
    for g in guesses:
        for wd in (1, 3, 5, 12, 10, 501):
            hit = workday_root(g, wd)
            if hit:
                out.append(hit)
    tasks = []
    with cf.ThreadPoolExecutor(8) as ex:
        for g in guesses:
            for wd in (1, 5, 3, 12, 10):
                for s in (wd_sites or []) + WD_SITES:
                    tasks.append(ex.submit(try_workday, g, wd, s))
            for k in ("greenhouse", "lever", "ashby", "smartrecruiters"):
                tasks.append(ex.submit(try_simple, k, g))
        hits = sorted({t.result() for t in tasks if t.result()})
    out += hits or ["no API hits"]
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1].endswith(".json"):
        # batch mode: list of [name, page, [guesses], [extra workday site names]]
        rows = json.load(open(sys.argv[1]))
        with cf.ThreadPoolExecutor(2) as ex:
            for res in ex.map(lambda r: discover(r[0], r[1], r[2], r[3] if len(r) > 3 else None), rows):
                print(res, flush=True)
    else:
        print(discover(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None, sys.argv[3:]))
