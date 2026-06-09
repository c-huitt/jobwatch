#!/usr/bin/env python3
"""
jobwatch.py — Watch company career pages for matching design roles.

How it works:
  Most companies post jobs through an Applicant Tracking System (ATS):
  Greenhouse, Lever, or Ashby. Each has a public JSON endpoint. This script
  queries those endpoints for the companies you list, filters by title and
  location keywords, remembers what it has already seen (seen.json), and
  reports only NEW matches each run.

Run it:
  python3 jobwatch.py

No external libraries required (uses only the Python standard library).
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import date

# ----------------------------------------------------------------------------
# CONFIG — edit this section
# ----------------------------------------------------------------------------

# Titles to match (case-insensitive substring match). Add/remove freely.
TITLE_KEYWORDS = [
    "product designer",
    "ux designer",
    "ui designer",
    "ux/ui",
    "ui/ux",
    "experience designer",
    "interaction designer",
    "associate designer",
    "product design",
]

# Locations to keep. A job is kept if its location text contains any of these,
# OR the job is flagged remote. Set REQUIRE_LOCATION_MATCH = False to keep all.
LOCATION_KEYWORDS = [
    "boston", "cambridge", "somerville", "watertown", "waltham", "newton",
    "massachusetts", "ma", "remote", "united states", "us", "anywhere",
]
REQUIRE_LOCATION_MATCH = True

# Titles to exclude even if they match above (avoids senior-only noise and
# the AI-annotation roles you want to skip).
TITLE_EXCLUDE = [
    "staff", "principal", "lead", "manager", "director",
    "head of", "vp", "annotation", "data labeling", "labeler", "rater",
]
# Note: "senior" / "sr." are intentionally NOT excluded, so Senior roles show.
# Add them back here if Senior postings become noise.

# Companies to watch.
#   ats:   "greenhouse" | "lever" | "ashby"
#   token: the company's board identifier
# Tokens marked "# verified" were confirmed live. The rest are best guesses
# (usually the company slug). On the first run, the script prints a Warning
# for any token that fails. Just fix or delete those lines. Companies that use
# Workday have NO public API and are listed in README_WORKDAY.txt instead;
# set manual job alerts on those sites.
COMPANIES = [
    # --- Boston metro: tech / SaaS / consumer ---
    {"name": "Klaviyo",          "ats": "greenhouse", "token": "klaviyo"},
    {"name": "HubSpot",          "ats": "greenhouse", "token": "hubspotjobs"},
    {"name": "Toast",            "ats": "greenhouse", "token": "toast"},
    {"name": "CarGurus",         "ats": "greenhouse", "token": "cargurus"},
    {"name": "ezCater",          "ats": "greenhouse", "token": "ezcaterinc"},
    {"name": "Acquia",           "ats": "greenhouse", "token": "acquia"},
    {"name": "SmartBear",        "ats": "greenhouse", "token": "smartbear"},
    {"name": "Hometap",          "ats": "greenhouse", "token": "hometap"},
    {"name": "Nasuni",           "ats": "greenhouse", "token": "nasuni"},
    {"name": "Starburst",        "ats": "greenhouse", "token": "starburst"},
    {"name": "Whoop",            "ats": "ashby",      "token": "whoop"},
    {"name": "SimpliSafe",       "ats": "greenhouse", "token": "simplisafe"},
    {"name": "Wistia",           "ats": "ashby",      "token": "wistia"},
    {"name": "LogRocket",        "ats": "lever",      "token": "logrocket"},
    {"name": "Jellyfish",        "ats": "ashby",      "token": "jellyfish"},
    {"name": "Hi Marley",        "ats": "greenhouse", "token": "himarley"},
    {"name": "Salsify",          "ats": "greenhouse", "token": "salsify"},
    {"name": "Tulip",            "ats": "greenhouse", "token": "tulip"},
    {"name": "ZoomInfo",         "ats": "greenhouse", "token": "zoominfo"},
    {"name": "Cybereason",       "ats": "greenhouse", "token": "cybereason"},
    {"name": "Onapsis",          "ats": "greenhouse", "token": "onapsis"},
    {"name": "Recorded Future",  "ats": "greenhouse", "token": "recordedfuture"},
    {"name": "Proof (Notarize)", "ats": "greenhouse", "token": "proof"},
    {"name": "Salesloft",        "ats": "greenhouse", "token": "salesloft"},
    {"name": "Pixability",       "ats": "greenhouse", "token": "pixability"},
    {"name": "Markforged",       "ats": "greenhouse", "token": "markforged"},
    {"name": "Formlabs",         "ats": "greenhouse", "token": "formlabs"},
    {"name": "Butterfly Network","ats": "greenhouse", "token": "butterflynetwork"},

    # --- Boston metro: biotech / health / climate ---
    {"name": "Ginkgo Bioworks",  "ats": "greenhouse", "token": "ginkgobioworks"},
    {"name": "Indigo Ag",        "ats": "greenhouse", "token": "indigo"},
    {"name": "Cohere Health",    "ats": "greenhouse", "token": "coherehealth"},
    {"name": "Form Energy",      "ats": "ashby",      "token": "formenergy"},
    {"name": "PathAI",           "ats": "greenhouse", "token": "pathai"},
    {"name": "Benchling",        "ats": "ashby",      "token": "benchling"},
    {"name": "Asimov",           "ats": "ashby",      "token": "asimov"},
    {"name": "Generate Biomedicines","ats": "greenhouse","token": "generatebiomedicines"},
    {"name": "Flatiron Health",  "ats": "greenhouse", "token": "flatironhealth"},
    {"name": "Komodo Health",    "ats": "greenhouse", "token": "komodohealth"},

    # --- Health / wellness (remote-friendly) ---
    {"name": "Oscar Health",     "ats": "greenhouse", "token": "oscar"},
    {"name": "Ro",               "ats": "lever",      "token": "ro"},
    {"name": "Cedar",            "ats": "ashby",      "token": "cedar"},
    {"name": "Maven Clinic",     "ats": "greenhouse", "token": "mavenclinic"},
    {"name": "Headway",          "ats": "ashby",      "token": "headway"},
    {"name": "Included Health",  "ats": "lever",      "token": "includedhealth"},
    {"name": "Garner Health",    "ats": "greenhouse", "token": "garnerhealth"},
    {"name": "Eight Sleep",      "ats": "ashby",      "token": "eightsleep"},
    {"name": "Strava",           "ats": "ashby",      "token": "strava"},
    {"name": "Calm",             "ats": "greenhouse", "token": "calm"},
    {"name": "Peloton",          "ats": "greenhouse", "token": "peloton"},

    # --- Agencies / design studios (often hire earlier-career) ---
    {"name": "IDEO",             "ats": "greenhouse", "token": "ideo"},

    # --- Fintech / finance ---
    {"name": "Stripe",           "ats": "greenhouse", "token": "stripe"},
    {"name": "Affirm",           "ats": "greenhouse", "token": "affirm"},
    {"name": "Robinhood",        "ats": "greenhouse", "token": "robinhood"},
    {"name": "Coinbase",         "ats": "greenhouse", "token": "coinbase"},
    {"name": "Brex",             "ats": "greenhouse", "token": "brex"},
    {"name": "Ramp",             "ats": "ashby",      "token": "ramp"},
    {"name": "Plaid",            "ats": "ashby",      "token": "plaid"},
    {"name": "Mercury",          "ats": "greenhouse", "token": "mercury"},
    {"name": "Marqeta",          "ats": "greenhouse", "token": "marqeta"},
    {"name": "Chime",            "ats": "greenhouse", "token": "chime"},
    {"name": "Wealthfront",      "ats": "lever",      "token": "wealthfront"},
    {"name": "Betterment",       "ats": "greenhouse", "token": "betterment"},
    {"name": "Carta",            "ats": "greenhouse", "token": "carta"},
    {"name": "Gusto",            "ats": "greenhouse", "token": "gusto"},
    {"name": "Bill",             "ats": "greenhouse", "token": "billcom"},
    {"name": "Modern Treasury",  "ats": "ashby",      "token": "moderntreasury"},
    {"name": "Unit",             "ats": "ashby",      "token": "unit"},
    {"name": "Lithic",           "ats": "greenhouse", "token": "lithic"},
    {"name": "Wealthsimple",     "ats": "ashby",      "token": "wealthsimple"},
    {"name": "Gemini",           "ats": "greenhouse", "token": "gemini"},
    {"name": "Dashlane",         "ats": "greenhouse", "token": "dashlane"},
    {"name": "1Password",        "ats": "ashby",      "token": "1password"},
    {"name": "FanDuel",          "ats": "greenhouse", "token": "fanduel"},

    # --- Remote-first design / dev tools / SaaS ---
    {"name": "GitLab",           "ats": "greenhouse", "token": "gitlab"},
    {"name": "Cloudflare",       "ats": "greenhouse", "token": "cloudflare"},
    {"name": "Figma",            "ats": "greenhouse", "token": "figma"},
    {"name": "Dropbox",          "ats": "greenhouse", "token": "dropbox"},
    {"name": "Reddit",           "ats": "greenhouse", "token": "reddit"},
    {"name": "Notion",           "ats": "ashby",      "token": "notion"},
    {"name": "Linear",           "ats": "ashby",      "token": "linear"},
    {"name": "Vercel",           "ats": "greenhouse", "token": "vercel"},
    {"name": "Webflow",          "ats": "greenhouse", "token": "webflow"},
    {"name": "Mozilla",          "ats": "greenhouse", "token": "mozilla"},
    {"name": "Datadog",          "ats": "greenhouse", "token": "datadog"},
    {"name": "MongoDB",          "ats": "greenhouse", "token": "mongodb"},
    {"name": "Okta",             "ats": "greenhouse", "token": "okta"},
    {"name": "Amplitude",        "ats": "greenhouse", "token": "amplitude"},
    {"name": "Asana",            "ats": "greenhouse", "token": "asana"},
    {"name": "Instacart",        "ats": "greenhouse", "token": "instacart"},
    {"name": "DoorDash",         "ats": "greenhouse", "token": "doordashusa"},
    {"name": "Airtable",         "ats": "greenhouse", "token": "airtable"},
    {"name": "Postman",          "ats": "greenhouse", "token": "postman"},
    {"name": "Calendly",         "ats": "greenhouse", "token": "calendly"},
    {"name": "Grafana Labs",     "ats": "greenhouse", "token": "grafanalabs"},
    {"name": "Squarespace",      "ats": "greenhouse", "token": "squarespace"},
    {"name": "Pinterest",        "ats": "greenhouse", "token": "pinterest"},
    {"name": "Lyft",             "ats": "greenhouse", "token": "lyft"},
    {"name": "Twilio",           "ats": "greenhouse", "token": "twilio"},
    {"name": "Discord",          "ats": "greenhouse", "token": "discord"},
    {"name": "Patreon",          "ats": "ashby",      "token": "patreon"},
    {"name": "Articulate",       "ats": "lever",      "token": "articulate"},
    {"name": "Zapier",           "ats": "ashby",      "token": "zapier"},
    {"name": "Pendo",            "ats": "greenhouse", "token": "pendo"},
    {"name": "Fivetran",         "ats": "greenhouse", "token": "fivetran"},
    {"name": "Mixpanel",         "ats": "greenhouse", "token": "mixpanel"},
    {"name": "Iterable",         "ats": "greenhouse", "token": "iterable"},
    {"name": "Braze",            "ats": "greenhouse", "token": "braze"},
    {"name": "Smartsheet",       "ats": "greenhouse", "token": "smartsheet"},
    {"name": "CircleCI",         "ats": "greenhouse", "token": "circleci"},
    {"name": "OneTrust",         "ats": "greenhouse", "token": "onetrust"},
    {"name": "Vanta",            "ats": "ashby",      "token": "vanta"},
    {"name": "Drata",            "ats": "ashby",      "token": "drata"},
    {"name": "Watershed",        "ats": "ashby",      "token": "watershed"},
    {"name": "Checkr",           "ats": "greenhouse", "token": "checkr"},
    {"name": "Lattice",          "ats": "greenhouse", "token": "lattice"},
    {"name": "Culture Amp",      "ats": "greenhouse", "token": "cultureamp"},
    {"name": "Deel",             "ats": "ashby",      "token": "deel"},
    {"name": "Remote",           "ats": "greenhouse", "token": "remote"},
    {"name": "Verkada",          "ats": "greenhouse", "token": "verkada"},
    {"name": "Samsara",          "ats": "greenhouse", "token": "samsara"},
    {"name": "Nuro",             "ats": "greenhouse", "token": "nuro"},
    {"name": "Flexport",         "ats": "greenhouse", "token": "flexport"},
    {"name": "Intercom",         "ats": "greenhouse", "token": "intercom"},
    {"name": "Algolia",          "ats": "greenhouse", "token": "algolia"},
    {"name": "Contentful",       "ats": "greenhouse", "token": "contentful"},
    {"name": "Netlify",          "ats": "greenhouse", "token": "netlify"},
    {"name": "Cockroach Labs",   "ats": "greenhouse", "token": "cockroachlabs"},
    {"name": "Confluent",        "ats": "ashby",      "token": "confluent"},
    {"name": "Databricks",       "ats": "greenhouse", "token": "databricks"},
    {"name": "Snowflake",        "ats": "ashby",      "token": "snowflake"},
    {"name": "Elastic",          "ats": "greenhouse", "token": "elastic"},
    {"name": "New Relic",        "ats": "greenhouse", "token": "newrelic"},
    {"name": "PagerDuty",        "ats": "greenhouse", "token": "pagerduty"},
    {"name": "Sentry",           "ats": "ashby",      "token": "sentry"},
    {"name": "Sendbird",         "ats": "greenhouse", "token": "sendbird"},
    {"name": "Storyblok",        "ats": "greenhouse", "token": "storyblok"},
    {"name": "Sanity",           "ats": "ashby",      "token": "sanity"},
    {"name": "Supabase",         "ats": "ashby",      "token": "supabase"},
    {"name": "PlanetScale",      "ats": "greenhouse", "token": "planetscale"},
    {"name": "Typeform",         "ats": "greenhouse", "token": "typeform"},
    {"name": "Gopuff",           "ats": "lever",      "token": "gopuff"},
    {"name": "Faire",            "ats": "greenhouse", "token": "faire"},
    {"name": "SeatGeek",         "ats": "greenhouse", "token": "seatgeek"},
    {"name": "Substack",         "ats": "ashby",      "token": "substack"},
    {"name": "Vox Media",        "ats": "greenhouse", "token": "voxmedia"},
    {"name": "The Athletic",     "ats": "lever",      "token": "theathletic"},
    {"name": "Away",             "ats": "ashby",      "token": "away"},
    {"name": "Poshmark",         "ats": "ashby",      "token": "poshmark"},
    {"name": "Glossier",         "ats": "greenhouse", "token": "glossier"},
    {"name": "Cresta",           "ats": "greenhouse", "token": "cresta"},

    # --- AI labs ---
    {"name": "Anthropic",        "ats": "greenhouse", "token": "anthropic"},
    {"name": "OpenAI",           "ats": "ashby",      "token": "openai"},
    {"name": "Scale AI",         "ats": "greenhouse", "token": "scaleai"},
    {"name": "Perplexity",       "ats": "ashby",      "token": "perplexity"},
    {"name": "Replit",           "ats": "ashby",      "token": "replit"},
    {"name": "Harvey",           "ats": "ashby",      "token": "harvey"},
    {"name": "Writer",           "ats": "ashby",      "token": "writer"},
    {"name": "Abridge",          "ats": "ashby",      "token": "abridge"},
    {"name": "ElevenLabs",       "ats": "ashby",      "token": "elevenlabs"},
    {"name": "Cohere",           "ats": "ashby",      "token": "cohere"},
    {"name": "Sierra",           "ats": "ashby",      "token": "sierra"},

    # --- Education / nonprofit / civic ---
    {"name": "Khan Academy",     "ats": "greenhouse", "token": "khanacademy"},
    {"name": "Duolingo",         "ats": "greenhouse", "token": "duolingo"},
    {"name": "Coursera",         "ats": "greenhouse", "token": "coursera"},
    {"name": "Wikimedia",        "ats": "greenhouse", "token": "wikimedia"},
    {"name": "Code for America", "ats": "greenhouse", "token": "codeforamerica"},
    {"name": "DonorsChoose",     "ats": "greenhouse", "token": "donorschoose"},
    {"name": "Brave",            "ats": "greenhouse", "token": "brave"},

    # --- Boston area: consulting / finance / VC ---
    {"name": "Thoughtworks",     "ats": "greenhouse", "token": "thoughtworks"},
    {"name": "Charles River Associates", "ats": "greenhouse", "token": "charlesriverassociates"},
    {"name": "Oliver Wyman",     "ats": "lever",      "token": "oliverwyman"},
    {"name": "GMO",              "ats": "lever",      "token": "gmo"},
    {"name": "Vestmark",         "ats": "greenhouse", "token": "vestmark"},
    {"name": "General Catalyst", "ats": "greenhouse", "token": "generalcatalyst"},

    # --- Boston area: tech / software ---
    {"name": "TripAdvisor",      "ats": "greenhouse", "token": "tripadvisor"},
    {"name": "EverQuote",        "ats": "greenhouse", "token": "everquote"},
    {"name": "Veracode",         "ats": "greenhouse", "token": "veracode"},
    {"name": "Definitive Healthcare", "ats": "greenhouse", "token": "definitivehc"},
    {"name": "Nylas",            "ats": "ashby",      "token": "nylas"},
    {"name": "Kaseya",           "ats": "greenhouse", "token": "kaseya"},
    {"name": "Immuta",           "ats": "lever",      "token": "immuta"},
    {"name": "Veeva",            "ats": "lever",      "token": "veeva"},
    {"name": "Hopper",           "ats": "ashby",      "token": "hopper"},
    {"name": "Tamr",             "ats": "ashby",      "token": "tamr"},
    {"name": "Locus Robotics",   "ats": "greenhouse", "token": "locusrobotics"},
    {"name": "Instrument",       "ats": "lever",      "token": "instrument"},

    # --- Boston area: biotech ---
    {"name": "Beam Therapeutics","ats": "greenhouse", "token": "beamtherapeutics"},
    {"name": "Kymera Therapeutics", "ats": "greenhouse", "token": "kymeratherapeutics"},
    {"name": "Scholar Rock",     "ats": "lever",      "token": "scholarrock"},
    {"name": "Dyne Therapeutics","ats": "greenhouse", "token": "dynetherapeutics"},
    {"name": "Tessera Therapeutics", "ats": "greenhouse", "token": "tesseratherapeutics"},

    # --- Boston area: health / insurtech ---
    {"name": "Amwell",           "ats": "greenhouse", "token": "amwell"},
    {"name": "Biofourmis",       "ats": "greenhouse", "token": "biofourmis"},
    {"name": "Openly",           "ats": "greenhouse", "token": "openly"},
]

SEEN_FILE = "seen.json"
USER_AGENT = "jobwatch/1.0 (personal job search)"
REQUEST_TIMEOUT = 20  # seconds

# ----------------------------------------------------------------------------
# Fetchers — one per ATS, each returns a list of normalized job dicts
# ----------------------------------------------------------------------------

def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_greenhouse(company):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company['token']}/jobs"
    data = _get_json(url)
    jobs = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "") or ""
        jobs.append({
            "company": company["name"],
            "id": f"gh-{company['token']}-{j.get('id')}",
            "title": j.get("title", "") or "",
            "location": loc,
            "remote": "remote" in loc.lower(),
            "url": j.get("absolute_url", "") or "",
        })
    return jobs


def fetch_lever(company):
    url = f"https://api.lever.co/v0/postings/{company['token']}?mode=json"
    data = _get_json(url)
    jobs = []
    for j in data:
        cats = j.get("categories") or {}
        loc = cats.get("location", "") or ""
        commitment = (cats.get("commitment", "") or "").lower()
        jobs.append({
            "company": company["name"],
            "id": f"lv-{company['token']}-{j.get('id')}",
            "title": j.get("text", "") or "",
            "location": loc,
            "remote": "remote" in loc.lower() or "remote" in commitment,
            "url": j.get("hostedUrl", "") or "",
        })
    return jobs


def fetch_ashby(company):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company['token']}"
    data = _get_json(url)
    jobs = []
    for j in data.get("jobs", []):
        loc = j.get("location", "") or ""
        jobs.append({
            "company": company["name"],
            "id": f"as-{company['token']}-{j.get('id')}",
            "title": j.get("title", "") or "",
            "location": loc,
            "remote": bool(j.get("isRemote")) or "remote" in loc.lower(),
            "url": j.get("jobUrl", "") or j.get("applyUrl", "") or "",
        })
    return jobs


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
}

# ----------------------------------------------------------------------------
# Matching
# ----------------------------------------------------------------------------

def title_matches(title):
    t = title.lower()
    if any(bad in t for bad in TITLE_EXCLUDE):
        return False
    return any(kw in t for kw in TITLE_KEYWORDS)


def location_matches(job):
    if not REQUIRE_LOCATION_MATCH:
        return True
    if job["remote"]:
        return True
    loc = job["location"].lower()
    if not loc:
        return True  # no location given, keep and let you judge
    return any(kw in loc for kw in LOCATION_KEYWORDS)


def job_is_match(job):
    return title_matches(job["title"]) and location_matches(job)


def is_senior(title):
    t = title.lower()
    return ("senior" in t) or ("sr." in t) or t.startswith("sr ") or (" sr " in t)


BOSTON_AREA = ("boston", "cambridge", "somerville", "watertown", "waltham",
               "newton", "massachusetts")


def is_priority_location(job):
    # Boston-area or remote roles get pulled to the top of each section.
    if job.get("remote"):
        return True
    loc = (job.get("location") or "").lower()
    return ("remote" in loc) or any(k in loc for k in BOSTON_AREA)


def sort_key(job):
    return (0 if is_priority_location(job) else 1, job["company"], job["title"])

# ----------------------------------------------------------------------------
# Seen-state persistence
# ----------------------------------------------------------------------------

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main():
    seen = load_seen()
    new_matches = []
    errors = []

    for company in COMPANIES:
        fetcher = FETCHERS.get(company.get("ats"))
        if not fetcher:
            errors.append(f"{company['name']}: unknown ATS '{company.get('ats')}'")
            continue
        try:
            jobs = fetcher(company)
        except urllib.error.HTTPError as e:
            errors.append(f"{company['name']}: HTTP {e.code} (check the token)")
            continue
        except Exception as e:
            errors.append(f"{company['name']}: {e}")
            continue

        for job in jobs:
            if job_is_match(job) and job["id"] not in seen:
                new_matches.append(job)
                seen.add(job["id"])
        time.sleep(0.5)  # be polite between companies

    save_seen(seen)

    today = date.today().isoformat()

    # Split matches: roles whose title does not say senior come first, senior
    # roles second. Within each, Boston-area and remote roles sort to the top.
    others = sorted([j for j in new_matches if not is_senior(j["title"])], key=sort_key)
    seniors = sorted([j for j in new_matches if is_senior(j["title"])], key=sort_key)

    def fmt(job):
        loc = job["location"] or ("Remote" if job["remote"] else "Location not listed")
        return [f"- **{job['title']}** - {job['company']} ({loc})", f"  {job['url']}"]

    def section(label, group):
        out = [f"## {label} ({len(group)})"]
        if group:
            for job in group:
                out += fmt(job)
        else:
            out.append("None today.")
        return out

    lines = [f"# New design roles: {today}", ""]
    if new_matches:
        lines.append(f"{len(new_matches)} new ({len(others)} roles, {len(seniors)} senior)")
        lines.append("")
        lines += section("Roles", others)
        lines.append("")
        lines += section("Senior roles", seniors)
    else:
        lines.append("No new matches today.")
    if errors:
        lines.append("")
        lines.append("## Warnings")
        for e in errors:
            lines.append(f"- {e}")

    report = "\n".join(lines)
    print(report)

    out_file = f"new_jobs_{today}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report + "\n")

    # Structured sidecar so the email step can build a styled HTML digest.
    with open(f"digest_{today}.json", "w", encoding="utf-8") as f:
        json.dump({"date": today, "seniors": seniors, "others": others,
                   "warnings": errors}, f, indent=2)

    print(f"\nSaved: {out_file}")
    print(f"Tracking {len(seen)} seen postings across {len(COMPANIES)} companies.")


if __name__ == "__main__":
    main()

# ----------------------------------------------------------------------------
# FINDING EACH COMPANY'S TOKEN
# ----------------------------------------------------------------------------
# Greenhouse: career URL looks like boards.greenhouse.io/COMPANYTOKEN
#             or the page embeds boards-api.greenhouse.io/v1/boards/COMPANYTOKEN
#             -> token is COMPANYTOKEN
# Lever:      career URL looks like jobs.lever.co/COMPANYTOKEN
#             -> token is COMPANYTOKEN
# Ashby:      career URL looks like jobs.ashbyhq.com/COMPANYTOKEN
#             -> token is COMPANYTOKEN
#
# Quick test for any token, e.g. Greenhouse:
#   https://boards-api.greenhouse.io/v1/boards/COMPANYTOKEN/jobs
# Paste that in a browser. If you get JSON, the token is correct.
#
# Workday-based companies (many large enterprises) do NOT have a simple public
# endpoint and are skipped by this script. For those, set a job alert on the
# company site directly.
