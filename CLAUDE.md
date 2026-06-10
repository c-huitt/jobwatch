# CLAUDE.md — jobwatch

Persistent context for this project. Read this at the start of every session.

## What this project is

A personal job-watching tool. `jobwatch.py` queries public Applicant Tracking
System (ATS) APIs for a list of companies, filters postings by title and
location, dedupes against `seen.json` so only new postings surface, and writes
results to a dated file `new_jobs_YYYY-MM-DD.md`. The goal is a reliable,
low-maintenance system that surfaces new design job openings across a wide net
of employers every morning.

## Who this is for

A recent graduate searching for UX, UI, or Product Design roles. Based in
Boston, MA, but open to roles anywhere: Boston metro, a Boston office of a
larger company, or fully remote with a non-Boston company. Open to all
sectors, not just tech or startups. About 4 months of professional experience,
so junior, associate, mid-level, and senior individual-contributor roles are
all in scope.

## Files

- `jobwatch.py` — the script. Standard library only, no pip installs.
  Run with: `python3 jobwatch.py`
- `seen.json` — tracks postings already reported. Do not hand-edit.
- `new_jobs_YYYY-MM-DD.md` — dated output of new matches.
- `README_WORKDAY.md` — major employers on Workday or closed systems that
  have no public API and need manual job alerts instead.
- `jobwatch.yml` — GitHub Actions workflow for daily cloud runs.

## Filters (keep these unless I say otherwise)

Match titles containing: product designer, ux designer, ui designer, ux/ui,
ui/ux, experience designer, interaction designer, associate designer,
product design.

KEEP Senior roles. Exclude titles containing: staff, principal, lead, manager,
director, head of, vp. Exclude AI annotation, data labeling, labeler, and
rater roles entirely.

Locations: keep Boston metro plus anything remote or US-wide.

## ATS endpoint reference

A token is valid only when the URL returns JSON containing jobs, not a 404.

- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/TOKEN/jobs`
- Lever:      `https://api.lever.co/v0/postings/TOKEN?mode=json`
- Ashby:      `https://api.ashbyhq.com/posting-api/job-board/TOKEN`

When adding any company, test its endpoint first. If a company uses Workday or
another closed system, put it in `README_WORKDAY.md`, not in `COMPANIES`.

## Working conventions

- After any change to `jobwatch.py`, run it and confirm zero warnings.
- Verify every new company's endpoint returns JSON before adding it, so the
  COMPANIES list stays clean.
- Prefer breadth: more verified companies is better.
- Do not use em dashes anywhere, in code comments or in messages to me.
- Keep explanations concise. Draft and iterate rather than overbuilding.

## Definition of done for a session

Zero warnings on run, any new companies verified live, and a short summary of
what changed plus the current company count.
