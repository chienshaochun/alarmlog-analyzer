---
name: alarm-log-analyzer
description: Validate, clean, and analyze industrial equipment Alarm Log CSV files; group related alarms into incidents; and produce structured JSON incident reports with data-quality findings and operational summaries. Use when Codex needs to inspect alarm histories, validate the required timestamp/equipment/alarm_type/severity schema, normalize or deduplicate records, tune an incident time window, explain rejected rows, or generate an incident report from an industrial alarm log.
---

# Alarm Log Analyzer

Turn a raw industrial Alarm Log into a reproducible incident report without modifying the source file. Use the bundled Python script for deterministic validation, cleaning, grouping, and JSON generation.

## Run the Workflow

1. Confirm that the input is a CSV file. Read [references/data-contract.md](references/data-contract.md) when mapping columns, changing the incident window, or interpreting output fields.
2. Run the analyzer with a separate output path:

   ```powershell
   python scripts/analyze_alarm_log.py <input.csv> --output <incident-report.json>
   ```

3. Use `--incident-window-minutes <minutes>` when the user supplies a site-specific correlation window. Keep the default of 15 minutes otherwise.
4. Use `--strict` when invalid data must make the command return a nonzero status. The script still writes the report so the rejected rows remain auditable.
5. Review `data_quality` and `validation_issues` before drawing conclusions from `summary` or `incidents`.
6. Report the input row count, accepted alarm count, rejected row count, duplicate count, incident count, affected equipment, and output path. Explain material validation issues and any non-default incident window.

## Apply the Data Rules

- Require `timestamp`, `equipment`, `alarm_type`, and `severity`; accept additional columns but do not copy them into the report.
- Accept UTF-8 and UTF-8 with BOM. Normalize header case and surrounding whitespace.
- Parse timestamps as `YYYY-MM-DD HH:MM:SS`.
- Collapse repeated whitespace in equipment and alarm type values.
- Normalize severity to lowercase and accept only `critical`, `warning`, or `info`.
- Reject invalid rows individually. Do not silently invent missing values.
- Remove exact duplicates after normalization and retain an audit issue for each removed row.
- Sort accepted alarms chronologically before grouping.

## Interpret Incidents

Group alarms by equipment. Continue an equipment's current incident when the next alarm occurs no more than the configured window after that equipment's previous alarm. Start a new incident when the gap is larger. Treat a gap exactly equal to the window as part of the same incident.

Assign each incident its highest alarm severity using `critical > warning > info`. Keep the original normalized alarms in every incident so conclusions remain traceable. Do not claim causal relationships; the grouping is temporal correlation only.

## Handle Failures

- Treat an unreadable file, invalid encoding, malformed CSV, or missing required header as a fatal input error.
- Treat row-level validation problems as recoverable unless `--strict` is requested.
- If no valid alarms remain, return an empty incident list and make the quality warning explicit.
- Never overwrite the input CSV. Ask before replacing an existing report when preservation matters to the user.

