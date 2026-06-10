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

import html
import json
import os
import re
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

# Location policy: keep only roles open to the US or Canada. A posting is kept
# if it names a US/Canada location (even alongside other countries, e.g.
# "London; New York; US"), or is remote with no country named (these are all
# US-based companies, so a bare "Remote" is treated as US-eligible). Postings
# that name ONLY non-US/Canada locations are dropped. See location_matches().
# Set REQUIRE_LOCATION_MATCH = False to keep everything regardless of location.
REQUIRE_LOCATION_MATCH = True

# Titles to exclude even if they match above (avoids senior-only noise and
# the AI-annotation roles you want to skip).
TITLE_EXCLUDE = [
    "staff", "principal", "lead", "manager", "director",
    "head of", "vp", "annotation", "data labeling", "labeler", "rater",
    "mechanical",  # drops hardware "Product Design Mechanical Engineer" roles
]
# Note: "senior" / "sr." are intentionally NOT excluded, so Senior roles show.
# Add them back here if Senior postings become noise.

# Companies to watch.
#   ats:   "greenhouse" | "lever" | "ashby" | "smartrecruiters" | "workable"
#          | "recruitee" | "breezy"
#   token: the company's board identifier (case-sensitive for SmartRecruiters)
# Tokens marked "# verified" were confirmed live. The rest are best guesses
# (usually the company slug). On the first run, the script prints a Warning
# for any token that fails. Just fix or delete those lines. Companies that use
# Workday have NO public API and are listed in README_WORKDAY.md instead;
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

    # --- Boston metro: expansion round 2 (all MA-based, verified live) ---
    {"name": "Wasabi",           "ats": "greenhouse", "token": "wasabi"},
    {"name": "Quaise Energy",    "ats": "greenhouse", "token": "quaise"},
    {"name": "VEIR",             "ats": "greenhouse", "token": "veir"},
    {"name": "CloudZero",        "ats": "ashby",      "token": "cloudzero"},
    {"name": "Paperless Parts",  "ats": "greenhouse", "token": "paperlessparts"},
    {"name": "Owl Labs",         "ats": "greenhouse", "token": "owllabs"},
    {"name": "BlueConic",        "ats": "greenhouse", "token": "blueconic"},
    {"name": "Mendix",           "ats": "lever",      "token": "mendix"},
    {"name": "ButcherBox",       "ats": "greenhouse", "token": "butcherbox"},
    {"name": "Ellevation",       "ats": "lever",      "token": "ellevationeducation"},
    {"name": "Pickle Robot",     "ats": "lever",      "token": "picklerobot"},
    {"name": "Demiurge Studios", "ats": "lever",      "token": "demiurgestudios"},
    {"name": "Blueprint Medicines","ats": "greenhouse","token": "blueprintmedicines"},
    {"name": "Disc Medicine",    "ats": "greenhouse", "token": "discmedicine"},
    {"name": "Relay Therapeutics","ats": "greenhouse", "token": "relaytherapeutics"},
    {"name": "Tango Therapeutics","ats": "greenhouse", "token": "tangotherapeutics"},
    {"name": "Akebia Therapeutics","ats": "greenhouse","token": "akebiatherapeutics"},
    {"name": "Korro Bio",        "ats": "lever",      "token": "korrobio"},
    {"name": "Chroma Medicine",  "ats": "greenhouse", "token": "chromamedicine"},
    {"name": "Valo Health",      "ats": "greenhouse", "token": "valohealth"},
    {"name": "Strand Therapeutics","ats": "greenhouse","token": "strandtherapeutics"},

    # --- Other ATS providers (SmartRecruiters / Workable / Recruitee / Breezy) ---
    # Add more here as you verify them. SmartRecruiters tokens are the exact,
    # case-sensitive company identifier (e.g. "Experian", not "experian").
    {"name": "Experian",         "ats": "smartrecruiters", "token": "Experian"},

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


