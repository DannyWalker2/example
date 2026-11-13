"""
rules.py - decides whether a job is a match and gives it a 0-100 score.

Everything is plain keyword rules so you can read and tweak it.
The two main functions:
    check(job)  -> (keep: bool, section: str, reason_if_dropped: str, start: str, exp: str)
    score(job, firm_applied) -> (score: int, one_line_reason: str)
"""
import re
from datetime import date, datetime

# ---------------------------------------------------------------- helpers
def _has(pattern, text):
    return re.search(pattern, text or "", re.I) is not None


US_STATES = ("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV "
             "NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC").split()
US_STATE_NAMES = ("alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|"
                  "georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|"
                  "massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|"
                  "new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|"
                  "oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|"
                  "vermont|virginia|washington|west virginia|wisconsin|wyoming|district of columbia")
US_CITIES = ("new york|nyc|manhattan|jersey city|newark|hoboken|charlotte|chicago|boston|dallas|houston|"
             "atlanta|san francisco|los angeles|san diego|pittsburgh|cleveland|columbus|philadelphia|"
             "st\\.? louis|saint louis|minneapolis|denver|seattle|miami|baltimore|wilmington|stamford|"
             "phoenix|richmond|detroit|cincinnati|milwaukee|nashville|tampa|buffalo|princeton")
NON_US_WORDS = [
    "canada", "toronto", "montreal", "vancouver", "calgary", "ontario", "quebec", "mississauga",
    "london", "united kingdom", "uk", "gb", "england", "scotland", "glasgow", "belfast",
    "ireland", "dublin", "france", "paris", "germany", "frankfurt", "munich", "berlin", "luxembourg",
    "switzerland", "zurich", "geneva", "netherlands", "amsterdam", "spain", "madrid", "italy", "milan",
    "poland", "warsaw", "krakow", "india", "mumbai", "gurugram", "noida", "bangalore", "bengaluru", "pune",
    "hyderabad", "chennai", "gurgaon", "singapore", "hong kong", "japan", "tokyo", "osaka", "china",
    "shanghai", "beijing", "australia", "sydney", "melbourne", "brazil", "sao paulo", "mexico city",
    "argentina", "chile", "colombia", "philippines", "manila", "taguig", "malaysia", "korea", "seoul",
    "uae", "dubai", "saudi", "riyadh", "israel", "south africa", "budapest", "hungary", "prague",
    "portugal", "lisbon", "belgium", "brussels", "bahrain", "monaco",
]
NON_US = r"\b(?:" + "|".join(NON_US_WORDS) + r")\b|(?<!new )\bmexico\b"

NY_NJ = r"new york|\bnyc\b|manhattan|brooklyn|\bny\b|new jersey|\bnj\b|jersey city|newark|hoboken|" \
        r"princeton|iselin|parsippany|morristown|short hills|florham park|whippany|wayne|paramus"
NORTHEAST = r"connecticut|\bct\b|stamford|greenwich|hartford|massachusetts|\bma\b|boston|" \
            r"pennsylvania|\bpa\b|philadelphia|pittsburgh|rhode island|\bri\b|providence|" \
            r"new hampshire|\bnh\b|vermont|\bvt\b|maine|\bme\b|delaware|\bde\b|wilmington|" \
            r"maryland|\bmd\b|baltimore|washington,? d\.?c|\bdc\b|buffalo|albany|rochester|syracuse"
SAN_DIEGO = r"san diego"
ST_LOUIS = r"st\.? louis|saint louis"


def is_us(job):
    """True / False / None (unknown)."""
    country = (job.get("country") or "").lower()
    loc = job.get("location") or ""
    if country:
        if "united states" in country or country in ("us", "usa", "u.s."):
            return True
        return False
    if _has(r"united states|\busa\b|\bu\.s\.|\bus\b", loc) and not _has(NON_US, loc):
        return True
    if _has(NON_US, loc):
        return False
    if any(re.search(rf"(,|\b){s}\b", loc) for s in US_STATES) or _has(US_STATE_NAMES, loc) or _has(US_CITIES, loc):
        return True
    m = re.search(r",\s*([A-Z]{2})\s*$", loc)
    if m and m.group(1) not in US_STATES + ["US"]:
        return False
    return None


