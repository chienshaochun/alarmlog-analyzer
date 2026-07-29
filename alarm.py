# argparse：解析使用者在命令列輸入的參數。
import argparse
# csv：讀取 CSV 格式的告警資料。
import csv
# sys：這裡用來將錯誤訊息送到 stderr（標準錯誤輸出）。
import sys
# datetime：將時間字串轉換成可驗證、可處理的時間物件。
from datetime import datetime
# Path：用物件方式處理檔案路徑，比手動拼接字串更安全。
from pathlib import Path


# __file__ 是目前程式的路徑；with_name() 取得同一資料夾內的 alarms.csv。
# 因此即使從其他資料夾啟動程式，也能找到預設 CSV。
DEFAULT_CSV_PATH = Path(__file__).with_name("alarms.csv")

# tuple 保存 CSV 一定要有的欄位名稱，也固定輸出 dict 的欄位順序。
REQUIRED_COLUMNS = ("timestamp", "equipment", "alarm_type", "severity")

# datetime.strptime() 使用的時間格式。
# %Y=四位數年份、%m=月份、%d=日期、%H=小時、%M=分鐘、%S=秒。
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class AlarmDataError(ValueError):
    """表示檔案存在，但 CSV 內的告警資料格式不正確。"""


def load_alarms(csv_path):
    """
    讀取並驗證 CSV，回傳所有告警。

    參數：
        csv_path：要讀取的 CSV 路徑，可以是字串或 Path。

    回傳：
        list[dict]，其中每個 dict 代表一筆告警，例如：
        {
            "timestamp": "2026-07-20 08:11:14",
            "equipment": "Pump-02",
            "alarm_type": "Pressure High",
            "severity": "warning",
        }

    可能拋出的例外：
        FileNotFoundError：找不到檔案。
        PermissionError：沒有權限讀取檔案。
        AlarmDataError：CSV 欄位或資料內容不正確。
    """
    alarms = []

    # utf-8-sig 同時支援一般 UTF-8 與帶有 BOM 的 UTF-8 CSV。
    # newline="" 是 csv 模組建議的開啟方式，讓模組自行處理換行。
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as file:
        # DictReader 使用第一列作為 key，之後每一列都會變成 dict。
        reader = csv.DictReader(file)

        # fieldnames 為 None 代表檔案是空的，連標題列都沒有。
        if reader.fieldnames is None:
            raise AlarmDataError("CSV 缺少標題列")

        # 集合差集：必要欄位 - 實際欄位 = 缺少的欄位。
        missing_columns = set(REQUIRED_COLUMNS) - set(reader.fieldnames)
        if missing_columns:
            # 先排序再用逗號組合，讓錯誤訊息固定且容易閱讀。
            column_names = ", ".join(sorted(missing_columns))
            raise AlarmDataError(f"CSV 缺少必要欄位：{column_names}")

        # CSV 第一列是標題，所以第一筆資料的實際行號從 2 開始。
        for line_number, row in enumerate(reader, start=2):
            # 建立新的 dict，只保留並整理本程式需要的欄位。
            alarm = {}

            for column in REQUIRED_COLUMNS:
                # get() 在欄位不存在時回傳 None，不會立刻產生 KeyError。
                value = row.get(column)

                # strip() 移除前後空白；只含空白的內容也視為空值。
                if value is None or not value.strip():
                    raise AlarmDataError(
                        f"第 {line_number} 行的 {column} 欄位不可為空"
                    )

                alarm[column] = value.strip()

            try:
                # strptime() 解析失敗時會拋出 ValueError。
                # 這裡的目的只是驗證，所以不需要保存轉換後的物件。
                datetime.strptime(alarm["timestamp"], TIMESTAMP_FORMAT)
            except ValueError as error:
                # from error 保留原始例外，方便除錯時追查真正原因。
                raise AlarmDataError(
                    f"第 {line_number} 行的 timestamp 格式錯誤，"
                    "正確格式為 YYYY-MM-DD HH:MM:SS"
                ) from error

            alarms.append(alarm)

    # 有標題卻沒有任何資料時，避免後續存取 alarms[0] 發生錯誤。
    if not alarms:
        raise AlarmDataError("CSV 沒有告警資料")

    return alarms