def fetch_smartrecruiters(company):
    jobs = []
    offset = 0
    while True:
        url = (f"https://api.smartrecruiters.com/v1/companies/{company['token']}"
               f"/postings?limit=100&offset={offset}")
        data = _get_json(url)
        content = data.get("content", [])
        for j in content:
            loc = j.get("location") or {}
            parts = [loc.get("city", ""), loc.get("region", ""), loc.get("country", "")]
            loc_str = ", ".join(p for p in parts if p)
            jid = j.get("id") or j.get("uuid") or ""
            jobs.append({
                "company": company["name"],
                "id": f"sr-{company['token']}-{jid}",
                "title": j.get("name", "") or "",
                "location": loc_str,
                "remote": bool(loc.get("remote")) or "remote" in loc_str.lower(),
                "url": f"https://jobs.smartrecruiters.com/{company['token']}/{jid}",
            })
        if len(content) < 100:
            break
        offset += 100
        if offset >= 600:  # safety cap on very large boards
            break
        time.sleep(0.2)
    return jobs


def fetch_workable(company):
    url = (f"https://apply.workable.com/api/v1/widget/accounts/"
           f"{company['token']}?details=true")
    data = _get_json(url)
    jobs = []
    for j in data.get("jobs", []):
        loc = j.get("location") or {}
        parts = [loc.get("city", ""), loc.get("region", ""), loc.get("country", "")]
        loc_str = ", ".join(p for p in parts if p)
        code = j.get("shortcode") or j.get("code") or ""
        jobs.append({
            "company": company["name"],
            "id": f"wk-{company['token']}-{code}",
            "title": j.get("title", "") or "",
            "location": loc_str,
            "remote": bool(loc.get("telecommuting")) or "remote" in loc_str.lower(),
            "url": j.get("url") or f"https://apply.workable.com/{company['token']}/j/{code}/",
        })
    return jobs


def fetch_recruitee(company):
    url = f"https://{company['token']}.recruitee.com/api/offers/"
    data = _get_json(url)
    jobs = []
    for j in data.get("offers", []):
        loc_str = j.get("location") or ", ".join(
            p for p in [j.get("city", ""), j.get("country", "")] if p)
        jobs.append({
            "company": company["name"],
            "id": f"rc-{company['token']}-{j.get('id')}",
            "title": j.get("title", "") or "",
            "location": loc_str or "",
            "remote": bool(j.get("remote")) or "remote" in (loc_str or "").lower(),
            "url": j.get("careers_url") or j.get("url") or "",
        })
    return jobs


def fetch_breezy(company):
    url = f"https://{company['token']}.breezy.hr/json"
    data = _get_json(url)
    jobs = []
    for j in (data if isinstance(data, list) else []):
        loc = j.get("location") or {}
        loc_str = loc.get("name", "") if isinstance(loc, dict) else (loc or "")
        remote = bool(loc.get("is_remote")) if isinstance(loc, dict) else False
        jobs.append({
            "company": company["name"],
            "id": f"bz-{company['token']}-{j.get('id')}",
            "title": j.get("name", "") or "",
            "location": loc_str,
            "remote": remote or "remote" in (loc_str or "").lower(),
            "url": j.get("url") or "",
        })
    return jobs


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "workable": fetch_workable,
    "recruitee": fetch_recruitee,
    "breezy": fetch_breezy,
}

# ----------------------------------------------------------------------------
# Matching
# ----------------------------------------------------------------------------

def title_matches(title):
    t = title.lower()
    if any(bad in t for bad in TITLE_EXCLUDE):
        return False
    return any(kw in t for kw in TITLE_KEYWORDS)


