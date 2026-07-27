import csv

# 資料檔與此程式放在同一資料夾，所以路徑直接用檔名即可
CSV_PATH = "alarms.csv"


def load_alarms(csv_path):
    """
    讀取 CSV，回傳所有告警的 list。
    每一筆告警是一個 dict，例如：
    {'timestamp': '...', 'equipment': 'Pump-02', 'alarm_type': '...', 'severity': 'warning'}
    """
    alarms = []  # 型態：list，用來存放多筆 dict

    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # row 是 dict；append 會把它加到 list 尾端
            alarms.append(row)

    return alarms  # 把結果交給呼叫這個函式的地方（例如 main）


def get_hour(timestamp):
    time_part = timestamp.split(" ")[1]   # "08:11:14"
    hour = time_part.split(":")[0]        # "08"
    return hour

def count_alarms_by_severity(alarms):
    count = {}

    for alarm in alarms:
        severity = alarm["severity"]

        if severity not in count:
            count[severity] = 0

        count[severity] += 1
    
    return count


def count_alarms_by_hour(alarms):
    count = {}

    for alarm in alarms:
        hour = get_hour(alarm["timestamp"])

        if hour not in count:
            count[hour] = 0
        
        count[hour] += 1

    return count

def find_busiest_hour(hour_count):
    busiest_hour = None
    busiest_count = 0

    for hour, count in hour_count.items():
        if count > busiest_count:
            busiest_count = count
            busiest_hour = hour

    return busiest_hour, busiest_count


def main():
    alarms = load_alarms(CSV_PATH)


    # len(alarms) -> int，list 裡有幾筆
    print(f"總共讀到 {len(alarms)} 筆告警")
    # alarms[0]  第一筆（索引從 0 開始）
    # alarms[-1] 最後一筆（-1 代表從後面數）
    print("第一筆：", alarms[0])
    print("最後一筆：", alarms[-1])

    print("告警嚴重程度統計：")
    severity_count = count_alarms_by_severity(alarms)
    for severity, count in severity_count.items():
        print(f"- [{severity}]: {count} 筆")
    
    print("告警時間統計：")
    hour_count = count_alarms_by_hour(alarms)

    print("每小時告警統計")
    for hour in sorted(hour_count):
        count = hour_count[hour]
        print(f"- [{hour}:00]: {count} 筆")
    
    busiest_hour,busiest_count = find_busiest_hour(hour_count)
    print(f"告警最多的時段：{busiest_hour}:00，共 {busiest_count} 筆") 

if __name__ == "__main__":
    main()
