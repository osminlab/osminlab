# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Fill the `activity` window of README.md with GitHub stats (stdlib only).

One GraphQL request gives the account's totals and the language sizes of
the user's public, non-fork repositories; a second one gives the daily
contributions of every year, for the all-time total and the averages. The
numbers become SVG cards (scripts/cards.py, written to assets/stats/). Each card
is optional: if its data is missing the others are still rendered. If the
API fails or there is no token, README.md and assets/ are left unchanged.

Usage:
  GITHUB_TOKEN=... uv run scripts/stats.py
  GITHUB_TOKEN=... uv run scripts/stats.py --login osminlab --readme README.md \\
      --assets assets/stats

Only the text between these markers is rewritten:
  <!-- osminlab-site:activity:start --> ... <!-- osminlab-site:activity:end -->
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import median

from cards import write_cards

ROOT = Path(__file__).resolve().parent.parent
START = "<!-- osminlab-site:activity:start -->"
END = "<!-- osminlab-site:activity:end -->"
FETCH_ERRORS = (urllib.error.URLError, ValueError, OSError)
SHAPE_ERRORS = (KeyError, TypeError, ValueError, ZeroDivisionError)

API = "https://api.github.com/graphql"
QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    pullRequests(states: MERGED) { totalCount }
    contributionsCollection {
      contributionYears
      contributionCalendar { totalContributions }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 privacy: PUBLIC) {
      nodes { languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
        edges { size node { name } }
      } }
    }
  }
}
"""

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]  # date.weekday()
# Pinned version so logos do not change between runs.
SIMPLE_ICONS = "https://cdn.jsdelivr.net/npm/simple-icons@16.33.0/icons/{}.svg"
# Linguist names whose Simple Icons slug is not the name in lower case.
ICON_SLUGS = {
    "Shell": "gnubash",
    "C++": "cplusplus",
    "C#": "csharp",
    "Jupyter Notebook": "jupyter",
    "Vue": "vuedotjs",
}


def graphql(query: str, variables: dict, token: str) -> dict:
    """Return the `user` object (parts may be None). Raise on HTTP errors."""
    body = json.dumps({"query": query, "variables": variables})
    req = urllib.request.Request(
        API,
        data=body.encode(),
        headers={"Authorization": f"Bearer {token}", "User-Agent": "stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    return (payload.get("data") or {}).get("user") or {}


def daily_history(login: str, token: str, years: list[int]) -> dict[date, int]:
    """Contributions per day of every year.

    One aliased field per year: the API allows at most one year per
    contributionsCollection.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    fields = []
    for year in years:
        end = min(f"{year}-12-31T23:59:59Z", now)
        fields.append(
            f'y{year}: contributionsCollection(from: "{year}-01-01T00:00:00Z",'
            f' to: "{end}") {{ contributionCalendar {{ weeks {{'
            " contributionDays { date contributionCount } } } }"
        )
    query = f"query($login: String!) {{ user(login: $login) {{ {' '.join(fields)} }} }}"
    user = graphql(query, {"login": login}, token)
    days: dict[date, int] = {}
    for year in years:
        for week in user[f"y{year}"]["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                day = date.fromisoformat(d["date"])
                if day.year == year:
                    days[day] = d["contributionCount"]
    return days


def averages(days: dict[date, int], since: date, today: date) -> dict:
    """Average contributions per calendar month, median per active weekday.

    Months: only whole months count (the month the account was created and
    the current one are partial, so they are left out). Weekdays: the median
    of the days with at least one contribution, from the account's creation
    to yesterday, so a single busy day does not inflate the value.
    """
    weekday_active: dict[int, list[int]] = {w: [] for w in range(7)}
    for d, count in days.items():
        if since <= d < today and count:
            weekday_active[d.weekday()].append(count)
    partial = {(since.year, since.month), (today.year, today.month)}
    month_total: Counter[int] = Counter()
    month_seen: Counter[int] = Counter()
    y, m = since.year, since.month
    while (y, m) <= (today.year, today.month):
        if (y, m) not in partial:
            month_seen[m] += 1
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    for d, count in days.items():
        if since <= d and (d.year, d.month) not in partial:
            month_total[d.month] += count

    def avg(total: Counter[int], seen: Counter[int], key: int) -> float:
        return total[key] / seen[key] if seen[key] else 0.0

    return {
        "month_avg": [
            (f"{date(2000, m, 1):%b}", avg(month_total, month_seen, m))
            for m in range(1, 13)
        ],
        "weekday_median": [
            (WEEKDAYS[w], float(median(weekday_active[w])) if weekday_active[w] else 0.0)
            for w in range(7)
        ],
        "span": f"{since.year}–{today.year}",
    }


# Notebooks are counted as Python; markup and document formats are excluded.
LANGUAGE_ALIASES = {"Jupyter Notebook": "Python"}
IGNORED_LANGUAGES = {"HTML", "CSS", "SCSS", "TeX"}


def top_languages(repos: list[dict]) -> list[tuple[str, float]]:
    """The top 5 languages by bytes, as (name, percent)."""
    sizes: Counter[str] = Counter()
    for repo in repos:
        for edge in (repo.get("languages") or {}).get("edges") or []:
            name = edge["node"]["name"]
            if name not in IGNORED_LANGUAGES:
                sizes[LANGUAGE_ALIASES.get(name, name)] += edge["size"]
    total = sum(sizes.values())
    if not total:
        return []
    top = sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    # Skip shares that would round to 0.0%.
    shares = [(name, size * 100 / total) for name, size in top]
    return [(name, pct) for name, pct in shares if pct >= 0.05]


def language_icon(name: str) -> str | None:
    """The SVG path of the language's Simple Icons logo, or None."""
    slug = ICON_SLUGS.get(name) or re.sub(r"[^a-z0-9]", "", name.lower())
    try:
        with urllib.request.urlopen(SIMPLE_ICONS.format(slug), timeout=15) as resp:
            svg = resp.read().decode("utf-8")
    except FETCH_ERRORS:
        return None
    match = re.search(r'<path d="([^"]+)"', svg)
    return match.group(1) if match else None


def collect(login: str, token: str) -> dict:
    """Every stat available; a part whose data is missing is left out."""
    user = graphql(QUERY, {"login": login}, token)
    stats: dict = {}
    today = datetime.now(UTC).date()

    def calendar() -> None:
        total = user["contributionsCollection"]["contributionCalendar"]
        stats["year_total"] = total["totalContributions"]

    def since() -> None:
        created = datetime.fromisoformat(user["createdAt"]).date()
        stats.update(created=created, since=created.year, years=today.year - created.year)

    def history() -> None:
        years = user["contributionsCollection"]["contributionYears"]
        days = daily_history(login, token, years)
        stats["all_time"] = sum(days.values())
        stats.update(averages(days, stats.get("created") or min(days), today))

    def merged() -> None:
        stats["merged"] = user["pullRequests"]["totalCount"]

    def languages() -> None:
        stats["languages"] = [
            (name, pct, language_icon(name))
            for name, pct in top_languages(user["repositories"]["nodes"])
        ]

    for part in (calendar, since, history, merged, languages):
        try:
            part()
        except (*FETCH_ERRORS, *SHAPE_ERRORS) as err:
            # GitHub Actions annotation, shown in the run summary.
            print(f"::warning::{part.__name__} skipped: {type(err).__name__}: {err}")
    return stats


def picture(src: str, name: str, alt: str) -> str:
    """A card that follows the viewer's GitHub theme (light or dark)."""
    return (
        f'<picture><source media="(prefers-color-scheme: dark)" '
        f'srcset="{src}/{name}-dark.svg"><img alt="{alt}" '
        f'src="{src}/{name}-light.svg"></picture>'
    )


ALT = {
    "overview": "GitHub activity",
    "activity": "Contribution metrics: average per month, median per active day by weekday",
    "languages": "Top languages",
}


def stats_markdown(cards: list[str], src: str) -> str:
    """Return the Markdown for the window, or "" if there is no card."""
    if not cards:
        return ""
    pictures = "\n  ".join(picture(src, name, ALT[name]) for name in cards)
    return f'<p align="center">\n  {pictures}\n</p>\n'


def replace_window(text: str, body: str) -> str:
    """Replace what sits between the activity markers; raise if one is missing."""
    i, j = text.find(START), text.find(END)
    for marker, pos in ((START, i), (END, j)):
        if pos < 0:
            raise LookupError(f"marker not found in README.md: {marker}")
    if j < i:
        raise LookupError(f"marker {END} comes before {START}")
    return f"{text[: i + len(START)]}\n{body}{text[j:]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--login", default="osminlab")
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    parser.add_argument("--assets", type=Path, default=ROOT / "assets" / "stats")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    try:
        old = args.readme.read_text(encoding="utf-8")
        replace_window(old, "")  # fail early if a marker is missing
    except (OSError, LookupError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    try:
        stats = collect(args.login, token) if token else {}
    except FETCH_ERRORS:
        stats = {}
    if not stats:
        print(
            "::warning::No stats (no token or API failure); README.md untouched."
        )
        return 0
    cards = write_cards(stats, args.assets)
    src = os.path.relpath(args.assets.resolve(), args.readme.resolve().parent)
    body = stats_markdown(cards, src)
    if not body:
        print("::warning::No stats to show; README.md untouched.")
        return 0
    new = replace_window(old, body)
    if new == old:
        print("README.md is up to date.")
        return 0
    args.readme.write_text(new, encoding="utf-8")
    print("README.md updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