# Strong, unambiguous US / Canada signals (case-insensitive substring).
US_STRONG = (
    "united states", "u.s.a", "u.s.", "usa", "north america",
    "remote, us", "remote - us", "remote-us", "remote us", "us-remote",
    "remote (us", "(us)", "us only", "anywhere in the us",
    "new york", "nyc", "san francisco", "bay area", "los angeles", "seattle",
    "boston", "cambridge", "somerville", "watertown", "waltham", "newton",
    "chicago", "austin", "denver", "atlanta", "dallas", "houston", "portland",
    "miami", "philadelphia", "phoenix", "san diego", "san jose", "minneapolis",
    "detroit", "nashville", "charlotte", "raleigh", "pittsburgh", "salt lake",
    "washington, d", "washington d", "brooklyn",
)
CA_STRONG = (
    "canada", "canadian", "toronto", "vancouver", "montreal", "ottawa",
    "calgary", "edmonton", "waterloo", "ontario", "quebec", "british columbia",
)
# Non-US/Canada places. If one of these appears and no US/Canada signal does,
# the posting is dropped.
FOREIGN = (
    "united kingdom", " uk", "(uk", "london", "england", "scotland", "wales",
    "ireland", "dublin", "germany", "berlin", "munich", "hamburg", "france",
    "paris", "spain", "madrid", "barcelona", "portugal", "lisbon", "porto",
    "netherlands", "amsterdam", "belgium", "brussels", "italy", "rome", "milan",
    "switzerland", "zurich", "geneva", "austria", "vienna", "poland", "warsaw",
    "krakow", "romania", "bucharest", "czech", "prague", "hungary", "budapest",
    "sweden", "stockholm", "norway", "oslo", "denmark", "copenhagen", "finland",
    "helsinki", "greece", "athens", "india", "bangalore", "bengaluru",
    "hyderabad", "mumbai", "delhi", "gurgaon", "gurugram", "pune", "chennai",
    "noida", "kolkata", "australia", "sydney", "melbourne", "brisbane", "perth",
    "new zealand", "auckland", "singapore", "japan", "tokyo", "osaka", "china",
    "shanghai", "beijing", "shenzhen", "hong kong", "taiwan", "taipei", "korea",
    "seoul", "brazil", "brasil", "são paulo", "sao paulo", "rio de janeiro",
    "mexico", "guadalajara", "argentina", "buenos aires", "colombia", "bogota",
    "chile", "santiago", "peru", "lima", "israel", "tel aviv",
    "united arab emirates", "dubai", "abu dhabi", "south africa",
    "johannesburg", "cape town", "nigeria", "lagos", "kenya", "nairobi",
    "egypt", "cairo", "turkey", "istanbul", "philippines", "manila",
    "indonesia", "jakarta", "vietnam", "hanoi", "thailand", "bangkok",
    "malaysia", "kuala lumpur", "pakistan", "bangladesh", "ukraine", "kyiv",
    "serbia", "belgrade", "bulgaria", "croatia", "lithuania", "estonia",
    "latvia", "europe", "emea", "apac", "latam",
)
# US state abbreviations as whole uppercase tokens (e.g. "Austin, TX"). Checked
# against the original-case string so foreign words like "Germany" cannot match.
_STATE_RE = re.compile(
    r"\b(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|"
    r"MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|"
    r"WA|WV|WI|WY|DC)\b")
_USABBR_RE = re.compile(r"\b(?:US|USA)\b")


def location_matches(job):
    if not REQUIRE_LOCATION_MATCH:
        return True
    loc = job["location"] or ""
    low = loc.lower()

    # Strong US/Canada signal anywhere keeps the role, even if other countries
    # are also listed (multi-location postings open to US candidates).
    if (any(p in low for p in US_STRONG) or any(p in low for p in CA_STRONG)
            or _USABBR_RE.search(loc)):
        return True

    # Otherwise, any foreign place named means it is not a US/Canada role.
    if any(p in low for p in FOREIGN):
        return False

    # Weak US signal: a state abbreviation, with no foreign place present.
    if _STATE_RE.search(loc):
        return True

    # No country named at all: bare "Remote" or empty. Treat as US-eligible
    # since every tracked company is US-based.
    if job["remote"] or not low.strip():
        return True

    return False


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


def pretty_date(iso):
    d = date.fromisoformat(iso)
    n = d.day
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{d.strftime('%B')} {n}{suffix} {d.year}"