# ---------------------------------------------------------------- hard filters
INTERNSHIP = r"shadow (week|day)|insight (week|day|program)|spring week|discovery day|info(rmation)? session|" \
             r"\bevent\b|webinar|talent community|\bintern\b|\binterns\b|internship|summer analyst|summer associate|summer 20\d\d|" \
             r"\bco-?op\b|externship|apprentice|fellowship program for students"
PART_TIME = r"part[- ]time|temporary|\btemp\b|seasonal|contract(or)?\b"
SENIOR_TITLE = r"\b(senior|sr\.?|vice president|\bvp\b|avp|director|managing director|principal|" \
               r"head|lead|leader|manager|mgr|executive director|chief|partner|officer|supervisor|" \
               r"architect|consultant ii|analyst ii|analyst iii|associate ii)\b"
RETAIL = r"premier advisor|private client banker|client associate|financial solutions advisor|" \
         r"advisor development|loan officer|mortgage|home lending|financial center|virtual engagement|" \
         r"wealth management|private bank advisor|banker - |sales representative|financial advisor|financial adviser|financial planner|wealth (management )?(advisor|sales)|" \
         r"personal banker|relationship banker|universal banker|branch|teller|client service associate|" \
         r"private client advisor|retail (sales|brokerage|banking)|registered representative|" \
         r"financial professional|insurance agent|sales agent"
MUNI_ADVISORY = r"municipal advis|financial advisory services|\bmunicipal advisor"
NON_FINANCE = r"software|engineer|developer|cyber|information security|\bit\b|technology(?! (investment |corporate )?banking)|application|programmer|\bpmo\b|support analyst|data & ai|" \
              r"\bpeople\b|talent|audit|compliance|operations|fraud|contact center|client service|" \
              r"document|processor|coordinator|representative|clerk|legal|solutions? architect|product analyst|" \
              r"data scien|machine learning|\bai\b|human resources|\bhr\b|recruit|marketing|" \
              r"graphic|nurse|legal assistant|paralegal|attorney|facilities|administrative assistant|" \
              r"executive assistant|call center|customer service|technician|mechanic|driver"
# For titles without a campus word, the description must clearly say it is for the class of 2027
# (generic "entry level" text is not enough: those roles usually start right away).
DESC_ENTRY_SIGNALS = r"class of 2027|graduat\w*[^.]{0,60}\b(spring|may|june)?\s*2027\b|" \
                     r"(start|begin|join)\w*[^.]{0,30}(summer|june|july|august|september|fall) 2027|" \
                     r"2027 (analyst|associate|graduate|full[- ]time) (program|class)"
ENTRY_SIGNALS = r"\b2027\b|\b2028\b|analyst program|associate program|development program|" \
                r"graduate program|graduate programme|rotational|rotation program|campus|" \
                r"early career|early-career|early talent|new grad|new graduate|recent graduate|" \
                r"recent college|entry[- ]level|full[- ]time analyst|analyst class|class of 2027|" \
                r"university graduate|college graduate|leadership development|leadership program|\bgraduate\b"
MA_ONLY = r"\bm&a\b|mergers|mergers & acquisitions|mergers and acquisitions|sell[- ]side advisory|" \
          r"restructuring advisory"
DEBT_ANGLE = r"debt|credit|leveraged|fixed income|public finance|municipal|financing|capital markets|" \
             r"lending|loan|bond"
MONTHS_BEFORE_JUNE = r"(january|february|march|april|may|jan|feb|mar|apr)\.?"


def years_required(text):
    """Smallest 'N+ years' / 'N years of experience' mentioned. None if not stated."""
    nums = []
    for m in re.finditer(r"(\d{1,2})\s*(?:\+|-\s*\d+|to\s*\d+|or more)?\s*(?:\+\s*)?years?\s*(?:of\s*)?"
                         r"(?:relevant\s*|related\s*|professional\s*|work\s*|full[- ]time\s*|prior\s*)*"
                         r"(?:experience|exp\b)", text or "", re.I):
        n = int(m.group(1))
        if n <= 15:
            nums.append(n)
    return min(nums) if nums else None


