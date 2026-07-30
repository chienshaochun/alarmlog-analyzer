import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_CSV_PATH = Path(__file__).with_name("alarms.csv")
REQUIRED_COLUMNS = ("timestamp", "equipment", "alarm_type", "severity")
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class AlarmDataError(ValueError):
    """表示 CSV 的告警資料格式不正確。"""


def load_alarms(csv_path):
    """
    讀取並驗證 CSV，回傳所有告警的 list。

    每一筆告警是一個 dict，例如：
    {'timestamp': '...', 'equipment': 'Pump-02', 'alarm_type': '...', 'severity': 'warning'}
    """
    alarms = []

    # with 會在離開區塊時自動關閉檔案；utf-8-sig 可讀一般 UTF-8 與 BOM。
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise AlarmDataError("CSV 缺少標題列")

        # 集合差集：必要欄位 - CSV 實際欄位 = 缺少的欄位。
        missing_columns = set(REQUIRED_COLUMNS) - set(reader.fieldnames)
        if missing_columns:
            column_names = ", ".join(sorted(missing_columns))
            raise AlarmDataError(f"CSV 缺少必要欄位：{column_names}")

        # enumerate() 同時取得行號與資料；2 是第一筆資料的實際 CSV 行號。
        for line_number, row in enumerate(reader, start=2):
            alarm = {}

            # 對目前這筆告警逐一檢查四個必要欄位。
            for column in REQUIRED_COLUMNS:
                value = row.get(column)
                if value is None or not value.strip():
                    raise AlarmDataError(
                        f"第 {line_number} 行的 {column} 欄位不可為空"
                    )
                # strip() 只移除字串前後的空白字元，不會移除中間空格。
                alarm[column] = value.strip()

            # strptime() 將字串解析成 datetime；這裡只用來驗證格式。
            try:
                datetime.strptime(alarm["timestamp"], TIMESTAMP_FORMAT)
            except ValueError as error:
                raise AlarmDataError(
                    f"第 {line_number} 行的 timestamp 格式錯誤，"
                    "正確格式為 YYYY-MM-DD HH:MM:SS"
                # from error 明確保留原始 ValueError 是新錯誤的原因。
                ) from error

            alarms.append(alarm)

    if not alarms:
        raise AlarmDataError("CSV 沒有告警資料")

    return alarms


def get_hour(timestamp):
    """將時間字串轉成 datetime，再回傳兩位數的小時字串。"""
    # strptime：字串 → datetime。
    alarm_time = datetime.strptime(timestamp, TIMESTAMP_FORMAT)
    # strftime：datetime → 指定格式的字串。
    return alarm_time.strftime("%H")


def count_alarms_by_field(alarms, field_name):
    """依指定欄位統計數量，避免為每個欄位重複撰寫迴圈。"""
    count = {}

    for alarm in alarms:
        # field_name 可傳入 severity、equipment 或 alarm_type。
        field_value = alarm[field_name]

        if field_value not in count:
            count[field_value] = 0

        count[field_value] += 1

    return count


def count_alarms_by_severity(alarms):
    return count_alarms_by_field(alarms, "severity")


def count_alarms_by_equipment(alarms):
    return count_alarms_by_field(alarms, "equipment")


def count_alarms_by_alarm_type(alarms):
    return count_alarms_by_field(alarms, "alarm_type")


def sort_counts_descending(counts):
    """依數量由多到少排序，數量相同時再依名稱排序。"""
    return sorted(
        counts.items(),
        # lambda 只建立比較用的 key，不會改變原始 item。
        # item[1] 是數量；加負號可讓 sorted() 達成由大到小。
        key=lambda item: (-item[1], item[0]),
    )


def find_most_common(counts):
    """回傳排序後的第一個 (名稱, 數量)，空資料回傳 (None, 0)。"""
    sorted_counts = sort_counts_descending(counts)

    if not sorted_counts:
        return None, 0

    # 如果最高數量並列，目前設計只取名稱排序較前的第一筆。
    return sorted_counts[0]


def count_alarms_by_hour(alarms):
    count = {}

    for alarm in alarms:
        hour = get_hour(alarm["timestamp"])

        if hour not in count:
            count[hour] = 0

        count[hour] += 1

    return count


def find_busiest_hour(hour_count):
    return find_most_common(hour_count)


def filter_alarms_by_severity(alarms, target_severity):
    """建立並回傳符合指定嚴重程度的新告警清單。"""
    filtered_alarms = []

    for alarm in alarms:
        # == 比較會區分大小寫，例如 critical 不等於 Critical。
        if alarm["severity"] == target_severity:
            filtered_alarms.append(alarm)

    return filtered_alarms


def calculate_percentage(part, total):
    if total == 0:
        return 0.0

    return part / total * 100