# Standalone "Open all" web page, regenerated each run and served via GitHub
# Pages. The daily email links here so you can open every posting in tabs.
OPEN_ALL_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>New design roles - __PRETTY__</title>
<style>
:root{--ink:#1f2330;--muted:#6b7280;--border:#e8eaed;--blue:#2563eb;--grey:#6b7280;--bg:#f4f5f7}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;line-height:1.5}
.wrap{max-width:760px;margin:0 auto;padding:28px 18px 60px}
.card{background:#fff;border:1px solid var(--border);border-radius:14px;padding:28px 30px}
h1{font-size:23px;margin:0}
.sub{color:var(--muted);font-size:14px;margin-top:6px}
.bar{position:sticky;top:0;background:var(--bg);padding:12px 0;margin:14px 0 4px;z-index:5}
button{font:600 14px inherit;border:1px solid var(--border);background:#fff;color:var(--ink);border-radius:10px;padding:10px 16px;cursor:pointer}
button:hover{background:#f3f4f6}
button.primary{background:var(--blue);color:#fff;border-color:var(--blue)}
.sec{margin-top:30px}
.sechead{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.label{font:700 14px inherit;text-transform:uppercase;letter-spacing:.03em}
.pill{color:#fff;border-radius:999px;font:600 12px inherit;padding:4px 10px}
.pill.blue{background:var(--blue)}.pill.grey{background:var(--grey)}
ul{list-style:none;margin:0;padding:0}
li{padding:16px 0;border-bottom:1px solid var(--border)}
li a{font:600 16px inherit;text-decoration:none}
.sec.roles li a{color:var(--blue)}.sec.senior li a{color:var(--grey)}
.meta{display:block;color:var(--muted);font-size:13px;margin-top:4px}
.note{color:var(--muted);font-size:13px;margin-top:8px}
.foot{color:var(--muted);font-size:12px;margin-top:28px}
</style></head>
<body><div class="wrap"><div class="card">
<h1>New design roles</h1>
<div class="sub">__TOTAL__ for __PRETTY__ &middot; __NROLES__ roles, __NSENIOR__ senior</div>
<div class="bar"><button class="primary" onclick="openAll(ALL)">Open all __TOTAL__ in new tabs</button></div>
<div class="note">First time only: your browser may block the extra tabs. Allow pop-ups for this page, then click again.</div>
<div class="sec roles">
<div class="sechead"><span class="label">Roles</span><span class="pill blue">__NROLES__</span>
<button onclick="openAll(ROLES)">Open all roles</button></div>
<ul>__ROLES_ROWS__</ul></div>
<div class="sec senior">
<div class="sechead"><span class="label">Senior roles</span><span class="pill grey">__NSENIOR__</span>
<button onclick="openAll(SENIOR)">Open all senior</button></div>
<ul>__SENIOR_ROWS__</ul></div>
<div class="foot">Generated by jobwatch. Always shows the most recent run.</div>
</div></div>
<script>
var ROLES=__ROLES_URLS__,SENIOR=__SENIOR_URLS__,ALL=__ALL_URLS__;
function openAll(urls){urls.forEach(function(u){window.open(u,'_blank','noopener');});}
</script>
</body></html>
"""


def _page_rows(group):
    out = []
    for j in group:
        loc = j["location"] or ("Remote" if j["remote"] else "Location not listed")
        out.append(
            f'<li><a href="{html.escape(j["url"], quote=True)}" target="_blank" '
            f'rel="noopener">{html.escape(j["title"])}</a>'
            f'<span class="meta">{html.escape(j["company"])} &middot; '
            f'{html.escape(loc)}</span></li>')
    return "\n".join(out)


def write_open_all_page(today, others, seniors):
    total = len(others) + len(seniors)
    repl = {
        "__PRETTY__": html.escape(pretty_date(today)),
        "__TOTAL__": str(total),
        "__NROLES__": str(len(others)),
        "__NSENIOR__": str(len(seniors)),
        "__ROLES_ROWS__": _page_rows(others),
        "__SENIOR_ROWS__": _page_rows(seniors),
        "__ROLES_URLS__": json.dumps([j["url"] for j in others]),
        "__SENIOR_URLS__": json.dumps([j["url"] for j in seniors]),
        "__ALL_URLS__": json.dumps([j["url"] for j in others + seniors]),
    }
    page = OPEN_ALL_TEMPLATE
    for k, v in repl.items():
        page = page.replace(k, v)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(page)

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
                   "warnings": errors, "companies": len(COMPANIES)}, f, indent=2)

    # Regenerate the "Open all" page only when there are matches, so a quiet
    # run does not wipe the last useful page the email links to.
    if new_matches:
        write_open_all_page(today, others, seniors)

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
