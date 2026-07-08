#!/usr/bin/env python3
"""
إدارة الوصفات الطبية — Arabic Medical Prescription Manager.

A CLI tool for adding, listing, searching, and exporting medical prescriptions.
All user-facing labels are in Arabic; code and comments are in English.

Usage:
    python scripts/add_prescription.py add
    python scripts/add_prescription.py list --limit 10 --filter doctor_name="د. أحمد"
    python scripts/add_prescription.py search "باراسيتامول"
    python scripts/add_prescription.py export --format csv --output prescriptions.csv
    python scripts/add_prescription.py export --id <uuid> --format json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Prescription:
    """A single medical prescription record."""

    id: str  # UUID
    patient_name: str  # Arabic name
    patient_id: str  # Medical ID
    doctor_name: str  # Arabic doctor name
    date: str  # ISO date (YYYY-MM-DD)
    diagnosis: str  # Arabic diagnosis
    medications: list[dict[str, str]]  # [{name, dose, frequency, duration}]
    notes: str  # Additional notes
    created_at: str  # ISO datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dictionary (JSON-serialisable)."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

# Resolve data directory relative to project root (two levels up from scripts/)
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_PRESCRIPTIONS_FILE = _DATA_DIR / "prescriptions.json"


def _ensure_data_dir() -> None:
    """Create the data directory if it does not exist."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_prescriptions() -> list[dict[str, Any]]:
    """Load all prescriptions from the JSON file.

    Returns an empty list if the file does not exist or is empty/invalid.
    """
    if not _PRESCRIPTIONS_FILE.exists():
        return []
    try:
        raw = _PRESCRIPTIONS_FILE.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        data: list[dict[str, Any]] = json.loads(raw)
        if not isinstance(data, list):
            print("⚠️ تنسيق الملف غير صحيح — يجب أن يكون مصفوفة JSON")
            return []
        return data
    except json.JSONDecodeError:
        print("⚠️ خطأ في قراءة ملف الوصفات: تنسيق JSON غير صالح")
        return []
    except OSError as exc:
        print(f"⚠️ خطأ في الوصول إلى ملف الوصفات: {exc}")
        return []


