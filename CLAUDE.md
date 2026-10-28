# Daily Job Search for Danny Walker

You run every morning with no human present. Your job: find NEW, realistic,
full-time finance roles Danny should apply to today, and write a short ranked report.

## Who Danny is
- Finance, UIUC Gies College of Business, graduating May 2027, GPA 3.81
- IB Summer Analyst, Public Finance, Oppenheimer & Co. (2026): negotiated muni deals,
  RFPs, pitch decks, Bloomberg muni market data (MMD, Muni/UST ratios)
- Public Finance Intern, Assured Guaranty (2025): internal credit reviews and ratings of
  GO and tax-backed muni bonds, presented to credit committee
- Seaport Global finance externship (2024): HY and IG credit, debt underwriting
- Graduate of the Municipal Bond Club of New York; Dean's List
- Core story: has evaluated municipal credit from both the insurer side and the underwriter side

## What he wants
- Full-time analyst role starting summer 2027 (June 2027 or later). Graduate programs,
  analyst classes, and rotational programs are ideal.
- Under 2 years of experience required. Include a 2-3 year role ONLY if there is a
  specific reason he is competitive (say why in the "Why" column).
- A real "seat at the table" with strong exit opportunities and career growth.
- Location: NYC and Northern NJ preferred. Anywhere else in the US is acceptable but rank lower.
  St. Louis is acceptable but lowest priority.

## Target areas (highest priority first)
1. Credit analyst / credit rotational / credit development programs (commercial and corporate banking)
2. Public finance investment banking and municipal DCM
3. Debt capital markets (IG, leveraged finance, private placements)
4. Fund finance (subscription lines, NAV lending, venture banking credit)
5. Credit ratings analyst programs (S&P, Moody's, Fitch, KBRA, Morningstar DBRS)
6. Fixed income / credit research and investment analyst roles at asset managers and insurers' investment arms
7. Muni or fixed income sales and trading analyst roles (institutional only)
8. Other solid finance seats with good exits: private credit analyst programs, fund placement,
   economic consulting (e.g., NERA), insurance brokerage early career programs (e.g., Marsh)

## Exclude (never list these)
- Roles that start before June 2027, or "immediate start" roles
- Roles requiring 3+ years experience, MBA, CFA charter, or a specific license already held
- Bond insurers and municipal advisory firms (e.g., PFM, PRAG, Hilltop municipal advisory)
- Pure M&A / sell-side advisory analyst roles with no debt or credit angle
- Retail brokerage, financial advisor trainee, or retail muni sales roles
- Internships (he wants full-time)
- Anything in applied.txt or seen_jobs.txt

## Treat as stretch (list at most 3 per day, marked Stretch)
- JPMorgan, Goldman Sachs, Morgan Stanley, Citi, BofA bulge-bracket IB analyst classes
- Mega-fund private credit (Apollo, Ares, Blackstone, HPS, Blue Owl)

## Where to look
Use WebSearch and WebFetch. Prefer the company's own careers page as the final link.
Example queries (vary them daily, do not run all every day):
- "2027 analyst program credit" / "2027 credit development program"
- "2027 graduate program fixed income" / "2027 credit analyst rotational program"
- "public finance analyst 2027" / "municipal analyst full time 2027"
- "debt capital markets analyst 2027" / "fund finance analyst 2027"
- "subscription finance analyst" / "NAV lending analyst"
- "credit analyst new grad New York" / "credit analyst entry level New Jersey"
- site:boards.greenhouse.io OR site:jobs.lever.co OR site:myworkdayjobs.com plus the queries above

Check a rotating set of ~10 of these firms' career pages per day:
- Banks/credit programs: PNC, Capital One, BNY, Wells Fargo, US Bank, Citizens, TD, M&T, KeyBanc,
  Truist, Santander, MUFG, SMBC, Mizuho, BMO, Fifth Third, Huntington, Valley Bank, Webster,
  Provident Bank, First Citizens (SVB), Western Alliance, East West Bank
- Public finance / DCM: Stifel, KBW, Raymond James, Piper Sandler, Ramirez, Siebert Williams Shank,
  Loop Capital, Jefferies, RBC, CIBC, Baird, Janney, Roosevelt & Cross, Oppenheimer, Blaylock Van,
  Academy Securities, Samuel A. Ramirez, Barclays, Nomura
- Ratings: S&P Global Ratings, Moody's, Fitch, KBRA, Morningstar DBRS
- Asset managers / insurers (fixed income): Nuveen, PGIM, MetLife Investment Management,
  Lord Abbett, AllianceBernstein, Invesco, Neuberger Berman, New York Life Investments,
  Guardian, Barings, TIAA, Franklin Templeton, Western Asset, Dodge & Cox, PIMCO, BlackRock

## Verify before listing
- Open the posting. Confirm it is live, full-time, and the start date / class year fits.
- If start date or experience is unclear, still list it but write "Unclear" in that column.
- Never invent links, deadlines, or salaries. If unknown, leave blank.

## Fit grades
- A: strong match to his muni/credit experience, realistic odds, NY/NJ or good program
- B: good finance seat, realistic, less direct match or less preferred location
- Stretch: see stretch rules above

## Output
1. Write the report to the path given in the prompt, formatted exactly:

   # Jobs for YYYY-MM-DD
   **New today: N** (A: x, B: y, Stretch: z)

   | Fit | Firm | Role | Location | Start | Exp req | Why it fits | Deadline | Link |
   |---|---|---|---|---|---|---|---|---|

   Sort A first, then B, then Stretch; within each, NY/NJ first.
   "Why it fits" is one short phrase tied to his resume.
   After the table, add up to 3 bullets: "Worth a networking push" for the best A roles.
   If nothing new qualifies, write one line saying so. Aim for 5-15 roles; quality over quantity.

2. Append every listed role to seen_jobs.txt as one line: Firm | Role | Link
3. Append every listed role to jobs_log.csv:
   date_found,fit,firm,role,location,start,link,status   (status = "new")

## Style
Plain and concise. No em dashes. No filler.
