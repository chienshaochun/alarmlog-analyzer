import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from alarm import (
    AlarmDataError,
    DEFAULT_CSV_PATH,
    build_report_data,
    calculate_percentage,
    count_alarms_by_alarm_type,
    count_alarms_by_equipment,
    count_alarms_by_field,
    count_alarms_by_hour,
    count_alarms_by_severity,
    filter_alarms_by_severity,
    find_busiest_hour,
    find_most_common,
    get_hour,
    load_alarms,
    main,
    parse_args,
    save_report_json,
    sort_counts_descending,
)


def make_sample_alarms():
    """建立每個測試都能獨立使用的新告警清單。"""
    return [
        {
            "timestamp": "2026-07-20 08:10:00",
            "equipment": "Pump-01",
            "alarm_type": "Pressure High",
            "severity": "warning",
        },
        {
            "timestamp": "2026-07-20 08:20:00",
            "equipment": "Pump-01",
            "alarm_type": "Pressure High",
            "severity": "critical",
        },
        {
            "timestamp": "2026-07-20 09:30:00",
            "equipment": "Valve-01",
            "alarm_type": "Position Error",
            "severity": "warning",
        },
    ]


def write_csv(directory, content, filename="alarms.csv"):
    """在暫存資料夾建立測試用 CSV，並回傳檔案路徑。"""
    csv_path = Path(directory) / filename
    csv_path.write_text(content, encoding="utf-8")
    return csv_path


class CalculatePercentageTests(unittest.TestCase):
    """測試 calculate_percentage() 的正常與邊界行為。"""

    def test_calculates_percentage(self):
        result = calculate_percentage(50, 200)

        self.assertEqual(result, 25.0)

    def test_returns_zero_when_total_is_zero(self):
        result = calculate_percentage(5, 0)

        self.assertEqual(result, 0.0)


class CountAlarmsByFieldTests(unittest.TestCase):
    """測試通用欄位統計函式。"""

    def test_counts_the_requested_field(self):
        alarms = [
            {"equipment": "Pump-01", "severity": "warning"},
            {"equipment": "Pump-02", "severity": "critical"},
            {"equipment": "Pump-01", "severity": "critical"},
        ]

        equipment_counts = count_alarms_by_field(alarms, "equipment")
        severity_counts = count_alarms_by_field(alarms, "severity")

        self.assertEqual(
            equipment_counts,
            {"Pump-01": 2, "Pump-02": 1},
        )
        self.assertEqual(
            severity_counts,
            {"warning": 1, "critical": 2},
        )

    def test_returns_empty_dict_for_empty_alarms(self):
        result = count_alarms_by_field([], "equipment")

        self.assertEqual(result, {})


class CountAlarmWrappersTests(unittest.TestCase):
    """測試三個指定欄位的統計包裝函式。"""

    def test_counts_each_supported_field(self):
        alarms = make_sample_alarms()

        self.assertEqual(
            count_alarms_by_severity(alarms),
            {"warning": 2, "critical": 1},
        )
        self.assertEqual(
            count_alarms_by_equipment(alarms),
            {"Pump-01": 2, "Valve-01": 1},
        )
        self.assertEqual(
            count_alarms_by_alarm_type(alarms),
            {"Pressure High": 2, "Position Error": 1},
        )


class SortCountsDescendingTests(unittest.TestCase):
    """測試統計結果的主要與次要排序規則。"""

    def test_sorts_by_count_then_name(self):
        counts = {
            "Pump-02": 20,
            "Tank-01": 10,
            "Pump-01": 20,
        }

        result = sort_counts_descending(counts)

        self.assertEqual(
            result,
            [
                ("Pump-01", 20),
                ("Pump-02", 20),
                ("Tank-01", 10),
            ],
        )

    def test_returns_empty_list_for_empty_counts(self):
        result = sort_counts_descending({})

        self.assertEqual(result, [])