def _save_prescriptions(prescriptions: list[dict[str, Any]]) -> None:
    """Persist prescriptions to the JSON file."""
    _ensure_data_dir()
    _PRESCRIPTIONS_FILE.write_text(
        json.dumps(prescriptions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Tabulate helper (optional dependency)
# ---------------------------------------------------------------------------


def _try_tabulate(rows: list[list[str]], headers: list[str]) -> str | None:
    """Return a tabulate-formatted table string, or *None* if tabulate is unavailable."""
    try:
        from tabulate import tabulate  # type: ignore[import-untyped]

        return tabulate(rows, headers=headers, tablefmt="grid")
    except ImportError:
        return None


def _plain_table(rows: list[list[str]], headers: list[str]) -> str:
    """Fall-back plain-text table when tabulate is not installed."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(cell))

    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_line = "|" + "|".join(f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)) + "|"
    lines: list[str] = [sep, header_line, sep]
    for row in rows:
        line = "|" + "|".join(f" {row[i]:<{col_widths[i]}} " for i in range(len(row))) + "|"
        lines.append(line)
    lines.append(sep)
    return "\n".join(lines)


def _render_table(rows: list[list[str]], headers: list[str]) -> str:
    """Render *rows* into a table string, preferring tabulate."""
    result = _try_tabulate(rows, headers)
    if result is not None:
        return result
    return _plain_table(rows, headers)


# ---------------------------------------------------------------------------
# Interactive "add" command
# ---------------------------------------------------------------------------


def _prompt_required(label: str) -> str:
    """Prompt the user until a non-empty value is given."""
    while True:
        value = input(f"  {label}: ").strip()
        if value:
            return value
        print(f"  ⚠️ هذا الحقل مطلوب — {label}")


def _prompt_optional(label: str) -> str:
    """Prompt the user; return empty string if skipped."""
    return input(f"  {label} (اختياري): ").strip()


def cmd_add(_args: argparse.Namespace) -> None:
    """Interactively collect prescription data and save it."""
    print("\n📋 إضافة وصفة طبية جديدة")
    print("═" * 40)

    patient_name = _prompt_required("اسم المريض")
    patient_id = _prompt_required("الرقم الطبي")
    doctor_name = _prompt_required("اسم الطبيب")
    diagnosis = _prompt_required("التشخيص")

    # Date — default to today
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    date_str = input(f"  التاريخ (YYYY-MM-DD، الافتراضي: {today}): ").strip() or today

    # Medications loop
    medications: list[dict[str, str]] = []
    print("\n  💊 إضافة الأدوية (اترك اسم الدواء فارغاً للإنهاء)")
    med_index = 1
    while True:
        name = input(f"  {med_index}. اسم الدواء: ").strip()
        if not name:
            break
        dose = _prompt_required("   الجرعة")
        frequency = _prompt_required("   التكرار")
        duration = _prompt_required("   المدة")
        medications.append({"name": name, "dose": dose, "frequency": frequency, "duration": duration})
        med_index += 1

    if not medications:
        print("  ⚠️ يجب إضافة دواء واحد على الأقل")
        sys.exit(1)

    notes = _prompt_optional("ملاحظات إضافية")

    rx = Prescription(
        id=str(uuid4()),
        patient_name=patient_name,
        patient_id=patient_id,
        doctor_name=doctor_name,
        date=date_str,
        diagnosis=diagnosis,
        medications=medications,
        notes=notes,
        created_at=datetime.now(UTC).isoformat(),
    )

    existing = _load_prescriptions()
    existing.append(rx.to_dict())
    _save_prescriptions(existing)

    print(f"\n✅ تم حفظ الوصفة بنجاح — المعرف: {rx.id}")


# ---------------------------------------------------------------------------
# "list" command
# ---------------------------------------------------------------------------


def _matches_filter(p: dict[str, Any], filter_str: str) -> bool:
    """Return *True* if *p* matches a ``key=value`` filter string."""
    if "=" not in filter_str:
        return False
    key, value = filter_str.split("=", 1)
    actual = str(p.get(key.strip(), ""))
    return value.strip().lower() in actual.lower()


def cmd_list(args: argparse.Namespace) -> None:
    """List prescriptions, optionally filtered and limited."""
    prescriptions = _load_prescriptions()
    if not prescriptions:
        print("📭 لا توجد وصفات مسجلة")
        return

    # Apply --filter
    if args.filter:
        prescriptions = [p for p in prescriptions if _matches_filter(p, args.filter)]

    if not prescriptions:
        print("📭 لا توجد وصفات تطابق البحث")
        return

    # Apply --limit
    limit = args.limit or len(prescriptions)
    prescriptions = prescriptions[:limit]

    headers = [
        "المعرف",
        "اسم المريض",
        "الرقم الطبي",
        "اسم الطبيب",
        "التاريخ",
        "التشخيص",
        "عدد الأدوية",
    ]
    rows: list[list[str]] = []
    for p in prescriptions:
        rows.append([
            p.get("id", "")[:8],
            p.get("patient_name", ""),
            p.get("patient_id", ""),
            p.get("doctor_name", ""),
            p.get("date", ""),
            p.get("diagnosis", ""),
            str(len(p.get("medications", []))),
        ])

    print(f"\n📄 الوصفات المسجلة ({len(prescriptions)} نتيجة)\n")
    print(_render_table(rows, headers))


# ---------------------------------------------------------------------------
# "search" command
# ---------------------------------------------------------------------------


def cmd_search(args: argparse.Namespace) -> None:
    """Search prescriptions by medication name (partial, case-insensitive)."""
    query = args.query.strip().lower()
    if not query:
        print("⚠️ يرجى إدخال اسم الدواء للبحث")
        sys.exit(1)

    prescriptions = _load_prescriptions()
    matches: list[dict[str, Any]] = []
    for p in prescriptions:
        for med in p.get("medications", []):
            if query in med.get("name", "").lower():
                matches.append(p)
                break  # avoid duplicate prescription entries

    if not matches:
        print(f"📭 لم يتم العثور على وصفات تحتوي على: {args.query}")
        return

    print(f"\n🔍 نتائج البحث عن «{args.query}» — {len(matches)} وصفة\n")
    for p in matches:
        print(f"  المعرف:      {p.get('id', '')}")
        print(f"  اسم المريض:  {p.get('patient_name', '')}")
        print(f"  الرقم الطبي: {p.get('patient_id', '')}")
        print(f"  اسم الطبيب:  {p.get('doctor_name', '')}")
        print(f"  التاريخ:     {p.get('date', '')}")
        print(f"  التشخيص:     {p.get('diagnosis', '')}")
        print("  الأدوية:")
        for med in p.get("medications", []):
            print(f"    • {med.get('name', '')} — {med.get('dose', '')} — {med.get('frequency', '')} — {med.get('duration', '')}")
        if p.get("notes"):
            print(f"  ملاحظات:     {p['notes']}")
        print()


# ---------------------------------------------------------------------------
# "export" command
# ---------------------------------------------------------------------------


def _export_json(prescriptions: list[dict[str, Any]], output: Path | None) -> None:
    """Export prescriptions as JSON."""
    content = json.dumps(prescriptions, indent=2, ensure_ascii=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"✅ تم التصدير إلى: {output}")
    else:
        print(content)


def _export_csv(prescriptions: list[dict[str, Any]], output: Path | None) -> None:
    """Export prescriptions as CSV (one row per medication)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "المعرف",
        "اسم المريض",
        "الرقم الطبي",
        "اسم الطبيب",
        "التاريخ",
        "التشخيص",
        "اسم الدواء",
        "الجرعة",
        "التكرار",
        "المدة",
        "ملاحظات",
        "تاريخ الإنشاء",
    ])
    for p in prescriptions:
        for med in p.get("medications", []):
            writer.writerow([
                p.get("id", ""),
                p.get("patient_name", ""),
                p.get("patient_id", ""),
                p.get("doctor_name", ""),
                p.get("date", ""),
                p.get("diagnosis", ""),
                med.get("name", ""),
                med.get("dose", ""),
                med.get("frequency", ""),
                med.get("duration", ""),
                p.get("notes", ""),
                p.get("created_at", ""),
            ])

    content = buf.getvalue()
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"✅ تم التصدير إلى: {output}")
    else:
        print(content, end="")