def start_info(job):
    """Guess the start timing from the title/description. Returns (label, too_early: bool)."""
    t = job["title"]
    d = job.get("description", "")
    both = t + "\n" + d
    if _has(r"immediate start|start immediately|asap start", both):
        return "Immediate", True
    if _has(rf"(start|starting|begin|beginning|commence)\w*\s+(date\s+)?(in\s+|of\s+|on\s+)?{MONTHS_BEFORE_JUNE}\s*,?\s*2027", both):
        return "Before Jun 2027", True
    if _has(r"winter 2027|january 2027|spring 2027", t):
        return "Before Jun 2027", True
    if _has(r"\b2026\b", t) and not _has(r"\b202[78]\b", t):
        return "2026 class", True
    m = re.search(r"(start|starting|begin|beginning|commence)\w*\s+(date\s+)?(in\s+|of\s+|on\s+)?"
                  r"((june|july|august|september|summer|fall)\s*,?\s*202[78])", both, re.I)
    if m:
        return m.group(4).title(), False
    if _has(r"\b2028\b", t):
        return "2028", False
    if _has(r"\b2027\b", t):
        return "2027 class", False
    if _has(r"(graduat\w+|degree)[^.]{0,60}(spring|may|june)\s*2027|class of 2027", d):
        return "2027 grads", False
    return "Unclear", False


def pay_floor(job):
    """Highest base pay number posted (annualized). None if no pay info.
    We drop jobs whose whole posted range is under $70k."""
    text = (job.get("pay_text", "") + "\n" + job.get("description", ""))
    best = None
    for m in re.finditer(r"\$\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d+)?\s?[kK]|\d{2,3}\.\d{2})"
                         r"(\s*(?:/|per)\s*(?:hour|hr))?", text):
        raw, hourly = m.group(1), m.group(2)
        num = float(re.sub(r"[,kK\s]", "", raw))
        if raw.lower().endswith("k"):
            num *= 1000
        if hourly or num < 200:  # hourly rate
            num *= 2080
        if 20000 <= num <= 1000000:
            best = num if best is None else max(best, num)
    return best


def check(job):
    """Hard MUST / EXCLUDE rules. Returns dict with keep, section, why_dropped, start, exp."""
    t = job["title"]
    d = job.get("description", "")
    both = t + "\n" + d
    out = {"keep": False, "section": "main", "dropped": "", "start": "", "exp": ""}

    def drop(why):
        out["dropped"] = why
        return out

    if _has(INTERNSHIP, t):
        return drop("internship or event")
    if _has(PART_TIME, t + " " + job.get("time_type", "")):
        return drop("part-time/temporary")
    if _has(SENIOR_TITLE, t):
        return drop("senior title")
    if _has(RETAIL, t):
        return drop("retail / wealth sales")
    if _has(MUNI_ADVISORY, t):
        return drop("municipal advisory")
    if _has(NON_FINANCE, t):
        return drop("not a finance seat")
    if is_us(job) is False:
        return drop("outside US")
    if not (_has(ENTRY_SIGNALS, t) or _has(DESC_ENTRY_SIGNALS, d)):
        return drop("not a campus / new-grad role")
    if _has(r"\bmba\b", t) or _has(r"\bmba\b[^.]{0,40}(required|candidates|students)|(current|recent) mba", d):
        return drop("MBA required")
    if _has(r"\bcfa charter(holder)?\b[^.]{0,30}required", both):
        return drop("CFA charter required")

    start, too_early = start_info(job)
    out["start"] = start
    if too_early:
        return drop(f"start too early ({start})")

    yrs = years_required(d)
    out["exp"] = "0-2 yrs" if yrs is None else f"{yrs}+ yrs"
    if yrs is None:
        out["exp"] = "Not stated"
    if yrs is not None and yrs >= 3:
        return drop(f"needs {yrs}+ years")

    pay = pay_floor(job)
    if pay is not None and pay < 70000:
        return drop(f"posted pay under $70k (${pay:,.0f})")

    if _has(MA_ONLY, t) and not _has(DEBT_ANGLE, t):
        out["section"] = "ma"
    out["keep"] = True
    return out


