#!/usr/bin/env python3
"""
llm_log_analyzer.py
===================

Read OmniMedical structured logs (JSON-lines) and produce a development
priorities report. Runs in two modes:

  1. **Statistical mode** (default, always works, no API key needed)
     - Parses omni.jsonl + errors.jsonl
     - Aggregates events by category, error_type, slowest durations
     - Detects repeated failures, slow functions, hot paths
     - Outputs a JSON report + human-readable Markdown summary

  2. **LLM mode** (--llm flag)
     - Sends the statistical summary to z-ai chat completion
     - Asks the LLM to identify development priorities
     - Saves LLM response as Markdown

Usage:
    python scripts/llm_log_analyzer.py                       # stats only
    python scripts/llm_log_analyzer.py --llm                 # stats + LLM
    python scripts/llm_log_analyzer.py --log-dir ~/.omni/logs
    python scripts/llm_log_analyzer.py --since 24h           # last 24h only
    python scripts/llm_log_analyzer.py --out report.md

Output files (in --out-dir, default ./log-reports):
    - stats.json          — raw aggregated statistics
    - summary.md          — human-readable summary (stats only)
    - llm_review.md       — LLM review (only if --llm)
    - timeline.csv        — per-event timeline (optional, --csv)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

DEFAULT_LOG_DIR = Path.home() / ".omni" / "logs"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LogStats:
    """Aggregated statistics from the JSONL logs."""

    total_events: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_event: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)
    by_logger: dict[str, int] = field(default_factory=dict)
    errors_by_type: dict[str, int] = field(default_factory=dict)
    errors_by_event: dict[str, int] = field(default_factory=dict)
    durations_ms: dict[str, list[float]] = field(default_factory=dict)
    sessions: set[str] = field(default_factory=set)
    first_event_ts: str | None = None
    last_event_ts: str | None = None
    top_files_with_errors: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sessions"] = list(self.sessions)
        d["durations_ms"] = {
            k: {
                "count": len(v),
                "min_ms": min(v) if v else 0,
                "max_ms": max(v) if v else 0,
                "mean_ms": round(mean(v), 2) if v else 0,
                "median_ms": round(median(v), 2) if v else 0,
                "stdev_ms": round(stdev(v), 2) if len(v) > 1 else 0,
            }
            for k, v in self.durations_ms.items()
        }
        return d


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO 8601 timestamp (handles 'Z' suffix and offset)."""
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


def _iter_jsonl(path: Path, since: datetime | None = None):
    """Yield parsed JSON dicts from a .jsonl file."""
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since is not None and obj.get("ts"):
                try:
                    if _parse_ts(obj["ts"]) < since:
                        continue
                except Exception:
                    pass
            obj["_line_no"] = line_no
            obj["_source_file"] = str(path.name)
            yield obj


