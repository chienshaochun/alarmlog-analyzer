# Alarm Log Analyzer

這是一個用來練習 Python 基礎能力的命令列專案。程式會讀取 CSV 格式的設備告警資料，驗證資料內容，並整理告警的嚴重程度與發生時段。

這個專案有明確的學習終點。完成下方的「專案畢業目標」後就停止擴充，進入下一個 Python 專案。

## 目前功能

執行程式後會：

1. 從預設或使用者指定的 CSV 載入告警。
2. 驗證必要欄位、空值及時間格式。
3. 顯示告警總筆數、第一筆與最後一筆資料。
4. 依嚴重程度統計筆數及百分比。
5. 依小時統計告警筆數。
6. 找出告警數量最多的時段。
7. 依數量由多到少顯示設備與告警類型統計。
8. 找出告警最多的設備與最常發生的告警類型。
9. 依命令列指定的嚴重程度篩選告警，並控制詳細資料顯示筆數。
10. 將完整統計、最高項目及篩選詳細資料輸出成 JSON。
11. 發生缺檔或資料格式錯誤時，顯示清楚訊息並回傳錯誤碼。

## 專案畢業目標

最終目標：使用純 Python 標準函式庫，完成一個可從命令列操作、能處理錯誤、可匯出分析結果，並具備自動化測試的告警分析工具。

目前任務進度：5 / 7

- [x] 讀取 UTF-8 CSV 告警資料
- [x] 統計嚴重程度、百分比與每小時告警數
- [x] 找出告警最多時段並篩選 `critical` 告警
- [x] 從命令列指定 CSV 路徑
- [x] 處理缺檔、必要欄位、空資料與時間格式錯誤
- [x] 使用 `pathlib`、`argparse`、函式與例外處理
- [x] 增加設備別與告警類型統計
- [x] 增加嚴重程度篩選與顯示筆數參數
- [x] 將分析結果匯出為 JSON
- [ ] 使用 Python 內建 `unittest` 測試核心函式
- [ ] 完成最終操作驗證，並能說明完整資料流程

## 專案結構

```text
alarmlog_analyzer/
├── alarm.py       # 命令列入口、資料驗證與告警分析
├── alarms.csv     # 告警原始資料
├── report.json    # 執行程式時建立或覆蓋的 JSON 報表
└── README.md      # 使用方式、資料格式與學習進度
```

## 執行環境

- Python 3
- 目前已使用 Python 3.12 驗證
- 僅使用 Python 標準函式庫，不需要執行 `pip install`
- 可在 Windows、macOS 或 Linux 執行

## 快速開始

在 PowerShell 進入專案目錄後，使用程式旁的預設 `alarms.csv`：

```powershell
python .\alarm.py
```

這會在目前 PowerShell 資料夾建立或覆蓋預設的 `report.json`。

指定其他 CSV：

```powershell
python .\alarm.py .\other_alarms.csv
```

篩選嚴重程度並控制詳細資料筆數：

```powershell
python .\alarm.py .\alarms.csv --severity warning --top 10
```

`--severity` 可使用 `critical`、`warning` 或 `info`；`--top` 必須是 0 或正整數，預設為 5。

指定其他 JSON 輸出路徑：

```powershell
python .\alarm.py --output .\other_report.json
```

查看命令列說明：

```powershell
python .\alarm.py --help
```

預設 CSV 路徑是根據 `alarm.py` 的位置取得，因此從其他工作目錄啟動程式時也能找到內附資料。JSON 輸出路徑則以目前命令列所在資料夾為基準。

## JSON 報表

每次執行都會以寫入模式建立或覆蓋 JSON。報表包含：

- 告警總數及嚴重程度、時段、設備、告警類型統計。
- 告警最多時段、設備與最常見告警類型。
- `--severity` 指定的條件及符合總數。
- `--top` 指定的限制、實際回傳數量及詳細告警。

預設輸出為 `report.json`；使用 `--output` 可以改成其他路徑。

## CSV 資料格式

CSV 必須包含以下欄位名稱：

