#!/usr/bin/env python3
"""Validate an industrial Alarm Log CSV and build a JSON incident report."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


REQUIRED_COLUMNS = ("timestamp", "equipment", "alarm_type", "severity")
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
VALID_SEVERITIES = ("critical", "warning", "info")
SEVERITY_RANK = {"info": 1, "warning": 2, "critical": 3}
DEFAULT_INCIDENT_WINDOW_MINUTES = 15
SCHEMA_VERSION = "1.0"


class AlarmLogError(ValueError):
    """Raised when the log cannot be processed as an Alarm Log."""


def normalize_text(value: str) -> str:
    """Trim a text value and collapse all runs of whitespace."""
    return " ".join(value.split())


def normalize_headers(fieldnames: list[str | None] | None) -> list[str]:
    """Normalize CSV headers and reject missing or duplicate header names."""
    if fieldnames is None:
        raise AlarmLogError("CSV is missing a header row")

    normalized = [
        normalize_text(name).lower() if name is not None else ""
        for name in fieldnames
    ]
    if any(not name for name in normalized):
        raise AlarmLogError("CSV contains a blank header name")
    if len(normalized) != len(set(normalized)):
        raise AlarmLogError("CSV contains duplicate header names after normalization")

    missing = sorted(set(REQUIRED_COLUMNS) - set(normalized))
    if missing:
        raise AlarmLogError(f"CSV is missing required columns: {', '.join(missing)}")
    return normalized


def make_issue(
    line_number: int,
    code: str,
    message: str,
    row: dict[str | None, Any],
) -> dict[str, Any]:
    """Build a JSON-safe audit record for a rejected or duplicate row."""
    return {
        "line": line_number,
        "code": code,
        "message": message,
        "raw": {column: row.get(column) for column in REQUIRED_COLUMNS},
    }


def clean_row(
    row: dict[str | None, Any],
    line_number: int,
) -> tuple[dict[str, str] | None, list[dict[str, Any]], int]:
    """Validate and normalize one DictReader row."""
    issues: list[dict[str, Any]] = []
    cleaned: dict[str, str] = {}
    normalized_values = 0

    surplus = row.get(None)
    if surplus and any(
        normalize_text(str(value)) for value in surplus if value is not None
    ):
        issues.append(
            make_issue(
                line_number,
                "unexpected_fields",
                "row has more values than the header defines",
                row,
            )
        )

    for column in REQUIRED_COLUMNS:
        raw_value = row.get(column)
        if raw_value is None or not normalize_text(str(raw_value)):
            issues.append(
                make_issue(
                    line_number,
                    "missing_value",
                    f"{column} is required",
                    row,
                )
            )
            continue

        value = normalize_text(str(raw_value))
        if column == "severity":
            value = value.lower()
        if value != raw_value:
            normalized_values += 1
        cleaned[column] = value

    if "timestamp" in cleaned:
        try:
            parsed = datetime.strptime(cleaned["timestamp"], TIMESTAMP_FORMAT)
            cleaned["timestamp"] = parsed.strftime(TIMESTAMP_FORMAT)
        except ValueError:
            issues.append(
                make_issue(
                    line_number,
                    "invalid_timestamp",
                    f"timestamp must match {TIMESTAMP_FORMAT}",
                    row,
                )
            )

    if "severity" in cleaned and cleaned["severity"] not in VALID_SEVERITIES:
        issues.append(
            make_issue(
                line_number,
                "invalid_severity",
                f"severity must be one of: {', '.join(VALID_SEVERITIES)}",
                row,
            )
        )

    if issues:
        return None, issues, normalized_values
    return cleaned, [], normalized_values


def load_and_clean_alarms(
    csv_path: str | Path,
) -> tuple[list[dict[str, str]], list[dict[str, Any]], dict[str, int]]:
    """Load a CSV, skip invalid rows, remove duplicates, and sort the result."""
    alarms: list[dict[str, str]] = []
    issues: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    input_rows = invalid_rows = duplicate_rows = normalized_values = 0

    with Path(csv_path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        reader.fieldnames = normalize_headers(reader.fieldnames)

        for line_number, row in enumerate(reader, start=2):
            input_rows += 1
            cleaned, row_issues, changed_values = clean_row(row, line_number)
            normalized_values += changed_values

            if cleaned is None:
                invalid_rows += 1
                issues.extend(row_issues)
                continue

            fingerprint = tuple(cleaned[column] for column in REQUIRED_COLUMNS)
            if fingerprint in seen:
                duplicate_rows += 1
                issues.append(
                    make_issue(
                        line_number,
                        "duplicate_record",
                        "duplicate removed after normalization",
                        row,
                    )
                )
                continue

            seen.add(fingerprint)
            alarms.append(cleaned)

    alarms.sort(
        key=lambda alarm: (
            alarm["timestamp"],
            alarm["equipment"],
            alarm["alarm_type"],
            alarm["severity"],
        )
    )
    quality = {
        "input_rows": input_rows,
        "valid_rows": len(alarms),
        "invalid_rows": invalid_rows,
        "duplicate_rows_removed": duplicate_rows,
        "normalized_values": normalized_values,
        "issue_count": len(issues),
    }
    return alarms, issues, quality


def highest_severity(alarms: Iterable[dict[str, str]]) -> str:
    """Return the most severe value in a non-empty alarm collection."""
    return max(
        (alarm["severity"] for alarm in alarms),
        key=SEVERITY_RANK.__getitem__,
    )


def group_incidents(
    alarms: list[dict[str, str]],
    incident_window_minutes: int = DEFAULT_INCIDENT_WINDOW_MINUTES,
) -> list[dict[str, Any]]:
    """Group alarms using an equipment-local sliding time gap."""
    if incident_window_minutes < 0:
        raise ValueError("incident_window_minutes must be at least 0")

    window = timedelta(minutes=incident_window_minutes)
    active: dict[str, dict[str, Any]] = {}
    grouped: list[dict[str, Any]] = []

    for alarm in sorted(
        alarms,
        key=lambda item: (
            item["timestamp"],
            item["equipment"],
            item["alarm_type"],
            item["severity"],
        ),
    ):
        alarm_time = datetime.strptime(alarm["timestamp"], TIMESTAMP_FORMAT)
        equipment = alarm["equipment"]
        current = active.get(equipment)

        if current is None or alarm_time - current["last_time"] > window:
            current = {
                "equipment": equipment,
                "start_time": alarm_time,
                "last_time": alarm_time,
                "alarms": [],
            }
            active[equipment] = current
            grouped.append(current)

        current["alarms"].append(alarm)
        current["last_time"] = alarm_time

    grouped.sort(key=lambda item: (item["start_time"], item["equipment"]))
    incidents: list[dict[str, Any]] = []
    for index, group in enumerate(grouped, start=1):
        start_time = group["start_time"]
        end_time = group["last_time"]
        incident_alarms = group["alarms"]
        incidents.append(
            {
                "incident_id": f"INC-{start_time:%Y%m%d}-{index:04d}",
                "equipment": group["equipment"],
                "start_time": start_time.strftime(TIMESTAMP_FORMAT),
                "end_time": end_time.strftime(TIMESTAMP_FORMAT),
                "duration_seconds": int((end_time - start_time).total_seconds()),
                "alarm_count": len(incident_alarms),
                "highest_severity": highest_severity(incident_alarms),
                "alarm_types": sorted(
                    {alarm["alarm_type"] for alarm in incident_alarms}
                ),
                "alarms": incident_alarms,
            }
        )
    return incidents


def sorted_counts(values: Iterable[str]) -> dict[str, int]:
    """Return deterministic alphabetical counts."""
    return dict(sorted(Counter(values).items()))


def build_report(
    csv_path: str | Path,
    alarms: list[dict[str, str]],
    incidents: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    quality: dict[str, int],
    incident_window_minutes: int,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the stable, JSON-serializable report contract."""
    if generated_at is None:
        generated_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    equipment_counts = sorted_counts(alarm["equipment"] for alarm in alarms)
    return {
        "report_metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "source_file": str(Path(csv_path)),
            "incident_window_minutes": incident_window_minutes,
        },
        "data_quality": quality,
        "summary": {
            "total_alarms": len(alarms),
            "total_incidents": len(incidents),
            "affected_equipment": len(equipment_counts),
            "alarm_severity_counts": sorted_counts(
                alarm["severity"] for alarm in alarms
            ),
            "incident_severity_counts": sorted_counts(
                incident["highest_severity"] for incident in incidents
            ),
            "equipment_alarm_counts": equipment_counts,
        },
        "incidents": incidents,
        "validation_issues": issues,
    }


