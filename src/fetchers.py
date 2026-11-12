"""
fetchers.py - one small function per job system (ATS).

Every fetcher takes a firm entry from firms.yaml and returns a list of jobs.
Each job is a plain dict with the same keys, no matter which ATS it came from:

    firm, tier, ats, job_id, title, location, country, posted (YYYY-MM-DD or ""),
    url (direct apply / posting link), description (plain text), time_type

Nothing here invents data: every field is copied from the ATS's own JSON.
If a site cannot be reached, the fetcher raises an error and main.py logs it.
"""
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; personal-job-finder/1.0)",
    "Accept": "application/json",
    "Accept-Language": "en-US",
}
TIMEOUT = 30

# Words we search for on big sites (Workday, Oracle, etc.) so we only pull
# campus / entry-level postings instead of thousands of jobs.
DEFAULT_SEARCHES = ["2027", "analyst program", "development program", "graduate program",
                    "rotational", "campus", "new grad", "early career"]

# Titles that are obviously not for us; skipped before we download the full posting
# (saves time on huge sites). Full filtering happens later in filters.py.
QUICK_SKIP = re.compile(r"\b(intern|internship|summer|co-?op|director|vice president|vp|avp|"
                        r"managing director|svp|evp|senior|sr\.?|principal|head of|lead|manager|"
                        r"software|engineer|developer|cyber|teller|branch|personal banker|"
                        r"financial advisor|nurse|technician)\b", re.I)


def strip_html(text):
    """Turn an HTML job description into plain text."""
    text = html.unescape(text or "")
    text = re.sub(r"<(br|p|li|div|h\d)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t\xa0]+", " ", text).strip()


def _date(value):
    """Normalize many date formats to YYYY-MM-DD ('' if unknown)."""
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):  # epoch seconds or milliseconds
        secs = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(secs, tz=timezone.utc).strftime("%Y-%m-%d")
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(value))
    return m.group(1) if m else ""