# ---------------------------------------------------------------- scoring
# (points, label, regex on title, regex on description) - first match wins per group.
AREAS = [
    (45, "credit program", r"credit (analyst|development|rotation|program|training|risk analyst|underwriting)|"
                           r"credit & lending|credit and lending|loan underwriting|portfolio management", None),
    (45, "public finance / muni", r"public finance|municipal|\bmuni\b|tax[- ]exempt", r"public finance|municipal bond"),
    (42, "DCM / syndicate", r"debt capital markets|\bdcm\b|syndicate|capital markets financing|"
                           r"investment grade|\big\b|private placement", None),
    (42, "credit ratings", r"rating|ratings", None),
    (40, "fixed income S&T", r"fixed income|rates|credit (sales|trading)|bond", None),
    (38, "lev fin / fund finance / private credit",
         r"leveraged finance|lev fin|fund finance|subscription|nav lending|private credit|"
         r"direct lending|sponsor finance|venture banking|asset[- ]based|structured finance|"
         r"securitization|project finance|infrastructure finance", None),
    (34, "corporate / commercial banking",
         r"corporate banking|commercial bank|commercial analyst|commercial credit|commercial & institutional|"
         r"c&ib|cib|middle market|relationship management|lending|loan", None),
    (32, "fixed income research / investment", r"research|investment analyst|investment associate|"
                                              r"asset management|investment management|portfolio", None),
    (28, "capital markets / markets", r"capital markets|global markets|sales (and|&) trading|markets", None),
    (24, "investment banking", r"investment banking|\bib\b|banking analyst", None),
    (22, "risk / treasury / finance", r"risk|treasury|finance|financial analyst|fp&a|economic|consulting|"
                                      r"brokerage|insurance|analyst", None),
]
DESC_BOOSTS = [
    (6, "mentions muni/public finance", r"municipal|public finance|muni(cipal)? bond"),
    (5, "mentions credit analysis", r"credit analysis|credit risk|underwrit|financial statement analysis"),
    (3, "mentions fixed income", r"fixed income|bond market"),
]
RATING_FIRMS = r"moody|s&p|fitch|kbra|kroll|dbrs|morningstar"


def location_points(loc):
    if _has(NY_NJ, loc):
        return 20, "NY/NJ"
    if _has(SAN_DIEGO, loc):
        return 18, "San Diego"
    if _has(NORTHEAST, loc):
        return 14, "Northeast"
    if _has(ST_LOUIS, loc):
        return 3, "St. Louis"
    if not loc:
        return 6, "location unclear"
    return 9, "US"


def score(job, info, applied_firm=False):
    """Return (score 0-100, short reason)."""
    t, d = job["title"], job.get("description", "")
    reasons = []
    pts = 0

    area_pts, area = 15, "general finance"
    for p, label, title_re, desc_re in AREAS:
        if _has(title_re, t) or (desc_re and _has(desc_re, d[:1500])):
            area_pts, area = p, label
            break
    if area == "credit ratings" and not _has(RATING_FIRMS, job["firm"]):
        area_pts, area = 22, "general finance"
    if _has(RATING_FIRMS, job["firm"]) and _has(r"analyst|associate|program", t) and area_pts < 42:
        area_pts, area = 42, "credit ratings"
    pts += area_pts
    reasons.append(area)

    for p, label, rx in DESC_BOOSTS:
        if _has(rx, d):
            pts += p
            reasons.append(label)
            break

    prog = 0
    if _has(r"\b2027\b", t):
        prog += 8
    if _has(r"program|programme|rotational|class|development|graduate|campus|early career|new grad", t):
        prog += 7
    pts += prog

    loc_pts, loc_label = location_points(job.get("location", ""))
    pts += loc_pts
    reasons.append(loc_label)

    pts += 8 if job.get("tier") == 1 else 4

    if job.get("posted"):
        try:
            age = (date.today() - datetime.strptime(job["posted"], "%Y-%m-%d").date()).days
            pts += 4 if age <= 3 else 2 if age <= 14 else 0
            if age <= 3:
                reasons.append("posted in last 3 days")
        except ValueError:
            pass

    if info.get("start") == "Unclear":
        pts -= 4
    if info.get("section") == "ma":
        pts -= 15
        reasons.append("M&A only")
    if applied_firm:
        pts -= 25
        reasons.append("already applied at this firm")
    return max(0, min(100, pts)), ", ".join(reasons)