def get_hour(timestamp):
    """將完整時間字串解析後，回傳兩位數小時，例如 "08"。"""
    alarm_time = datetime.strptime(timestamp, TIMESTAMP_FORMAT)
    return alarm_time.strftime("%H")


def count_alarms_by_field(alarms, field_name):
    """
    依指定欄位統計告警數量。

    例如 field_name="equipment" 時，回傳：
    {"Pump-01": 34, "Pump-02": 36, ...}

    這個通用函式讓 severity、equipment 和 alarm_type 不必各寫一次迴圈。
    """
    count = {}

    for alarm in alarms:
        # field_name 是變數，所以可用同一行讀取不同欄位。
        field_value = alarm[field_name]

        # 第一次遇到某個值時，先在 dict 建立 key 並從 0 開始。
        if field_value not in count:
            count[field_value] = 0

        count[field_value] += 1

    return count


def count_alarms_by_severity(alarms):
    """統計每種嚴重程度的告警數量。"""
    return count_alarms_by_field(alarms, "severity")


def count_alarms_by_equipment(alarms):
    """統計每台設備的告警數量。"""
    return count_alarms_by_field(alarms, "equipment")


def count_alarms_by_alarm_type(alarms):
    """統計每種告警類型的數量。"""
    return count_alarms_by_field(alarms, "alarm_type")


def sort_counts_descending(counts):
    """
    將統計 dict 轉成由多到少排列的 list[tuple]。

    counts.items() 的每個 item 是 (名稱, 數量)：
    item[0] 是名稱，item[1] 是數量。
    """
    return sorted(
        counts.items(),
        # 數量加負號可達成由大到小；數量相同時再依名稱排序。
        key=lambda item: (-item[1], item[0]),
    )


def find_most_common(counts):
    """回傳數量最多的 (名稱, 數量)；空統計則回傳 (None, 0)。"""
    sorted_counts = sort_counts_descending(counts)

    if not sorted_counts:
        return None, 0

    # 排序後的索引 0 就是數量最多的項目。
    return sorted_counts[0]


def count_alarms_by_hour(alarms):
    """依告警 timestamp 的小時統計數量。"""
    count = {}

    for alarm in alarms:
        hour = get_hour(alarm["timestamp"])

        if hour not in count:
            count[hour] = 0

        count[hour] += 1

    return count


def find_busiest_hour(hour_count):
    """回傳告警最多的 (小時, 數量)。"""
    # 最多時段與「找出數量最多項目」的邏輯相同，所以直接重用函式。
    return find_most_common(hour_count)


def filter_alarms_by_severity(alarms, target_severity):
    """回傳 severity 等於 target_severity 的告警清單。"""
    filtered_alarms = []

    for alarm in alarms:
        if alarm["severity"] == target_severity:
            filtered_alarms.append(alarm)

    return filtered_alarms


def calculate_percentage(part, total):
    """計算 part 佔 total 的百分比，避免 total=0 時除以零。"""
    if total == 0:
        return 0.0

    return part / total * 100


