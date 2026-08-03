# Alarm Log Data Contract

## Input CSV

| Column | Rule | Example |
| --- | --- | --- |
| `timestamp` | `YYYY-MM-DD HH:MM:SS`, interpreted as local plant time | `2026-07-20 08:11:14` |
| `equipment` | Non-empty equipment identifier | `Pump-02` |
| `alarm_type` | Non-empty alarm name or code | `Pressure High` |
| `severity` | `critical`, `warning`, or `info`, case-insensitive | `warning` |

Header names are case-insensitive and surrounding whitespace is ignored. Extra columns are accepted and ignored. Source rows are never modified.

## Cleaning and Validation

- Trim surrounding whitespace and collapse internal whitespace.
- Normalize severity to lowercase.
- Reject a row with a missing value, invalid timestamp, invalid severity, or surplus unheaded CSV fields.
- Remove exact duplicates after normalization.
- Sort valid unique records by timestamp, equipment, alarm type, and severity.

`data_quality.input_rows` equals accepted unique alarms plus invalid rows plus removed duplicates.

## Incident Correlation

Use a sliding time-gap rule independently for each equipment:

1. Start an incident with the equipment's first alarm.
2. Add the next alarm for that equipment when it occurs within the configured number of minutes of the previous alarm.
3. Otherwise start a new incident.
4. Sort all incidents by start time and assign deterministic IDs such as `INC-20260720-0001`.

The default correlation window is 15 minutes. This is temporal correlation, not proof that one alarm caused another.

## JSON Report

| Field | Contents |
| --- | --- |
| `report_metadata` | Generation time, source file, schema version, and incident window |
| `data_quality` | Input, accepted, rejected, duplicate, normalization, and issue counts |
| `summary` | Alarm and incident totals plus severity and equipment counts |
| `incidents` | Incident identity, timing, equipment, highest severity, alarm types, and alarms |
| `validation_issues` | Row number, issue code, message, and raw required fields |

Command exit codes:

- `0`: report created; recoverable row issues may exist in non-strict mode
- `1`: fatal file, encoding, CSV, header, or output error
- `2`: report created but row issues were found in `--strict` mode