def cmd_export(args: argparse.Namespace) -> None:
    """Export prescriptions to JSON or CSV."""
    all_prescriptions = _load_prescriptions()

    # Select which prescriptions to export
    if args.all or args.id is None:
        to_export = all_prescriptions
    else:
        to_export = [p for p in all_prescriptions if p.get("id") == args.id]
        if not to_export:
            print(f"⚠️ لم يتم العثور على وصفة بالمعرف: {args.id}")
            sys.exit(1)

    if not to_export:
        print("📭 لا توجد وصفات للتصدير")
        return

    fmt = (args.format or "json").lower()
    output: Path | None = Path(args.output) if args.output else None

    if fmt == "csv":
        _export_csv(to_export, output)
    else:
        _export_json(to_export, output)


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="add_prescription",
        description="إدارة الوصفات الطبية — Medical Prescription Manager",
    )
    sub = parser.add_subparsers(dest="command")

    # -- add --
    sub.add_parser("add", help="إضافة وصفة طبية جديدة — Add a new prescription")

    # -- list --
    list_parser = sub.add_parser("list", help="عرض الوصفات المسجلة — List prescriptions")
    list_parser.add_argument("--limit", type=int, default=None, help="الحد الأقصى للنتائج — Max results")
    list_parser.add_argument("--filter", default=None, help="تصفية (مثال: doctor_name=د. أحمد) — Filter key=value")

    # -- search --
    search_parser = sub.add_parser("search", help="البحث في الوصفات — Search prescriptions")
    search_parser.add_argument("query", help="اسم الدواء للبحث — Medication name to search")

    # -- export --
    export_parser = sub.add_parser("export", help="تصدير الوصفات — Export prescriptions")
    export_parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="تنسيق التصدير — Export format (default: json)",
    )
    export_parser.add_argument("--output", default=None, help="مسار الملف — Output file path")
    export_group = export_parser.add_mutually_exclusive_group()
    export_group.add_argument("--all", action="store_true", default=True, help="تصدير الكل — Export all (default)")
    export_group.add_argument("--id", default=None, help="معرف وصفة محددة — Specific prescription ID")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "export":
        cmd_export(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