def print_report(alarms):
    """呼叫各分析函式，並將完整統計報表顯示在終端機。"""
    # 基本資料摘要。
    print(f"總共讀到 {len(alarms)} 筆告警")
    print("第一筆：", alarms[0])
    print("最後一筆：", alarms[-1])

    # 嚴重程度統計與百分比。
    print("告警嚴重程度統計：")
    severity_count = count_alarms_by_severity(alarms)
    total_alarms = len(alarms)

    for severity, count in severity_count.items():
        percentage = calculate_percentage(count, total_alarms)
        # :.2f 表示浮點數固定顯示到小數點後兩位。
        print(f"- [{severity}]: {count} 筆 ({percentage:.2f}%)")

    # 每小時統計。sorted(hour_count) 會按照 00、01、02...排列 key。
    print("每小時告警統計：")
    hour_count = count_alarms_by_hour(alarms)
    for hour in sorted(hour_count):
        print(f"- [{hour}:00]: {hour_count[hour]} 筆")

    # tuple 可以一次拆成 busiest_hour 與 busiest_count 兩個變數。
    busiest_hour, busiest_count = find_busiest_hour(hour_count)
    print(f"告警最多的時段：{busiest_hour}:00，共 {busiest_count} 筆")

    # 設備統計依數量由多到少輸出。
    print("設備告警統計：")
    equipment_count = count_alarms_by_equipment(alarms)
    for equipment, count in sort_counts_descending(equipment_count):
        print(f"- [{equipment}]: {count} 筆")

    busiest_equipment, equipment_alarm_count = find_most_common(equipment_count)
    print(
        f"告警最多的設備：{busiest_equipment}，"
        f"共 {equipment_alarm_count} 筆"
    )

    # 告警類型統計也重用同一組排序與尋找最高項目的函式。
    print("告警類型統計：")
    alarm_type_count = count_alarms_by_alarm_type(alarms)
    for alarm_type, count in sort_counts_descending(alarm_type_count):
        print(f"- [{alarm_type}]: {count} 筆")

    most_common_alarm_type, alarm_type_total = find_most_common(alarm_type_count)
    print(
        f"最常發生的告警類型：{most_common_alarm_type}，"
        f"共 {alarm_type_total} 筆"
    )

    # 目前固定篩選 critical，並用 [:5] 只取前 5 筆。
    # 任務 4 會把這兩個固定值改成命令列參數。
    critical_alarms = filter_alarms_by_severity(alarms, "critical")
    print(f"Critical 告警共有 {len(critical_alarms)} 筆")

    for alarm in critical_alarms[:5]:
        print(
            alarm["timestamp"],
            alarm["equipment"],
            alarm["alarm_type"],
        )


def parse_args(argv=None):
    """定義並解析命令列參數，回傳 argparse.Namespace。"""
    parser = argparse.ArgumentParser(
        description="讀取 CSV 告警紀錄並顯示統計結果。"
    )
    parser.add_argument(
        # 沒有 -- 開頭的參數稱為 positional argument（位置參數）。
        "csv_path",
        # ? 表示這個位置參數可以出現 0 次或 1 次。
        nargs="?",
        # argparse 收到的原始值是字串；type=Path 會自動轉換成 Path。
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="CSV 檔案路徑（預設：程式旁的 alarms.csv）",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """協調參數解析、資料載入、錯誤處理與報表輸出。"""
    args = parse_args(argv)

    try:
        alarms = load_alarms(args.csv_path)
    except FileNotFoundError:
        # stderr 專門放錯誤訊息，讓正常輸出與錯誤輸出可以分開處理。
        print(f"錯誤：找不到 CSV 檔案：{args.csv_path}", file=sys.stderr)
        return 1
    except PermissionError:
        print(f"錯誤：沒有權限讀取 CSV 檔案：{args.csv_path}", file=sys.stderr)
        return 1
    except UnicodeDecodeError:
        print("錯誤：CSV 必須使用 UTF-8 編碼", file=sys.stderr)
        return 1
    except (csv.Error, AlarmDataError) as error:
        # 一個 except 可以用 tuple 同時處理多種例外。
        print(f"錯誤：{error}", file=sys.stderr)
        return 1

    print_report(alarms)
    # 慣例上 0 代表成功，非 0（這裡是 1）代表執行失敗。
    return 0


# 只有直接執行 alarm.py 時才呼叫 main()；被其他程式 import 時不會執行。
if __name__ == "__main__":
    # SystemExit 會將 main() 的回傳值交給作業系統當作程式退出碼。
    raise SystemExit(main())
