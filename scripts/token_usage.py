#!/usr/bin/env python3
"""Aggregate local Claude Code token usage into _data/token_usage.json.

The Claude Code CLI keeps a JSONL transcript per session under
~/.claude/projects/<project>/<session>.jsonl.  Every assistant record carries a
`message.usage` block with the token counts billed for that turn.  This script
walks those transcripts, buckets the counts by local calendar day, and writes a
pre-laid-out JSON blob that the Jekyll templates render as a GitHub-style
contribution heatmap.

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
DEFAULT_SOURCE = Path.home() / ".claude" / "projects"
DEFAULT_OUTPUT = REPO_ROOT / "_data" / "token_usage.json"

# The four token classes the API reports, in the order they are stacked in the
# breakdown bar on the detailed view.
TOKEN_KINDS = (
    ("input", "input_tokens", "Input"),
    ("output", "output_tokens", "Output"),
    ("cache_creation", "cache_creation_input_tokens", "Cache write"),
    ("cache_read", "cache_read_input_tokens", "Cache read"),
)

WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_timestamp(raw, tz):
    """Parse an ISO-8601 UTC timestamp into a timezone-aware local datetime."""
    if not raw:
        return None
    text = raw.replace("Z", "+00:00")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(tz)


def iter_usage_records(source, tz):
    """Yield (local_datetime, model, counts) for every billed assistant turn."""
    seen = set()
    for path in sorted(Path(source).rglob("*.jsonl")):
        try:
            handle = path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = record.get("message")
                if not isinstance(message, dict):
                    continue
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue

                # A resumed or forked session replays earlier turns into a new
                # transcript, so the same API response can appear more than
                # once.  Key on the message id to count each turn exactly once.
                key = (message.get("id"), record.get("requestId"))
                if key != (None, None):
                    if key in seen:
                        continue
                    seen.add(key)

                stamp = parse_timestamp(record.get("timestamp"), tz)
                if stamp is None:
                    continue

                counts = {name: int(usage.get(field) or 0)
                          for name, field, _ in TOKEN_KINDS}
                if not any(counts.values()):
                    continue

                model = message.get("model") or "unknown"
                yield stamp, model, counts


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


def longest_streak(daily, start, end):
    """Longest and current run of consecutive days with any usage."""
    longest = current = running = 0
    day = start
    while day <= end:
        if daily.get(day.isoformat(), {}).get("total", 0) > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0
        day += timedelta(days=1)
    current = running
    return longest, current


def build(source, days, tz, today):
    daily = defaultdict(lambda: {name: 0 for name, _, _ in TOKEN_KINDS})
    models = defaultdict(int)
    hour_weekday = [[0] * 24 for _ in range(7)]
    hourly = [0] * 24
    totals = {name: 0 for name, _, _ in TOKEN_KINDS}
    messages = 0
    first_seen = None
    last_seen = None

    for stamp, model, counts in iter_usage_records(source, tz):
        turn_total = sum(counts.values())
        date_key = stamp.date().isoformat()
        bucket = daily[date_key]
        for name, value in counts.items():
            bucket[name] += value
            totals[name] += value
        models[model] += turn_total
        # Python's weekday() is Mon=0; the calendar grid is Sun-first.
        row = (stamp.weekday() + 1) % 7
        hour_weekday[row][stamp.hour] += turn_total
        hourly[stamp.hour] += turn_total
        messages += 1
        first_seen = stamp if first_seen is None or stamp < first_seen else first_seen
        last_seen = stamp if last_seen is None or stamp > last_seen else last_seen

    for bucket in daily.values():
        bucket["total"] = sum(bucket[name] for name, _, _ in TOKEN_KINDS)

    # The grid always ends on today and starts on a Sunday so the columns line
    # up as whole weeks.
    end = today
    span_start = end - timedelta(days=days - 1)
    start = span_start - timedelta(days=(span_start.weekday() + 1) % 7)

    cuts = level_thresholds(
        bucket["total"] for date_key, bucket in daily.items()
        if start.isoformat() <= date_key <= end.isoformat()
    )

    weeks = []
    month_labels = []
    last_month = None
    day = start
    while day <= end:
        column = {"days": []}
        for _ in range(7):
            if day > end:
                break
            bucket = daily.get(day.isoformat())
            total = bucket["total"] if bucket else 0
            cell = {
                "date": day.isoformat(),
                "label": day.strftime("%b %-d, %Y"),
                "weekday": (day.weekday() + 1) % 7,
                "total": total,
                "compact": compact(total),
                "level": level_for(total, cuts),
            }
            if bucket:
                for name, _, _ in TOKEN_KINDS:
                    cell[name] = bucket[name]
            column["days"].append(cell)
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

    in_window = {
        date_key: bucket for date_key, bucket in daily.items()
        if start.isoformat() <= date_key <= end.isoformat()
    }
    window_total = sum(bucket["total"] for bucket in in_window.values())
    active_days = sum(1 for bucket in in_window.values() if bucket["total"] > 0)
    busiest_key = max(in_window, key=lambda k: in_window[k]["total"], default=None)
    longest, current = longest_streak(in_window, start, end)

    grand_total = sum(totals.values())
    by_type = []
    for name, _, label in TOKEN_KINDS:
        by_type.append({
            "key": name.replace("_", "-"),
            "label": label,
            "total": totals[name],
            "compact": compact(totals[name]),
            "share": round(100.0 * totals[name] / grand_total, 1) if grand_total else 0.0,
        })

    model_rows = []
    for name, value in sorted(models.items(), key=lambda kv: kv[1], reverse=True):
        model_rows.append({
            "name": name,
            "total": value,
            "compact": compact(value),
            "share": round(100.0 * value / grand_total, 1) if grand_total else 0.0,
        })

    peak_hour = max(range(24), key=lambda h: hourly[h]) if any(hourly) else None
    hour_peak = max(max(row) for row in hour_weekday) if any(hourly) else 0
    clock = []
    for hour in range(24):
        clock.append({
            "hour": hour,
            "label": "{:02d}:00".format(hour),
            "total": hourly[hour],
            "compact": compact(hourly[hour]),
            "share": round(100.0 * hourly[hour] / grand_total, 1) if grand_total else 0.0,
        })

    rhythm = []
    for row in range(7):
        cells = []
        for hour in range(24):
            value = hour_weekday[row][hour]
            cells.append({
                "hour": hour,
                "total": value,
                "compact": compact(value),
                "level": 0 if value <= 0 else min(4, max(1, int(round(4.0 * value / hour_peak)))),
            })
        rhythm.append({"weekday": WEEKDAY_LABELS[row], "hours": cells})

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
            "messages": messages,
            "active_days": active_days,
            "sessions": len(list(Path(source).rglob("*.jsonl"))) if Path(source).exists() else 0,
            "daily_average": int(round(window_total / active_days)) if active_days else 0,
            "daily_average_compact": compact(round(window_total / active_days)) if active_days else "0",
        },
        "busiest": {
            "date": busiest_key,
            "total": in_window[busiest_key]["total"] if busiest_key else 0,
            "compact": compact(in_window[busiest_key]["total"]) if busiest_key else "0",
        },
        "streak": {"longest": longest, "current": current},
        "thresholds": cuts,
        "weekday_labels": WEEKDAY_LABELS,
        "weeks": weeks,
        "month_labels": trimmed_labels,
        "by_type": by_type,
        "models": model_rows,
        "clock": clock,
        "peak_hour": "{:02d}:00".format(peak_hour) if peak_hour is not None else None,
        "rhythm": rhythm,
    }


def date_from(text):
    return datetime.strptime(text, "%Y-%m-%d").date()


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
    parser.add_argument("--source", default=str(DEFAULT_SOURCE),
                        help="directory holding Claude Code session transcripts "
                             "(default: %(default)s)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help="where to write the aggregated JSON (default: %(default)s)")
    parser.add_argument("--days", type=int, default=365,
                        help="size of the heatmap window in days (default: %(default)s)")
    parser.add_argument("--tz", default=None,
                        help="IANA timezone for day bucketing (default: this machine's)")
    args = parser.parse_args()

    source = Path(os.path.expanduser(args.source))
    if not source.exists():
        sys.exit("no Claude Code transcripts at {}".format(source))

    tz = resolve_tz(args.tz)
    payload = build(source, max(7, args.days), tz, datetime.now(tz).date())

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=False)
        handle.write("\n")

    print("wrote {}".format(output))
    print("  {} tokens over {} active day(s), {} turns".format(
        payload["totals"]["compact"],
        payload["totals"]["active_days"],
        payload["totals"]["messages"]))


if __name__ == "__main__":
    main()
