# Danny's job finder

Every 6 hours GitHub runs this tool for you. It:

1. Pulls live postings straight from each firm's own job system (Workday, Greenhouse,
   Oracle, iCIMS and others). It never touches LinkedIn, Indeed or Glassdoor.
2. Keeps only full-time new-grad / Class of 2027 roles in the US that start June 2027 or later,
   need 0-2 years of experience, and are not internships, retail/wealth sales, muni advisory,
   or roles with posted base pay under $70k.
3. Scores each one 0-100 (credit programs, public finance, DCM, ratings, fixed income and lev fin
   score highest; NY/NJ is the best location, St. Louis the lowest) with a one-line reason.
4. Skips anything in `applied.txt` and anything it has already shown you (`seen.json`).
5. Updates **[jobs.md](jobs.md)**, the full ranked list with the newest and best first.
6. Opens a GitHub Issue called **"New jobs YYYY-MM-DD"** that lists only the NEW matches.
   GitHub emails you about it.
7. Lists any firm it could not reach in **[errors.md](errors.md)**, so nothing fails silently.

Every job in jobs.md comes from a real job-system response and includes the apply link,
posting date, location and job ID. Nothing is guessed.

---

## One-time setup (about 5 minutes)

**1. Merge the pull request.** On GitHub, open the "Pull requests" tab, open the job finder PR,
click **Merge pull request**, then **Confirm merge**. The 6-hour schedule only starts once
the code is on the repo's default branch.

**2. Allow the workflow to write.** Go to **Settings → Actions → General**. Scroll to
"Workflow permissions", choose **Read and write permissions**, and click **Save**.
(The workflow already asks for these permissions, so this is only needed if your
account blocks them.)

**3. Make sure you get the emails.** Click your profile picture → **Settings → Notifications**.
Under "Subscriptions → Watching" (or "Participating"), make sure **Email** is ticked.
Each issue also @mentions you, which always triggers an email.

**4. (Optional) Add Claude ratings.** Every new job can also get a 1-10 fit rating from Claude
and a one-sentence "why apply" note. To turn this on:
- Get an API key at console.anthropic.com → API Keys.
- In this repo, go to **Settings → Secrets and variables → Actions → New repository secret**.
- Name: `ANTHROPIC_API_KEY`. Value: paste the key. Click **Add secret**.

Without the key everything still works; you just don't get the Claude columns. With it, the cost is a
few cents per run (it only rates new jobs, at most 40 per run).

---

## How to run it now (manually)

1. Open the repo on GitHub and click the **Actions** tab.
2. In the left list, click **Find jobs**.
3. Click the **Run workflow** button (right side), then the green **Run workflow**.
4. Wait about 5-10 minutes. Refresh. When the run has a green check, open `jobs.md`.

## How to mark something as applied

Edit `applied.txt` on GitHub: open the file, click the pencil icon, add a line, and click
**Commit changes**. There are three kinds of line:

| You write | What happens |
|---|---|
| `R-123456` | Hides that exact job. Copy the ID from the "Job ID" column in jobs.md. |
| `Wells Fargo \| 2027 Corporate Banking Analyst Program` | Hides roles at that firm whose title matches. |
| `US Bank` | Every role at that firm moves to a lower section, "At firms you already applied to". It is still shown. |

Jobs you have already seen will not be emailed again either way; `applied.txt` mainly
cleans up `jobs.md`.

## How to add a firm

Open `firms.yaml` and copy an existing entry. You need the firm's job-system address:

1. Open one of the firm's job postings in your browser and look at the address bar.
2. Match it to the table below and fill in `ats` and `endpoint`.

| If the posting address looks like | ats | endpoint to write |
|---|---|---|
| `https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers/job/...` | `workday` | `https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/AcmeCareers` |
| `https://job-boards.greenhouse.io/acme/jobs/123` | `greenhouse` | `acme` |
| `https://jobs.lever.co/acme/...` | `lever` | `acme` |
| `https://jobs.ashbyhq.com/acme/...` | `ashby` | `acme` |
| `https://jobs.smartrecruiters.com/Acme/...` | `smartrecruiters` | `Acme` |
| `https://xyz.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/...` | `oracle` | `https://xyz.fa.us2.oraclecloud.com\|CX_1` |
| `https://careers-acme.icims.com/jobs/123/...` | `icims` | `https://careers-acme.icims.com` |
| `https://acme.eightfold.ai/careers/job/...` | `eightfold` | `https://acme.eightfold.ai\|acme.com` |
| `https://careers.acme.com/job/City-Title/123456/` (SuccessFactors) | `successfactors` | `https://careers.acme.com` |

Example:

```yaml
  - name: Acme Bank
    tier: 2
    ats: workday
    endpoint: https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/AcmeCareers
```

Not sure which system a firm uses? Run the helper (it needs normal internet):

```bash
python tools/discover.py "Acme Bank" https://www.acme.com/careers acme
```

After you add a firm, click **Run workflow** (above) and check `errors.md`. If the firm
is listed there, the address is wrong.

## How to change the schedule

Open `.github/workflows/find-jobs.yml` and edit this line:

```yaml
    - cron: "17 */6 * * *"   # every 6 hours
```

The five fields are minute, hour, day of month, month, and day of week, in UTC (New York time
is UTC minus 5 hours in winter and minus 4 in summer). Examples:

- `17 */6 * * *` means every 6 hours (current)
- `17 */12 * * *` means every 12 hours
- `30 11 * * *` means once a day at 11:30 UTC (6:30am New York in winter)
- `30 11 * * 1-5` means weekdays only

To pause it completely: **Actions → Find jobs → "..." menu → Disable workflow**.

## How to tune what counts as a match

All rules are in `src/rules.py`, in plain keyword lists:
- `AREAS` holds the points for each type of role (credit, public finance, DCM...).
- `location_points` holds the points for each location.
- `INTERNSHIP`, `RETAIL`, `MUNI_ADVISORY`, `NON_FINANCE` and `SENIOR_TITLE` are words that drop a job.
- `MIN_SCORE` in `src/main.py` (currently 30) hides anything that scores lower.

## What each file is

| File | What it is |
|---|---|
| `jobs.md` | The ranked list of every current match. **NEW** marks jobs found this run. |
| `errors.md` | Firms that could not be checked this run, and why. "manual" firms have no public job API, so it gives you a link to check by hand. |
| `applied.txt` | Your applied/closed list (you edit this). |
| `firms.yaml` | Which firms to check and where (you can edit this). |
| `seen.json` | Memory of every job already shown to you. Delete its contents (leave `{}`) to start fresh. |
| `src/` | The code: `fetchers.py` (one function per job system), `rules.py` (filters and scores), `main.py` (runs everything), `claude_rate.py` (optional Claude rating). |
| `tools/discover.py` | Helper for finding a new firm's job system. |

## Running it on your own computer (optional)

```bash
pip install -r requirements.txt
```

```bash
python src/main.py
```

Add `--test` to only check that every firm answers (it writes `errors.md`).