def build_report_data(alarms, target_severity, top):
    """整理完整統計與指定篩選結果，回傳可轉成 JSON 的 dict。"""
    severity_counts = count_alarms_by_severity(alarms)
    hour_counts = count_alarms_by_hour(alarms)
    equipment_counts = count_alarms_by_equipment(alarms)
    alarm_type_counts = count_alarms_by_alarm_type(alarms)

    # JSON 與終端機使用相同的 severity 和 top 篩選條件。
    matching_alarms = filter_alarms_by_severity(alarms, target_severity)
    selected_alarms = matching_alarms[:top]

    # 這三個函式都回傳 (名稱, 數量)，可用 tuple unpacking 拆開。
    busiest_hour, busiest_hour_count = find_busiest_hour(hour_counts)
    busiest_equipment, equipment_alarm_count = find_most_common(
        equipment_counts
    )
    most_common_alarm_type, most_common_alarm_type_count = find_most_common(
        alarm_type_counts
    )

    # dict 的 key 將成為 JSON 欄位名稱，value 也可以是另一個 dict。
    report_data = {
        "total_alarms": len(alarms),
        "selected_alarms": {
            "severity": target_severity,
            "total_matches": len(matching_alarms),
            "limit": top,
            "returned": len(selected_alarms),
            "alarms": selected_alarms,
        },
        "severity_counts": severity_counts,
        "hour_counts": hour_counts,
        "busiest_hour": {
            "hour": busiest_hour,
            "count": busiest_hour_count,
        },
        "equipment_counts": equipment_counts,
        "busiest_equipment": {
            "equipment": busiest_equipment,
            "count": equipment_alarm_count,
        },
        "alarm_type_counts": alarm_type_counts,
        "most_common_alarm_type": {
            "alarm_type": most_common_alarm_type,
            "count": most_common_alarm_type_count,
        },
    }

    return report_data


def save_report_json(report_data, output_path):
    """將報表 dict 寫成 UTF-8 JSON 檔案。"""
    with Path(output_path).open("w", encoding="utf-8") as file:
        json.dump(
            report_data,
            file,
            ensure_ascii=False,
            indent=2,
        )
        # 在檔案末尾補換行，讓文字編輯器與版本控制顯示更整齊。
        file.write("\n")


def print_report(alarms, target_severity, top):
    """顯示完整統計，並列出指定嚴重程度的前 top 筆告警。"""
    print(f"總共讀到 {len(alarms)} 筆告警")
    print("第一筆：", alarms[0])
    print("最後一筆：", alarms[-1])

    print("告警嚴重程度統計：")
    severity_count = count_alarms_by_severity(alarms)
    total_alarms = len(alarms)

    for severity, count in severity_count.items():
        percentage = calculate_percentage(count, total_alarms)
        print(f"- [{severity}]: {count} 筆 ({percentage:.2f}%)")

    print("每小時告警統計：")
    hour_count = count_alarms_by_hour(alarms)
    for hour in sorted(hour_count):
        print(f"- [{hour}:00]: {hour_count[hour]} 筆")

    busiest_hour, busiest_count = find_busiest_hour(hour_count)
    print(f"告警最多的時段：{busiest_hour}:00，共 {busiest_count} 筆")

    print("設備告警統計：")
    equipment_count = count_alarms_by_equipment(alarms)
    for equipment, count in sort_counts_descending(equipment_count):
        print(f"- [{equipment}]: {count} 筆")

    busiest_equipment, equipment_alarm_count = find_most_common(equipment_count)
    print(
        f"告警最多的設備：{busiest_equipment}，"
        f"共 {equipment_alarm_count} 筆"
    )

    print("告警類型統計：")
    alarm_type_count = count_alarms_by_alarm_type(alarms)
    for alarm_type, count in sort_counts_descending(alarm_type_count):
        print(f"- [{alarm_type}]: {count} 筆")

    most_common_alarm_type, alarm_type_total = find_most_common(alarm_type_count)
    print(
        f"最常發生的告警類型：{most_common_alarm_type}，"
        f"共 {alarm_type_total} 筆"
    )

    # target_severity 來自命令列的 args.severity，不再固定為 critical。
    filtered_alarms = filter_alarms_by_severity(alarms, target_severity)
    print(f"{target_severity} 告警共有 {len(filtered_alarms)} 筆")

    # list[:top] 會從索引 0 開始，最多取得 top 筆。
    for alarm in filtered_alarms[:top]:
        print(
            alarm["timestamp"],
            alarm["equipment"],
            alarm["alarm_type"],
        )


def parse_args(argv=None):
    """定義並解析命令列參數。"""
    parser = argparse.ArgumentParser(
        description="讀取 CSV 告警紀錄並顯示統計結果。"
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="CSV 檔案路徑（預設：程式旁的 alarms.csv）",
    )
    # 有 -- 開頭的是選用參數；choices 會限制允許輸入的值。
    parser.add_argument(
        "--severity",
        choices=("critical", "warning", "info"),
        default="critical",
        help="要顯示的告警嚴重程度（預設：critical）",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="詳細告警的顯示筆數（預設：5）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("report.json"),
        help="JSON 報表的輸出路徑（預設:report.json）",
    )

    args = parser.parse_args(argv)
    # int 會拒絕非整數；這裡再拒絕會造成反向切片的負數。
    if args.top < 0:
        parser.error("--top 不可小於 0")

    return args


def main(argv=None):
    args = parse_args(argv)

    try:
        alarms = load_alarms(args.csv_path)
    except FileNotFoundError:
        print(f"錯誤：找不到 CSV 檔案：{args.csv_path}", file=sys.stderr)
        return 1
    except PermissionError:
        print(f"錯誤：沒有權限讀取 CSV 檔案：{args.csv_path}", file=sys.stderr)
        return 1
    except UnicodeDecodeError:
        print("錯誤：CSV 必須使用 UTF-8 編碼", file=sys.stderr)
        return 1
    except (csv.Error, AlarmDataError) as error:
        print(f"錯誤：{error}", file=sys.stderr)
        return 1

    # 將 parse_args() 解析出的 severity 與 top 傳入報表函式。
    print_report(alarms, args.severity, args.top)

    # args.output 未指定時也是 Path("report.json")，因此每次都會輸出報表。
    report_data = build_report_data(alarms, args.severity, args.top)

    try:
        save_report_json(report_data, args.output)
    except OSError as error:
        print(f"錯誤：無法寫入 JSON 報表：{error}", file=sys.stderr)
        return 1

    print(f"JSON 報表已輸出：{args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