class FindMostCommonTests(unittest.TestCase):
    """測試找出最高統計項目的規則。"""

    def test_returns_item_with_highest_count(self):
        counts = {
            "Pump-01": 3,
            "Pump-02": 5,
            "Tank-01": 2,
        }

        result = find_most_common(counts)

        self.assertEqual(result, ("Pump-02", 5))

    def test_uses_name_order_when_highest_count_is_tied(self):
        counts = {
            "Pump-02": 5,
            "Pump-01": 5,
        }

        result = find_most_common(counts)

        self.assertEqual(result, ("Pump-01", 5))

    def test_returns_default_value_for_empty_counts(self):
        result = find_most_common({})

        self.assertEqual(result, (None, 0))


class HourStatisticsTests(unittest.TestCase):
    """測試時間轉換、每小時統計與最高時段。"""

    def test_get_hour_returns_two_digit_hour(self):
        result = get_hour("2026-07-20 08:10:00")

        self.assertEqual(result, "08")

    def test_counts_alarms_by_hour(self):
        result = count_alarms_by_hour(make_sample_alarms())

        self.assertEqual(result, {"08": 2, "09": 1})

    def test_finds_busiest_hour(self):
        result = find_busiest_hour({"08": 2, "09": 1})

        self.assertEqual(result, ("08", 2))


class FilterAlarmsBySeverityTests(unittest.TestCase):
    """測試嚴重程度篩選及無符合資料的情況。"""

    def test_returns_only_matching_alarms(self):
        result = filter_alarms_by_severity(
            make_sample_alarms(),
            "warning",
        )

        self.assertEqual(len(result), 2)
        self.assertTrue(
            all(alarm["severity"] == "warning" for alarm in result)
        )

    def test_returns_empty_list_when_nothing_matches(self):
        result = filter_alarms_by_severity(make_sample_alarms(), "info")

        self.assertEqual(result, [])


class LoadAlarmsTests(unittest.TestCase):
    """使用暫存 CSV 測試資料載入與驗證。"""

    def test_loads_valid_csv_and_strips_outer_whitespace(self):
        content = (
            "timestamp,equipment,alarm_type,severity\n"
            " 2026-07-20 08:10:00 , Pump-01 , Pressure High , warning \n"
        )

        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)

            result = load_alarms(csv_path)

        self.assertEqual(
            result,
            [
                {
                    "timestamp": "2026-07-20 08:10:00",
                    "equipment": "Pump-01",
                    "alarm_type": "Pressure High",
                    "severity": "warning",
                }
            ],
        )

    def test_rejects_missing_required_column(self):
        content = (
            "timestamp,equipment,alarm_type\n"
            "2026-07-20 08:10:00,Pump-01,Pressure High\n"
        )

        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)

            with self.assertRaisesRegex(AlarmDataError, "severity"):
                load_alarms(csv_path)

    def test_rejects_blank_required_value(self):
        content = (
            "timestamp,equipment,alarm_type,severity\n"
            "2026-07-20 08:10:00, ,Pressure High,warning\n"
        )

        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)

            with self.assertRaisesRegex(
                AlarmDataError,
                "第 2 行的 equipment 欄位不可為空",
            ):
                load_alarms(csv_path)

    def test_rejects_invalid_timestamp(self):
        content = (
            "timestamp,equipment,alarm_type,severity\n"
            "not-a-time,Pump-01,Pressure High,warning\n"
        )

        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)

            with self.assertRaisesRegex(AlarmDataError, "timestamp 格式錯誤"):
                load_alarms(csv_path)

    def test_rejects_csv_without_alarm_rows(self):
        content = "timestamp,equipment,alarm_type,severity\n"

        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)

            with self.assertRaisesRegex(AlarmDataError, "沒有告警資料"):
                load_alarms(csv_path)