def _relative_date(text):
    """Workday list pages say 'Posted 3 Days Ago'. Convert to a date."""
    if not text:
        return ""
    today = datetime.now(timezone.utc)
    t = text.lower()
    if "today" in t:
        return today.strftime("%Y-%m-%d")
    if "yesterday" in t:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.search(r"(\d+)\+?\s*day", t)
    if m:
        return (today - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    return ""


def _job(firm, **kw):
    base = {"firm": firm["name"], "tier": firm.get("tier", 2), "ats": firm["ats"],
            "job_id": "", "title": "", "location": "", "country": "", "posted": "",
            "url": "", "description": "", "time_type": "", "pay_text": ""}
    base.update({k: (v if v is not None else "") for k, v in kw.items()})
    base["job_id"] = str(base["job_id"])
    return base


def _searches(firm):
    return firm.get("searches") or DEFAULT_SEARCHES


# --------------------------------------------------------------------------- Workday
def fetch_workday(firm):
    """
    Workday career sites have a hidden JSON API:
      POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
    firms.yaml stores the full 'endpoint' (everything up to /jobs).
    """
    endpoint = firm["endpoint"].rstrip("/")
    root = endpoint.split("/wday/")[0]
    site = endpoint.rstrip("/").split("/")[-1]
    session = requests.Session()
    session.headers.update(HEADERS)
    found = {}
    for query in _searches(firm):
        for offset in range(0, 100, 20):  # at most 100 results per search word
            body = {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": query}
            r = session.post(endpoint + "/jobs", json=body, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            postings = data.get("jobPostings", [])
            for p in postings:
                path = p.get("externalPath", "")
                if path and path not in found:
                    found[path] = p
            if len(postings) < 20 or offset + 20 >= data.get("total", 0):
                break
    def detail(item):
        path, p = item
        title = p.get("title", "")
        # Download the full posting for description, exact date, country, job ID.
        info = {}
        try:
            d = session.get(endpoint + path, timeout=TIMEOUT)
            if d.ok:
                info = d.json().get("jobPostingInfo", {})
        except (requests.RequestException, ValueError):
            pass
        locs = [info.get("location") or p.get("locationsText", "")] + info.get("additionalLocations", [])
        country = (info.get("country") or {}).get("descriptor", "")
        job_id = info.get("jobReqId") or (p.get("bulletFields") or [""])[0] or path.split("_")[-1]
        return _job(
            firm, job_id=job_id, title=title,
            location="; ".join(x for x in locs if x),
            country=country,
            posted=_date(info.get("startDate")) or _relative_date(p.get("postedOn")),
            url=info.get("externalUrl") or f"{root}/{site}{path}",
            description=strip_html(info.get("jobDescription", "")),
            time_type=info.get("timeType", ""),
        )

    todo = [(path, p) for path, p in found.items() if not QUICK_SKIP.search(p.get("title", ""))]
    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(detail, todo))


# --------------------------------------------------------------------------- Greenhouse
def fetch_greenhouse(firm):
    """GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"""
    slug = firm["endpoint"]
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                     params={"content": "true"}, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        jobs.append(_job(
            firm, job_id=j.get("id"), title=j.get("title", ""),
            location=(j.get("location") or {}).get("name", ""),
            posted=_date(j.get("first_published") or j.get("updated_at")),
            url=j.get("absolute_url", ""),
            description=strip_html(j.get("content", "")),
        ))
    return jobs


# --------------------------------------------------------------------------- Lever
def fetch_lever(firm):
    """GET https://api.lever.co/v0/postings/{slug}?mode=json"""
    slug = firm["endpoint"]
    r = requests.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"},
                     headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    jobs = []
    for j in r.json():
        cat = j.get("categories") or {}
        sal = j.get("salaryRange") or {}
        pay = f"${sal.get('min')} - ${sal.get('max')} {sal.get('interval', '')}" if sal.get("min") else ""
        jobs.append(_job(
            firm, job_id=j.get("id"), title=j.get("text", ""),
            location=cat.get("location", ""), country=j.get("country", ""),
            posted=_date(j.get("createdAt")), url=j.get("hostedUrl", ""),
            description=j.get("descriptionPlain", "") + "\n" + strip_html(
                " ".join(l.get("content", "") for l in j.get("lists", []))),
            time_type=cat.get("commitment", ""), pay_text=pay,
        ))
    return jobs


# --------------------------------------------------------------------------- Ashby
def fetch_ashby(firm):
    """GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"""
    slug = firm["endpoint"]
    r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                     params={"includeCompensation": "true"}, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        comp = (j.get("compensation") or {}).get("compensationTierSummary", "")
        addr = ((j.get("address") or {}).get("postalAddress") or {})
        jobs.append(_job(
            firm, job_id=j.get("id"), title=j.get("title", ""),
            location=j.get("location", ""), country=addr.get("addressCountry", ""),
            posted=_date(j.get("publishedAt")), url=j.get("jobUrl", ""),
            description=j.get("descriptionPlain", ""), time_type=j.get("employmentType", ""),
            pay_text=comp,
        ))
    return jobs


# --------------------------------------------------------------------------- SmartRecruiters
def fetch_smartrecruiters(firm):
    """GET https://api.smartrecruiters.com/v1/companies/{slug}/postings"""
    slug = firm["endpoint"]
    base = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    jobs, seen = [], set()
    for query in _searches(firm):
        r = requests.get(base, params={"q": query, "limit": 100, "country": "us"},
                         headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        for j in r.json().get("content", []):
            if j["id"] in seen or QUICK_SKIP.search(j.get("name", "")):
                continue
            seen.add(j["id"])
            loc = j.get("location") or {}
            desc = ""
            try:
                d = requests.get(f"{base}/{j['id']}", headers=HEADERS, timeout=TIMEOUT).json()
                sections = (d.get("jobAd") or {}).get("sections") or {}
                desc = strip_html(" ".join((s or {}).get("text", "") for s in sections.values()))
            except (requests.RequestException, ValueError):
                pass
            jobs.append(_job(
                firm, job_id=j["id"], title=j.get("name", ""),
                location=", ".join(x for x in [loc.get("city"), loc.get("region")] if x),
                country=loc.get("country", ""), posted=_date(j.get("releasedDate")),
                url=f"https://jobs.smartrecruiters.com/{slug}/{j['id']}", description=desc,
                time_type=(j.get("typeOfEmployment") or {}).get("label", ""),
            ))
    return jobs


# --------------------------------------------------------------------------- Oracle Cloud (e.g. JPMorgan)
def fetch_oracle(firm):
    """
    Oracle Recruiting Cloud. endpoint = "https://{host}|{siteNumber}", e.g.
    "https://jpmc.fa.oraclecloud.com|CX_1001"
    """
    host, site = firm["endpoint"].split("|")
    api = f"{host}/hcmRestApi/resources/latest"
    jobs, seen = [], set()
    for query in _searches(firm):
        finder = (f'findReqs;siteNumber={site},limit=100,keyword="{query}",'
                  f'sortBy=POSTING_DATES_DESC')
        r = requests.get(f"{api}/recruitingCEJobRequisitions",
                         params={"onlyData": "true", "expand": "requisitionList.secondaryLocations",
                                 "finder": finder}, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        items = r.json().get("items") or [{}]
        for j in items[0].get("requisitionList", []):
            if j["Id"] in seen or QUICK_SKIP.search(j.get("Title", "")):
                continue
            seen.add(j["Id"])
            desc = j.get("ShortDescriptionStr", "")
            try:
                d = requests.get(f"{api}/recruitingCEJobRequisitionDetails",
                                 params={"expand": "all", "onlyData": "true",
                                         "finder": f'ById;Id="{j["Id"]}",siteNumber={site}'},
                                 headers=HEADERS, timeout=TIMEOUT).json()
                det = (d.get("items") or [{}])[0]
                desc = strip_html(" ".join(str(det.get(k) or "") for k in (
                    "ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr")))
            except (requests.RequestException, ValueError):
                pass
            jobs.append(_job(
                firm, job_id=j["Id"], title=j.get("Title", ""),
                location=j.get("PrimaryLocation", ""), country=j.get("PrimaryLocationCountry", ""),
                posted=_date(j.get("PostedDate")),
                url=f"{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{j['Id']}",
                description=desc, time_type=j.get("WorkerType", "") or "",
            ))
    return jobs


# --------------------------------------------------------------------------- Eightfold (e.g. BNY)
def fetch_eightfold(firm):
    """
    Eightfold career sites. endpoint = "https://{host}|{domain}", e.g.
    "https://bnymellon.eightfold.ai|bnymellon.com"
    """
    host, domain = firm["endpoint"].split("|")
    jobs, seen = [], set()
    for query in _searches(firm):
        r = requests.get(f"{host}/api/apply/v2/jobs",
                         params={"domain": domain, "query": query, "start": 0, "num": 50,
                                 "sort_by": "relevance"}, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        for j in r.json().get("positions", []):
            if j["id"] in seen or QUICK_SKIP.search(j.get("name", "")):
                continue
            seen.add(j["id"])
            desc = j.get("job_description", "")
            if not desc:
                try:
                    d = requests.get(f"{host}/api/apply/v2/jobs/{j['id']}",
                                     params={"domain": domain}, headers=HEADERS, timeout=TIMEOUT)
                    desc = d.json().get("job_description", "")
                except (requests.RequestException, ValueError):
                    pass
            jobs.append(_job(
                firm, job_id=j.get("ats_job_id") or j["id"], title=j.get("name", ""),
                location="; ".join(j.get("locations") or [j.get("location", "")]),
                posted=_date(j.get("t_create")),
                url=j.get("canonicalPositionUrl") or f"{host}/careers/job/{j['id']}",
                description=strip_html(desc), time_type=j.get("type", ""),
            ))
    return jobs


# --------------------------------------------------------------------------- Phenom
def fetch_phenom(firm):
    """
    Phenom People career sites (jobs.example.com). They expose a search API at
    POST {site}/widgets. endpoint = "https://jobs.example.com|en_us"
    """
    site, lang = (firm["endpoint"].split("|") + ["en_us"])[:2]
    jobs, seen = [], set()
    for query in _searches(firm):
        body = {"lang": lang, "deviceType": "desktop", "country": lang.split("_")[-1],
                "pageName": "search-results", "ddoKey": "refineSearch", "sortBy": "Most recent",
                "subsearch": "", "from": 0, "jobs": True, "counts": False, "all_fields": [],
                "size": 50, "clearAll": False, "jdsource": "facets", "isSliderEnable": False,
                "pageId": "page20", "siteType": "external", "keywords": query, "global": True,
                "selected_fields": {}, "locationData": {}}
        r = requests.post(f"{site}/widgets", json=body, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = ((r.json().get("refineSearch") or {}).get("data") or {}).get("jobs", [])
        for j in data:
            jid = j.get("jobId") or j.get("reqId")
            if not jid or jid in seen or QUICK_SKIP.search(j.get("title", "")):
                continue
            seen.add(jid)
            jobs.append(_job(
                firm, job_id=jid, title=j.get("title", ""),
                location=j.get("location") or j.get("cityStateCountry", ""),
                country=j.get("country", ""), posted=_date(j.get("postedDate")),
                url=j.get("applyUrl") or f"{site}/job/{jid}",
                description=strip_html(j.get("descriptionTeaser", "")),
                time_type=j.get("type", ""),
            ))
    return jobs


# --------------------------------------------------------------------------- iCIMS
def fetch_icims(firm):
    """
    iCIMS career sites have no public JSON API, but the search page is plain HTML.
    endpoint = "https://careers-{company}.icims.com"
    """
    host = firm["endpoint"].rstrip("/")
    jobs, seen = [], set()
    for query in _searches(firm):
        r = requests.get(f"{host}/jobs/search", params={"ss": "1", "searchKeyword": query, "in_iframe": "1"},
                         headers={**HEADERS, "Accept": "text/html"}, timeout=TIMEOUT)
        r.raise_for_status()
        for m in re.finditer(r'href="(https?://[^"]+/jobs/(\d+)/[^"]+/job)[^"]*"[^>]*>(.*?)</a>', r.text, re.S):
            url, jid, inner = m.group(1), m.group(2), m.group(3)
            title = strip_html(inner).replace("Title", "").strip()
            if jid in seen or not title or QUICK_SKIP.search(title):
                continue
            seen.add(jid)
            # The location sits in the same row, shortly after the link.
            after = r.text[m.end(): m.end() + 1500]
            loc = re.search(r"(?:Location|iCIMS_JobHeaderData)[^>]*>\s*(?:<[^>]+>\s*)*([^<]{3,80})", after)
            desc, posted = "", ""
            try:
                d = requests.get(url, params={"in_iframe": "1"}, headers={**HEADERS, "Accept": "text/html"},
                                 timeout=TIMEOUT).text
                body = re.search(r'class="iCIMS_JobContent"(.*?)class="iCIMS_JobOptions"', d, re.S)
                desc = strip_html(body.group(1) if body else d)[:8000]
                pm = re.search(r'Posted Date.*?(\d{1,2}/\d{1,2}/\d{4})', d, re.S) or \
                    re.search(r'"datePosted"\s*:\s*"([\d-]+)', d)
                if pm:
                    v = pm.group(1)
                    posted = datetime.strptime(v, "%m/%d/%Y").strftime("%Y-%m-%d") if "/" in v else _date(v)
            except (requests.RequestException, ValueError):
                pass
            jobs.append(_job(firm, job_id=jid, title=title,
                             location=strip_html(loc.group(1)) if loc else "",
                             posted=posted, url=url, description=desc))
    return jobs


# --------------------------------------------------------------------------- SAP SuccessFactors career sites
def fetch_successfactors(firm):
    """
    SuccessFactors 'Recruiting Marketing' career sites (e.g. careers.fitch.group).
    The search page /search/?q=... is HTML with one row per job.
    endpoint = "https://careers.fitch.group"
    """
    site = firm["endpoint"].rstrip("/")
    jobs, seen = [], set()
    for query in _searches(firm):
        r = requests.get(f"{site}/search/", params={"q": query, "sortColumn": "referencedate",
                                                   "sortDirection": "desc"},
                         headers={**HEADERS, "Accept": "text/html"}, timeout=TIMEOUT)
        r.raise_for_status()
        for row in re.findall(r'<tr class="data-row.*?</tr>', r.text, re.S):
            a = re.search(r'href="(/job/[^"]+?/(\d+)/?)"[^>]*>(.*?)</a>', row, re.S)
            if not a:
                continue
            path, jid, title = a.group(1), a.group(2), strip_html(a.group(3))
            if jid in seen or QUICK_SKIP.search(title):
                continue
            seen.add(jid)
            loc = re.search(r'class="jobLocation[^"]*"[^>]*>(.*?)</span>', row, re.S)
            dt = re.search(r'class="jobDate[^"]*"[^>]*>(.*?)</span>', row, re.S)
            posted = ""
            if dt:
                try:
                    posted = datetime.strptime(strip_html(dt.group(1)), "%b %d, %Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass
            desc = ""
            try:
                d = requests.get(site + path, headers={**HEADERS, "Accept": "text/html"}, timeout=TIMEOUT).text
                body = re.search(r'class="jobdescription"(.*?)</span>\s*</div>', d, re.S) or \
                    re.search(r'itemprop="description"(.*?)</div>', d, re.S)
                desc = strip_html(body.group(1) if body else "")[:8000]
            except requests.RequestException:
                pass
            jobs.append(_job(firm, job_id=jid, title=title,
                             location=strip_html(loc.group(1)) if loc else "",
                             posted=posted, url=site + path, description=desc))
    return jobs


def fetch_manual(firm):
    """Firms with no public job API. We can't fetch them automatically, so we
    raise an error that shows up in errors.md with the link to check by hand."""
    raise RuntimeError(f"No public job API found. Check by hand: {firm['endpoint']}")


FETCHERS = {
    "workday": fetch_workday,
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "oracle": fetch_oracle,
    "eightfold": fetch_eightfold,
    "phenom": fetch_phenom,
    "icims": fetch_icims,
    "successfactors": fetch_successfactors,
    "manual": fetch_manual,
}


def fetch(firm, retries=2):
    """Fetch one firm with a couple of retries for flaky networks."""
    fn = FETCHERS.get(firm["ats"])
    if fn is None:
        raise ValueError(f"unknown ats type '{firm['ats']}'")
    for attempt in range(retries + 1):
        try:
            return fn(firm)
        except (requests.ConnectionError, requests.Timeout):
            if attempt == retries:
                raise
            time.sleep(3 * (attempt + 1))