def collect_stats(log_dir: Path, since: datetime | None = None) -> LogStats:
    """Walk all .jsonl files under ``log_dir`` and aggregate stats."""
    stats = LogStats()

    # All jsonl files (omni.jsonl + rotated backups + errors.jsonl + ...)
    jsonl_files = sorted(log_dir.glob("*.jsonl"))

    for path in jsonl_files:
        for obj in _iter_jsonl(path, since=since):
            stats.total_events += 1

            ts = obj.get("ts")
            if ts:
                if stats.first_event_ts is None or ts < stats.first_event_ts:
                    stats.first_event_ts = ts
                if stats.last_event_ts is None or ts > stats.last_event_ts:
                    stats.last_event_ts = ts

            cat = obj.get("category") or "other"
            event = obj.get("event") or obj.get("message", "")[:80]
            sev = obj.get("level", "info")
            logger = obj.get("logger", "?")
            sess = obj.get("session_id")
            if sess:
                stats.sessions.add(sess)

            stats.by_category[cat] = stats.by_category.get(cat, 0) + 1
            stats.by_event[event] = stats.by_event.get(event, 0) + 1
            stats.by_severity[sev] = stats.by_severity.get(sev, 0) + 1
            stats.by_logger[logger] = stats.by_logger.get(logger, 0) + 1

            if sev in ("error", "critical"):
                err_type = obj.get("error_type") or obj.get("exception", "")[:80] or "unknown"
                stats.errors_by_type[err_type] = stats.errors_by_type.get(err_type, 0) + 1
                stats.errors_by_event[event] = stats.errors_by_event.get(event, 0) + 1
                file_loc = obj.get("file", "?")
                stats.top_files_with_errors[file_loc] = (
                    stats.top_files_with_errors.get(file_loc, 0) + 1
                )

            dur = obj.get("duration_ms")
            if dur is not None and isinstance(dur, (int, float)):
                stats.durations_ms.setdefault(event, []).append(float(dur))

    return stats


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def render_markdown(stats: LogStats, since: datetime | None, log_dir: Path) -> str:
    """Render a human-readable Markdown summary."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    since_str = since.isoformat(timespec="seconds") if since else "(all time)"
    lines = [
        "# OmniMedical — Log Review Report",
        "",
        f"- Generated: `{now}`",
        f"- Log dir: `{log_dir}`",
        f"- Window: `{since_str}` → `{stats.last_event_ts or 'n/a'}`",
        f"- Sessions: `{len(stats.sessions)}`",
        f"- Total events: **{stats.total_events}**",
        "",
        "## Distribution by category",
        "",
        "| Category | Events |",
        "|----------|-------:|",
    ]
    for cat, n in sorted(stats.by_category.items(), key=lambda x: -x[1]):
        lines.append(f"| {cat} | {n} |")

    lines += ["", "## Distribution by severity", "", "| Severity | Count |", "|----------|-------:|"]
    for sev, n in sorted(stats.by_severity.items(), key=lambda x: -x[1]):
        lines.append(f"| {sev} | {n} |")

    lines += ["", "## Top 15 events by frequency", "",
              "| Event | Count |", "|-------|------:|"]
    for ev, n in sorted(stats.by_event.items(), key=lambda x: -x[1])[:15]:
        lines.append(f"| `{ev}` | {n} |")

    if stats.errors_by_type:
        lines += ["", "## Errors by type", "", "| Type | Count |", "|------|------:|"]
        for t, n in sorted(stats.errors_by_type.items(), key=lambda x: -x[1]):
            lines.append(f"| `{t}` | {n} |")

        lines += ["", "## Top files with errors", "", "| File | Errors |", "|------|-------:|"]
        for f, n in sorted(stats.top_files_with_errors.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"| `{f}` | {n} |")

    # Slowest operations
    slow = [(ev, d) for ev, d in stats.durations_ms.items() if d]
    slow.sort(key=lambda x: -max(x[1]))
    if slow:
        lines += ["", "## Slowest operations (top 10 by max)", "",
                  "| Event | n | min ms | median ms | mean ms | max ms | stdev |",
                  "|-------|--:|-------:|----------:|--------:|-------:|------:|"]
        for ev, d in slow[:10]:
            lines.append(
                f"| `{ev}` | {len(d)} | {min(d):.1f} | {median(d):.1f} | "
                f"{mean(d):.1f} | {max(d):.1f} | {stdev(d) if len(d) > 1 else 0:.1f} |"
            )

    # Heuristic dev priorities
    lines += ["", "## Suggested development priorities (rule-based)", ""]
    priorities: list[str] = []

    err_total = sum(stats.by_severity.get(s, 0) for s in ("error", "critical"))
    if err_total > 0:
        top_err = max(stats.errors_by_type.items(), key=lambda x: x[1])
        priorities.append(
            f"1. **Fix the dominant error** `{top_err[0]}` "
            f"({top_err[1]} of {err_total} errors) — investigate the source file(s) "
            f"listed in 'Top files with errors'."
        )

    if slow:
        slowest_ev, slowest_d = slow[0]
        priorities.append(
            f"2. **Optimize the slowest operation** `{slowest_ev}` "
            f"(max {max(slowest_d):.1f} ms, mean {mean(slowest_d):.1f} ms across "
            f"{len(slowest_d)} calls) — likely a bottleneck."
        )

    # Check for retries / repeated identical events (heuristic)
    event_counts = Counter(stats.by_event)
    for ev, n in event_counts.most_common(5):
        if n > 100 and "error" in ev.lower():
            priorities.append(
                f"3. **Investigate repeated error event** `{ev}` "
                f"({n} occurrences) — may indicate a retry storm or a missing fallback."
            )

    if not stats.durations_ms and err_total == 0:
        priorities.append("1. **No issues detected** from logs — consider running the app "
                          "longer to gather more data, or instrument more code paths.")

    lines += priorities
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM review
# ---------------------------------------------------------------------------


def render_llm_prompt(stats_dict: dict[str, Any], sample_errors: list[dict[str, Any]]) -> str:
    """Build the prompt sent to the LLM."""
    # Compress: top-N everything to fit token budget
    def top(d: dict[str, Any], n: int = 10) -> dict[str, Any]:
        return dict(sorted(d.items(), key=lambda x: -x[1])[:n])

    compact = {
        "total_events": stats_dict["total_events"],
        "sessions": len(stats_dict["sessions"]),
        "window": {
            "first": stats_dict["first_event_ts"],
            "last": stats_dict["last_event_ts"],
        },
        "by_category": top(stats_dict["by_category"], 10),
        "by_severity": stats_dict["by_severity"],
        "top_events": top(stats_dict["by_event"], 15),
        "errors_by_type": top(stats_dict["errors_by_type"], 10),
        "errors_by_event": top(stats_dict["errors_by_event"], 10),
        "top_files_with_errors": top(stats_dict["top_files_with_errors"], 5),
        "durations_top_max": sorted(
            [
                {"event": ev, **d}
                for ev, d in stats_dict["durations_ms"].items()
            ],
            key=lambda x: -x["max_ms"],
        )[:5],
        "sample_error_records": sample_errors[:5],
    }

    return f"""You are a senior software architect reviewing the observability logs
