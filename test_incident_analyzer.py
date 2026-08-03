import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPTS_DIR = (
    Path(__file__).parent
    / ".agents"
    / "skills"
    / "alarm-log-analyzer"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS_DIR))

from analyze_alarm_log import (  # noqa: E402
    AlarmLogError,
    analyze_alarm_log,
    group_incidents,
    load_and_clean_alarms,
    main,
)


def write_csv(directory, content, filename="alarms.csv"):
    csv_path = Path(directory) / filename
    csv_path.write_text(content, encoding="utf-8")
    return csv_path


def alarm(
    timestamp,
    equipment="Pump-01",
    alarm_type="Pressure High",
    severity="warning",
):
    return {
        "timestamp": timestamp,
        "equipment": equipment,
        "alarm_type": alarm_type,
        "severity": severity,
    }


class LoadAndCleanAlarmsTests(unittest.TestCase):
    def test_normalizes_rejects_and_deduplicates_rows(self):
        content = (
            " Timestamp , Equipment , Alarm_Type , Severity \n"
            " 2026-07-20 08:00:00 , Pump-01 , Pressure   High , WARNING \n"
            "2026-07-20 08:00:00,Pump-01,Pressure High,warning\n"
            "not-a-time,Pump-02,Position Error,critical\n"
            "2026-07-20 09:00:00,Pump-03,Temperature High,urgent\n"
        )
        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)
            alarms, issues, quality = load_and_clean_alarms(csv_path)

        self.assertEqual(alarms, [alarm("2026-07-20 08:00:00")])
        self.assertEqual(quality["input_rows"], 4)
        self.assertEqual(quality["valid_rows"], 1)
        self.assertEqual(quality["invalid_rows"], 2)
        self.assertEqual(quality["duplicate_rows_removed"], 1)
        self.assertGreaterEqual(quality["normalized_values"], 4)
        self.assertEqual(
            {issue["code"] for issue in issues},
            {"duplicate_record", "invalid_timestamp", "invalid_severity"},
        )

    def test_rejects_missing_required_header(self):
        content = "timestamp,equipment,alarm_type\n"
        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)
            with self.assertRaisesRegex(AlarmLogError, "severity"):
                load_and_clean_alarms(csv_path)

    def test_rejects_surplus_unheaded_fields(self):
        content = (
            "timestamp,equipment,alarm_type,severity\n"
            "2026-07-20 08:00:00,Pump-01,Pressure High,warning,unexpected\n"
        )
        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)
            alarms, issues, quality = load_and_clean_alarms(csv_path)

        self.assertEqual(alarms, [])
        self.assertEqual(quality["invalid_rows"], 1)
        self.assertEqual(issues[0]["code"], "unexpected_fields")


class GroupIncidentsTests(unittest.TestCase):
    def test_groups_by_equipment_with_sliding_window(self):
        alarms = [
            alarm("2026-07-20 08:00:00"),
            alarm(
                "2026-07-20 08:10:00",
                alarm_type="Pressure Low",
                severity="critical",
            ),
            alarm("2026-07-20 08:25:00", alarm_type="Motor Hot"),
            alarm(
                "2026-07-20 08:05:00",
                equipment="Valve-01",
                alarm_type="Position Error",
            ),
            alarm("2026-07-20 08:40:01"),
        ]

        incidents = group_incidents(alarms, incident_window_minutes=15)

        self.assertEqual(len(incidents), 3)
        pump_incidents = [
            item for item in incidents if item["equipment"] == "Pump-01"
        ]
        self.assertEqual([item["alarm_count"] for item in pump_incidents], [3, 1])
        self.assertEqual(pump_incidents[0]["duration_seconds"], 1500)
        self.assertEqual(pump_incidents[0]["highest_severity"], "critical")
        self.assertEqual(pump_incidents[0]["incident_id"], "INC-20260720-0001")

    def test_zero_window_groups_only_equal_timestamps(self):
        alarms = [
            alarm("2026-07-20 08:00:00"),
            alarm("2026-07-20 08:00:00", alarm_type="Pressure Low"),
            alarm("2026-07-20 08:00:01", alarm_type="Motor Hot"),
        ]

        incidents = group_incidents(alarms, incident_window_minutes=0)

        self.assertEqual([item["alarm_count"] for item in incidents], [2, 1])


class ReportAndCliTests(unittest.TestCase):
    def test_builds_structured_report(self):
        content = (
            "timestamp,equipment,alarm_type,severity\n"
            "2026-07-20 08:00:00,Pump-01,Pressure High,warning\n"
            "2026-07-20 08:10:00,Pump-01,Pressure High,critical\n"
            "2026-07-20 09:00:00,Valve-01,Position Error,info\n"
        )
        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)
            report = analyze_alarm_log(
                csv_path,
                incident_window_minutes=15,
                generated_at="2026-08-03T00:00:00Z",
            )

        self.assertEqual(report["report_metadata"]["schema_version"], "1.0")
        self.assertEqual(report["summary"]["total_alarms"], 3)
        self.assertEqual(report["summary"]["total_incidents"], 2)
        self.assertEqual(report["summary"]["affected_equipment"], 2)
        self.assertEqual(
            report["summary"]["alarm_severity_counts"],
            {"critical": 1, "info": 1, "warning": 1},
        )

    def test_strict_mode_writes_report_and_returns_two_for_issues(self):
        content = (
            "timestamp,equipment,alarm_type,severity\n"
            "2026-07-20 08:00:00,Pump-01,Pressure High,warning\n"
            "bad-time,Pump-02,Position Error,critical\n"
        )
        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)
            output_path = Path(directory) / "report.json"
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                result = main(
                    [str(csv_path), "--output", str(output_path), "--strict"]
                )
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result, 2)
        self.assertEqual(report["data_quality"]["invalid_rows"], 1)
        self.assertEqual(report["summary"]["total_incidents"], 1)

    def test_non_strict_mode_returns_zero_with_recoverable_issues(self):
        content = (
            "timestamp,equipment,alarm_type,severity\n"
            "bad-time,Pump-02,Position Error,critical\n"
        )
        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)
            output_path = Path(directory) / "report.json"
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                result = main([str(csv_path), "--output", str(output_path)])

        self.assertEqual(result, 0)

    def test_returns_one_when_output_directory_is_missing(self):
        content = (
            "timestamp,equipment,alarm_type,severity\n"
            "2026-07-20 08:00:00,Pump-01,Pressure High,warning\n"
        )
        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)
            output_path = Path(directory) / "missing" / "report.json"
            stderr = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                result = main([str(csv_path), "--output", str(output_path)])

        self.assertEqual(result, 1)
        self.assertIn("could not write report", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
