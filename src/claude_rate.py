"""
claude_rate.py - OPTIONAL. If the ANTHROPIC_API_KEY secret is set, ask Claude to
rate each NEW job 1-10 against Danny's profile and write a one-sentence "why apply".
If the key is missing (or anything goes wrong), the tool keeps working without it.
"""
import json
import os

MODEL = "claude-opus-5-5"
MAX_JOBS_PER_RUN = 40  # keeps cost small; ratings are saved in seen.json and reused

PROFILE = """Danny Walker: Finance major, UIUC Gies College of Business, graduating May 2027, GPA 3.8.
- Public Finance IB Summer Analyst, Oppenheimer (2026): muni underwriting support, RFPs, Sales Point Memos,
  Bloomberg market data (MMD, Muni/UST ratios).
- Public Finance intern, Assured Guaranty (2025): municipal credit analysis, internal credit ratings,
  presented to credit committees.
- Seaport Global finance externship (HY/IG credit, private placements). Municipal Bond Club of New York graduate.
- Skills: Bloomberg, Excel (intermediate), some Python. Little accounting.
Wants: full-time new-grad analyst/rotational program starting June 2027 or later, 0-2 yrs experience, US.
Top interests: credit analyst programs, public finance IB / muni DCM, DCM, fixed income S&T, ratings agencies,
lev fin / fund finance / private credit. NY/NJ best, San Diego great, Northeast good, St. Louis lowest."""

SCHEMA = {
    "type": "object",
    "properties": {"rating": {"type": "integer"}, "why_apply": {"type": "string"}},
    "required": ["rating", "why_apply"],
    "additionalProperties": False,
}


def enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _rate_one(client, job):
    prompt = (f"Candidate profile:\n{PROFILE}\n\nJob posting:\nFirm: {job['firm']}\nTitle: {job['title']}\n"
              f"Location: {job['location']}\nDescription:\n{job['description'][:6000]}\n\n"
              "Rate how well this job fits the candidate from 1 (poor) to 10 (excellent), considering "
              "his muni/credit experience, realistic odds, start date and location. Then write ONE short "
              "sentence (under 30 words, no em dashes) on why he should apply, tied to his resume.")
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=2000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if the model declines, the API retries on a fallback model
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "refusal":
        return None
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(text)
    return max(1, min(10, int(data["rating"]))), data["why_apply"].strip()


def rate(jobs, seen):
    try:
        import anthropic
    except ImportError:
        print("anthropic package not installed; skipping Claude ratings")
        return
    client = anthropic.Anthropic()
    todo = sorted(jobs, key=lambda j: -j["score"])[:MAX_JOBS_PER_RUN]
    for job in todo:
        saved = seen.get(job["key"], {})
        if saved.get("claude_score"):
            job["claude_score"], job["claude_note"] = saved["claude_score"], saved.get("claude_note", "")
            continue
        try:
            result = _rate_one(client, job)
        except anthropic.APIStatusError as e:
            print(f"Claude rating skipped for {job['firm']} ({e.status_code})")
            if e.status_code in (401, 403):
                return  # bad key: stop trying
            continue
        except (anthropic.APIConnectionError, ValueError, KeyError) as e:
            print(f"Claude rating skipped for {job['firm']}: {type(e).__name__}")
            continue
        if result:
            job["claude_score"], job["claude_note"] = result