| 欄位 | 說明 | 範例 |
| --- | --- | --- |
| `timestamp` | 告警發生時間，格式為 `YYYY-MM-DD HH:MM:SS` | `2026-07-20 08:11:14` |
| `equipment` | 發生告警的設備名稱或編號 | `Pump-02` |
| `alarm_type` | 告警類型 | `Pressure High` |
| `severity` | 告警嚴重程度 | `warning` |

範例：

```csv
timestamp,equipment,alarm_type,severity
2026-07-20 08:11:14,Pump-02,Pressure High,warning
2026-07-20 08:31:39,Valve-02,Failed to Close,critical
```

程式以 `utf-8-sig` 編碼讀取 CSV，因此可接受一般 UTF-8 CSV，也可處理由 Excel 等工具輸出的 UTF-8 BOM。

以下情況會停止分析並顯示錯誤：

- 找不到或沒有權限讀取 CSV。
- CSV 缺少標題列或必要欄位。
- 必要欄位的值為空。
- `timestamp` 不符合指定格式。
- CSV 只有標題而沒有告警資料。

## 目前資料的分析結果

使用專案內附的 `alarms.csv` 執行時：

- 告警總數：300 筆
- `warning`：164 筆（54.67%）
- `critical`：131 筆（43.67%）
- `info`：5 筆（1.67%）
- 告警最多的時段：11:00，共 20 筆
- 告警最多的設備：`Tank-01`，共 49 筆
- 最常發生的告警類型：`Position Error`，共 32 筆

如果修改或指定其他 CSV，分析結果也會隨之改變。

## 程式處理流程

```text
命令列參數
    ↓
選擇 CSV 路徑
    ↓
load_alarms()：讀取並驗證資料
    ├──→ print_report()
    │       ├── 嚴重程度、時段、設備及告警類型統計
    │       └── severity 篩選 ──→ 顯示前 top 筆
    └──→ build_report_data()
            ↓
         save_report_json() ──→ report.json
```

## 主要函式與類別

| 名稱 | 用途 |
| --- | --- |
| `AlarmDataError` | 表示 CSV 告警內容不符合格式 |
| `load_alarms(csv_path)` | 讀取並驗證 CSV，回傳告警清單 |
| `get_hour(timestamp)` | 解析時間並取得小時 |
| `count_alarms_by_field(alarms, field_name)` | 依指定欄位進行通用筆數統計 |
| `count_alarms_by_severity(alarms)` | 統計各嚴重程度的告警數量 |
| `count_alarms_by_equipment(alarms)` | 統計各設備的告警數量 |
| `count_alarms_by_alarm_type(alarms)` | 統計各告警類型的數量 |
| `count_alarms_by_hour(alarms)` | 統計每個小時的告警數量 |
| `sort_counts_descending(counts)` | 將統計結果依數量由多到少排列 |
| `find_most_common(counts)` | 找出統計結果中數量最多的項目 |
| `find_busiest_hour(hour_count)` | 找出告警最多的小時及筆數 |
| `filter_alarms_by_severity(alarms, target_severity)` | 依指定嚴重程度篩選告警 |
| `calculate_percentage(part, total)` | 計算百分比，總數為 0 時回傳 `0.0` |
| `build_report_data(alarms, target_severity, top)` | 建立包含完整統計與篩選資料的報表 dict |
| `save_report_json(report_data, output_path)` | 將報表 dict 寫成 UTF-8 JSON 檔案 |
| `print_report(alarms, target_severity, top)` | 顯示統計及指定嚴重程度的前 `top` 筆告警 |
| `parse_args(argv)` | 定義並解析命令列參數 |
| `main(argv)` | 串接參數、資料載入、錯誤處理與報表輸出 |

## 目前限制

- `severity` 比對會區分大小寫，例如 `critical` 與 `Critical` 是不同值。
- 多個項目的數量相同時，會再依名稱排列；並列最多時會取名稱排序較前的項目。

## 不在本專案範圍

為了維持 Python 基礎練習的焦點，本專案不加入圖形介面、網頁介面、資料庫、登入系統或 AI 分析。