def analyze_alarm_log(
    csv_path: str | Path,
    incident_window_minutes: int = DEFAULT_INCIDENT_WINDOW_MINUTES,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Execute the complete Alarm Log analysis pipeline."""
    alarms, issues, quality = load_and_clean_alarms(csv_path)
    incidents = group_incidents(alarms, incident_window_minutes)
    return build_report(
        csv_path,
        alarms,
        incidents,
        issues,
        quality,
        incident_window_minutes,
        generated_at,
    )


def save_json(report: dict[str, Any], output_path: str | Path) -> None:
    """Write a UTF-8 JSON report with a final newline."""
    with Path(output_path).open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate an Alarm Log and create a structured incident report."
    )
    parser.add_argument("csv_path", type=Path, help="input Alarm Log CSV")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("incident_report.json"),
        help="output JSON path (default: incident_report.json)",
    )
    parser.add_argument(
        "--incident-window-minutes",
        type=int,
        default=DEFAULT_INCIDENT_WINDOW_MINUTES,
        help="maximum gap between alarms in one incident (default: 15)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return status 2 when invalid or duplicate rows are found",
    )
    args = parser.parse_args(argv)
    if args.incident_window_minutes < 0:
        parser.error("--incident-window-minutes must be at least 0")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = analyze_alarm_log(args.csv_path, args.incident_window_minutes)
    except FileNotFoundError:
        print(f"Error: CSV file not found: {args.csv_path}", file=sys.stderr)
        return 1
    except PermissionError as error:
        print(
            f"Error: permission denied: {error.filename or args.csv_path}",
            file=sys.stderr,
        )
        return 1
    except UnicodeDecodeError:
        print("Error: CSV must use UTF-8 encoding", file=sys.stderr)
        return 1
    except (csv.Error, AlarmLogError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    try:
        save_json(report, args.output)
    except OSError as error:
        print(f"Error: could not write report {args.output}: {error}", file=sys.stderr)
        return 1

    quality = report["data_quality"]
    summary = report["summary"]
    print(
        "Created incident report: "
        f"{summary['total_alarms']} alarms, "
        f"{summary['total_incidents']} incidents, "
        f"{quality['invalid_rows']} invalid rows, "
        f"{quality['duplicate_rows_removed']} duplicates"
    )
    print(f"Output: {args.output}")

    if args.strict and quality["issue_count"]:
        print(
            "Strict validation failed; inspect validation_issues in the report.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