of the OmniMedical suite (Python, OCR + scanner_fixer + Gradio/PySide6 apps).

Your task: identify the **top 3-5 development priorities** the team should
tackle next, based on the log statistics below.

For each priority, output:
- **Title** (short, actionable)
- **Why it matters** (cite the log numbers)
- **Suggested first step** (concrete: which file to look at, what to instrument, ...)

Be concise. Use Markdown. End with a 1-sentence "overall assessment" line.

Here is the aggregated log data as JSON:

```json
{json.dumps(compact, indent=2, ensure_ascii=False)}
```
"""


def collect_sample_errors(log_dir: Path, since: datetime | None, n: int = 5) -> list[dict[str, Any]]:
    """Collect a few representative error records for the LLM."""
    samples: list[dict[str, Any]] = []
    err_files = sorted(log_dir.glob("errors*.jsonl"))
    for path in err_files:
        for obj in _iter_jsonl(path, since=since):
            samples.append(obj)
            if len(samples) >= n:
                return samples
    return samples


def call_llm(prompt: str) -> str:
    """Call z-ai CLI (Node SDK wrapper) to get an LLM completion."""
    import tempfile

    out_path = tempfile.mktemp(suffix=".json")
    # z-ai chat CLI accepts --prompt inline. For very long prompts we still
    # pass inline (truncated to a safe length) since the CLI doesn't support
    # reading prompt from a file.
    inline_prompt = prompt[:30000]

    cmd = [
        "z-ai", "chat",
        "--prompt", inline_prompt,
        "--system", (
            "You are a senior software architect reviewing observability logs. "
            "Respond in Markdown. Be specific and concise."
        ),
        "-o", out_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except FileNotFoundError:
        return "(LLM review unavailable: z-ai CLI not installed)\n"

    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip() or "unknown error"
        return f"(LLM review failed: {msg})\n"

    out_file = Path(out_path)
    try:
        if out_file.exists():
            data = json.loads(out_file.read_text(encoding="utf-8"))
            # z-ai chat -o writes a JSON object with the message content
            return (
                data.get("content")
                or data.get("response")
                or data.get("choices", [{}])[0].get("message", {}).get("content", "")
                or json.dumps(data, indent=2, ensure_ascii=False)
            )
        return "(LLM review: no output file produced)\n"
    except json.JSONDecodeError as exc:
        return f"(LLM review: failed to parse output JSON: {exc})\n"
    finally:
        out_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# CSV timeline
# ---------------------------------------------------------------------------


def write_timeline_csv(log_dir: Path, since: datetime | None, out_csv: Path) -> int:
    """Write a per-event timeline CSV. Returns row count."""
    rows = 0
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "ts", "level", "category", "event", "logger",
            "duration_ms", "status", "session_id", "file", "message",
        ])
        for path in sorted(log_dir.glob("*.jsonl")):
            for obj in _iter_jsonl(path, since=since):
                w.writerow([
                    obj.get("ts", ""),
                    obj.get("level", ""),
                    obj.get("category", ""),
                    obj.get("event", ""),
                    obj.get("logger", ""),
                    obj.get("duration_ms", ""),
                    obj.get("status", ""),
                    obj.get("session_id", ""),
                    obj.get("file", ""),
                    obj.get("message", "")[:200],
                ])
                rows += 1
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _parse_since(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip().lower()
    now = datetime.now(timezone.utc)
    if s.endswith("h"):
        return now - timedelta(hours=int(s[:-1]))
    if s.endswith("d"):
        return now - timedelta(days=int(s[:-1]))
    if s.endswith("m"):
        return now - timedelta(minutes=int(s[:-1]))
    # Fallback: try ISO format
    return _parse_ts(s)


def main() -> int:
    p = argparse.ArgumentParser(description="Analyze OmniMedical logs.")
    p.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR),
                   help=f"Log directory (default: {DEFAULT_LOG_DIR})")
    p.add_argument("--since", default=None,
                   help="Only consider events since this time (e.g. 24h, 7d, 30m, or ISO ts)")
    p.add_argument("--out-dir", default="./log-reports",
                   help="Output directory for reports")
    p.add_argument("--csv", action="store_true",
                   help="Also write a per-event timeline CSV")
    p.add_argument("--llm", action="store_true",
                   help="Send the summary to z-ai LLM for prioritized review")
    args = p.parse_args()

    log_dir = Path(args.log_dir).expanduser()
    if not log_dir.exists():
        print(f"Log directory does not exist: {log_dir}", file=sys.stderr)
        print("Hint: run any instrumented OmniMedical script first to produce logs.",
              file=sys.stderr)
        return 2

    since = _parse_since(args.since)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Analyzing logs in {log_dir} (since={since})...")
    stats = collect_stats(log_dir, since=since)
    stats_dict = stats.to_dict()

    stats_path = out_dir / "stats.json"
    stats_path.write_text(json.dumps(stats_dict, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  → wrote {stats_path} ({stats.total_events} events, {len(stats.sessions)} sessions)")

    md = render_markdown(stats, since, log_dir)
    md_path = out_dir / "summary.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  → wrote {md_path}")

    if args.csv:
        csv_path = out_dir / "timeline.csv"
        n = write_timeline_csv(log_dir, since, csv_path)
        print(f"  → wrote {csv_path} ({n} rows)")

    if args.llm:
        print("Calling LLM for review...")
        sample_errors = collect_sample_errors(log_dir, since)
        prompt = render_llm_prompt(stats_dict, sample_errors)
        llm_md = call_llm(prompt)
        llm_path = out_dir / "llm_review.md"
        llm_path.write_text(llm_md, encoding="utf-8")
        print(f"  → wrote {llm_path}")
        # Also print to stdout for convenience
        print("\n" + "=" * 70 + "\nLLM REVIEW\n" + "=" * 70 + "\n")
        print(llm_md)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