class BuildReportDataTests(unittest.TestCase):
    """測試報表是否整合正確統計及 top 篩選結果。"""

    def test_builds_complete_report_data(self):
        alarms = make_sample_alarms()

        result = build_report_data(alarms, "warning", 1)

        self.assertEqual(result["total_alarms"], 3)
        self.assertEqual(
            result["severity_counts"],
            {"warning": 2, "critical": 1},
        )
        self.assertEqual(result["hour_counts"], {"08": 2, "09": 1})
        self.assertEqual(
            result["busiest_hour"],
            {"hour": "08", "count": 2},
        )
        self.assertEqual(
            result["busiest_equipment"],
            {"equipment": "Pump-01", "count": 2},
        )
        self.assertEqual(
            result["most_common_alarm_type"],
            {"alarm_type": "Pressure High", "count": 2},
        )
        self.assertEqual(
            result["selected_alarms"],
            {
                "severity": "warning",
                "total_matches": 2,
                "limit": 1,
                "returned": 1,
                "alarms": [alarms[0]],
            },
        )


class SaveReportJsonTests(unittest.TestCase):
    """測試報表能以 UTF-8 JSON 寫入檔案。"""

    def test_writes_readable_json_with_final_newline(self):
        report_data = {"message": "告警報表", "total_alarms": 3}

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "report.json"

            save_report_json(report_data, output_path)
            saved_text = output_path.read_text(encoding="utf-8")

        self.assertEqual(json.loads(saved_text), report_data)
        self.assertIn("告警報表", saved_text)
        self.assertTrue(saved_text.endswith("\n"))


class ParseArgsTests(unittest.TestCase):
    """測試命令列參數的預設值、指定值及錯誤值。"""

    def test_uses_default_values(self):
        args = parse_args([])

        self.assertEqual(args.csv_path, DEFAULT_CSV_PATH)
        self.assertEqual(args.severity, "critical")
        self.assertEqual(args.top, 5)
        self.assertEqual(args.output, Path("report.json"))

    def test_parses_custom_values(self):
        args = parse_args(
            [
                "input.csv",
                "--severity",
                "warning",
                "--top",
                "3",
                "--output",
                "custom.json",
            ]
        )

        self.assertEqual(args.csv_path, Path("input.csv"))
        self.assertEqual(args.severity, "warning")
        self.assertEqual(args.top, 3)
        self.assertEqual(args.output, Path("custom.json"))

    def test_rejects_negative_top(self):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as context:
                parse_args(["--top", "-1"])

        self.assertEqual(context.exception.code, 2)


class MainIntegrationTests(unittest.TestCase):
    """測試 main() 能串起 CSV、報表顯示及 JSON 輸出。"""

    def test_returns_zero_and_creates_report_for_valid_csv(self):
        content = (
            "timestamp,equipment,alarm_type,severity\n"
            "2026-07-20 08:10:00,Pump-01,Pressure High,warning\n"
            "2026-07-20 08:20:00,Pump-01,Pressure High,critical\n"
            "2026-07-20 09:30:00,Valve-01,Position Error,warning\n"
        )

        with TemporaryDirectory() as directory:
            csv_path = write_csv(directory, content)
            output_path = Path(directory) / "report.json"
            stdout = StringIO()

            with redirect_stdout(stdout):
                result = main(
                    [
                        str(csv_path),
                        "--severity",
                        "warning",
                        "--top",
                        "1",
                        "--output",
                        str(output_path),
                    ]
                )

            report_data = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertIn("warning 告警共有 2 筆", stdout.getvalue())
        self.assertIn("JSON 報表已輸出", stdout.getvalue())
        self.assertEqual(report_data["selected_alarms"]["returned"], 1)

    def test_returns_one_when_csv_does_not_exist(self):
        with TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing.csv"
            output_path = Path(directory) / "report.json"
            stderr = StringIO()

            with redirect_stderr(stderr):
                result = main(
                    [
                        str(missing_path),
                        "--output",
                        str(output_path),
                    ]
                )

            output_exists = output_path.exists()

        self.assertEqual(result, 1)
        self.assertIn("找不到 CSV 檔案", stderr.getvalue())
        self.assertFalse(output_exists)


if __name__ == "__main__":
    unittest.main()
