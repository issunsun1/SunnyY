#!/usr/bin/env python3
"""Aggregate local AI coding-agent token usage into _data/token_usage.json.

Two agents keep transcripts on this machine and both record what they billed:

  Claude Code  ~/.claude/projects/<project>/<session>.jsonl
               every assistant record carries a `message.usage` block.
  Codex        ~/.codex/sessions/<y>/<m>/<d>/rollout-*.jsonl and
               ~/.codex/archived_sessions/rollout-*.jsonl
               `token_count` events carry a running `total_token_usage`.

Both are walked, bucketed by local calendar day, and consolidated into a single
series that the Jekyll templates render as a GitHub-style contribution heatmap.

Only aggregate counts are written out - no prompts, file paths, or project
names ever leave the local machine.

Usage:
    python3 scripts/token_usage.py            # regenerate _data/token_usage.json
    python3 scripts/token_usage.py --days 180
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CLAUDE_SOURCE = Path.home() / ".claude" / "projects"
DEFAULT_CODEX_SOURCE = Path.home() / ".codex"
DEFAULT_OUTPUT = REPO_ROOT / "_data" / "token_usage.json"

# Claude Code reports each token class separately; the day total is their sum.
CLAUDE_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)

WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_timestamp(raw, tz):
    """Parse an ISO-8601 UTC timestamp into a timezone-aware local datetime."""
    if not raw:
        return None
    text = str(raw).replace("Z", "+00:00")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(tz)


def read_jsonl(path):
    """Yield parsed records from a JSONL file, skipping anything malformed."""
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def iter_claude_usage(source, tz):
    """Yield (local_datetime, tokens) for every billed Claude Code turn."""
    seen = set()
    for path in sorted(Path(source).rglob("*.jsonl")):
        for record in read_jsonl(path):
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue

            # Claude Code writes one transcript record per content block, so a
            # single API response repeats its usage object across several
            # lines. Resumed sessions replay earlier turns too. Keying on the
            # message id counts each response exactly once.
            key = (message.get("id"), record.get("requestId"))
            if key != (None, None):
                if key in seen:
                    continue
                seen.add(key)

            stamp = parse_timestamp(record.get("timestamp"), tz)
            if stamp is None:
                continue

            tokens = sum(int(usage.get(field) or 0) for field in CLAUDE_TOKEN_FIELDS)
            if tokens > 0:
                yield stamp, tokens, path


def codex_transcripts(source):
    source = Path(source)
    paths = []
    paths.extend(sorted((source / "sessions").rglob("rollout-*.jsonl")))
    paths.extend(sorted((source / "archived_sessions").glob("rollout-*.jsonl")))
    return paths


def iter_codex_usage(source, tz):
    """Yield (local_datetime, tokens) for every billed Codex turn.

    `token_count` events carry the session's running total rather than the
    turn's own cost, and the same total can be emitted more than once. Taking
    the increase between consecutive events gives the per-turn spend and lands
    on the session's final total exactly.
    """
    for path in codex_transcripts(source):
        running = 0
        for record in read_jsonl(path):
            payload = record.get("payload")
            if not isinstance(payload, dict) or payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            if not isinstance(info, dict):
                continue
            totals = info.get("total_token_usage")
            if not isinstance(totals, dict):
                continue

            current = int(totals.get("total_tokens") or 0)
            # A session that restarts its counter is treated as a fresh run
            # rather than as a negative delta.
            delta = current - running if current >= running else current
            running = current
            if delta <= 0:
                continue

            stamp = parse_timestamp(record.get("timestamp"), tz)
            if stamp is None:
                continue
            yield stamp, delta, path


def compact(value):
    """Format a token count the way the UI shows it: 1.2K, 3.4M, 5.6B."""
    value = float(value)
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= limit:
            scaled = value / limit
            precision = 0 if scaled >= 100 else 1
            return "{:.{}f}{}".format(scaled, precision, suffix)
    return str(int(value))


def level_thresholds(values):
    """Pick four cut-offs that spread the active days across shades 1-4."""
    active = sorted(v for v in values if v > 0)
    if not active:
        return [1, 2, 3, 4]
    if len(active) < 4:
        # Too few active days for quantiles to mean anything - split the range.
        top = active[-1]
        return [max(1, int(round(top * frac))) for frac in (0.25, 0.5, 0.75, 1.0)]
    cuts = []
    for frac in (0.25, 0.5, 0.75, 1.0):
        index = min(len(active) - 1, int(round(frac * (len(active) - 1))))
        cuts.append(active[index])
    # Keep the ladder strictly increasing so every shade is reachable.
    for i in range(1, len(cuts)):
        if cuts[i] <= cuts[i - 1]:
            cuts[i] = cuts[i - 1] + 1
    return cuts


def level_for(value, cuts):
    if value <= 0:
        return 0
    for index, cut in enumerate(cuts):
        if value <= cut:
            return index + 1
    return 4


def streaks(daily, start, end):
    """Longest and current run of consecutive days with any usage."""
    longest = running = 0
    day = start
    while day <= end:
        if daily.get(day.isoformat(), 0) > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0
        day += timedelta(days=1)
    return longest, running


def date_from(text):
    return datetime.strptime(text, "%Y-%m-%d").date()


def build(claude_source, codex_source, days, tz, today):
    daily = defaultdict(int)
    sources = []
    total_turns = 0
    total_sessions = 0
    grand_total = 0
    first_seen = None
    last_seen = None

    readers = [("Claude Code", iter_claude_usage, claude_source),
               ("Codex", iter_codex_usage, codex_source)]

    for name, reader, source in readers:
        if not source or not Path(source).exists():
            continue
        subtotal = turns = 0
        files = set()
        for stamp, tokens, path in reader(source, tz):
            daily[stamp.date().isoformat()] += tokens
            subtotal += tokens
            turns += 1
            files.add(path)
            first_seen = stamp if first_seen is None or stamp < first_seen else first_seen
            last_seen = stamp if last_seen is None or stamp > last_seen else last_seen
        if subtotal <= 0:
            continue
        grand_total += subtotal
        total_turns += turns
        total_sessions += len(files)
        sources.append({
            "name": name,
            "total": subtotal,
            "compact": compact(subtotal),
            "turns": turns,
            "sessions": len(files),
        })

    for entry in sources:
        entry["share"] = round(100.0 * entry["total"] / grand_total, 1) if grand_total else 0.0

    # The grid always ends on today and starts on a Sunday so the columns line
    # up as whole weeks.
    end = today
    span_start = end - timedelta(days=days - 1)
    start = span_start - timedelta(days=(span_start.weekday() + 1) % 7)

    in_window = {key: value for key, value in daily.items()
                 if start.isoformat() <= key <= end.isoformat()}
    cuts = level_thresholds(in_window.values())

    weeks = []
    month_labels = []
    last_month = None
    day = start
    while day <= end:
        column = {"days": []}
        for _ in range(7):
            if day > end:
                break
            total = daily.get(day.isoformat(), 0)
            column["days"].append({
                "date": day.isoformat(),
                "label": day.strftime("%b %-d, %Y"),
                "total": total,
                "compact": compact(total),
                "level": level_for(total, cuts),
            })
            day += timedelta(days=1)
        # Label a column with its month when the month changes mid-grid.
        first_day = date_from(column["days"][0]["date"])
        if first_day.month != last_month:
            last_month = first_day.month
            month_labels.append({
                "column": len(weeks),
                "label": MONTH_LABELS[first_day.month - 1],
            })
        weeks.append(column)

    # Drop a month label that would collide with the next one.
    trimmed_labels = []
    for index, label in enumerate(month_labels):
        following = month_labels[index + 1]["column"] if index + 1 < len(month_labels) else None
        if following is not None and following - label["column"] < 3:
            continue
        trimmed_labels.append(label)

    window_total = sum(in_window.values())
    active_days = sum(1 for value in in_window.values() if value > 0)
    busiest_key = max(in_window, key=lambda k: in_window[k], default=None)
    longest, current = streaks(in_window, start, end)

    return {
        "generated_at": datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z").strip(),
        "timezone": str(tz),
        "window_days": (end - start).days + 1,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "first_activity": first_seen.date().isoformat() if first_seen else None,
        "last_activity": last_seen.date().isoformat() if last_seen else None,
        "has_data": grand_total > 0,
        "totals": {
            "total": grand_total,
            "compact": compact(grand_total),
            "window_total": window_total,
            "window_compact": compact(window_total),
            "turns": total_turns,
            "active_days": active_days,
            "sessions": total_sessions,
            "daily_average": int(round(window_total / active_days)) if active_days else 0,
            "daily_average_compact": compact(round(window_total / active_days)) if active_days else "0",
        },
        "busiest": {
            "date": busiest_key,
            "total": in_window[busiest_key] if busiest_key else 0,
            "compact": compact(in_window[busiest_key]) if busiest_key else "0",
        },
        "streak": {"longest": longest, "current": current},
        "thresholds": cuts,
        "weekday_labels": WEEKDAY_LABELS,
        "weeks": weeks,
        "month_labels": trimmed_labels,
        "sources": sources,
    }


def resolve_tz(name):
    if not name:
        return datetime.now().astimezone().tzinfo
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        sys.exit("--tz needs Python 3.9+ with zoneinfo available")
    try:
        return ZoneInfo(name)
    except Exception:
        sys.exit("unknown timezone: {}".format(name))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--claude-source", default=str(DEFAULT_CLAUDE_SOURCE),
                        help="Claude Code transcript directory (default: %(default)s)")
    parser.add_argument("--codex-source", default=str(DEFAULT_CODEX_SOURCE),
                        help="Codex home directory (default: %(default)s)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help="where to write the aggregated JSON (default: %(default)s)")
    parser.add_argument("--days", type=int, default=365,
                        help="size of the heatmap window in days (default: %(default)s)")
    parser.add_argument("--tz", default=None,
                        help="IANA timezone for day bucketing (default: this machine's)")
    args = parser.parse_args()

    claude_source = Path(os.path.expanduser(args.claude_source))
    codex_source = Path(os.path.expanduser(args.codex_source))
    if not claude_source.exists() and not codex_source.exists():
        sys.exit("no transcripts found at {} or {}".format(claude_source, codex_source))

    tz = resolve_tz(args.tz)
    payload = build(claude_source, codex_source, max(7, args.days), tz,
                    datetime.now(tz).date())

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=False)
        handle.write("\n")

    print("wrote {}".format(output))
    for entry in payload["sources"]:
        print("  {:<12} {:>8} over {} session(s)".format(
            entry["name"], entry["compact"], entry["sessions"]))
    print("  {:<12} {:>8} over {} active day(s)".format(
        "combined", payload["totals"]["compact"], payload["totals"]["active_days"]))


if __name__ == "__main__":
    main()
