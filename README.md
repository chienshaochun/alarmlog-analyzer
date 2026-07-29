# Alarm Log Analyzer

這是一個使用 Python 撰寫的告警紀錄分析練習專案。程式會讀取 CSV 格式的設備告警資料，整理告警的嚴重程度與發生時段，協助快速了解一批告警紀錄的分布情況。

目前專案是以命令列執行的單一 Python 程式，不需要安裝第三方套件。

## 目前功能

執行程式後會：

1. 從 `alarms.csv` 載入所有告警。
2. 顯示告警總筆數、第一筆與最後一筆資料。
3. 依嚴重程度統計筆數及百分比。
4. 依小時統計告警筆數。
5. 找出告警數量最多的時段。
6. 篩選 `critical` 告警，並顯示前 5 筆的時間、設備與告警類型。

## 專案結構

```text
alarmlog_analyzer/
├── alarm.py       # 載入、分析並輸出告警統計
├── alarms.csv     # 告警原始資料
└── README.md      # 專案說明
```

## 執行環境

- Python 3
- 目前已使用 Python 3.12 驗證
- 僅使用 Python 標準函式庫，不需要執行 `pip install`

目前 `alarm.py` 內含 Windows 的 `nt` 模組匯入，因此建議先在 Windows 環境執行。該匯入目前沒有參與告警分析邏輯。

## 快速開始

在 PowerShell 進入專案目錄：

```powershell
cd C:\Users\ru03g\side_project\alarmlog_analyzer
python .\alarm.py
```

程式目前使用相對路徑讀取 `alarms.csv`，因此執行時的工作目錄需要是專案根目錄。

## CSV 資料格式

`alarms.csv` 必須包含以下欄位名稱：

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

程式以 `utf-8-sig` 編碼讀取 CSV，因此可接受一般 UTF-8 CSV，也可正確處理由 Excel 等工具輸出的 UTF-8 BOM。

## 目前資料的分析結果

使用專案內附的 `alarms.csv` 執行時：

- 告警總數：300 筆
- `warning`：164 筆（54.67%）
- `critical`：131 筆（43.67%）
- `info`：5 筆（1.67%）
- 告警最多的時段：11:00，共 20 筆

部分輸出如下：

```text
總共讀到 300 筆告警
告警嚴重程度統計：
- [warning]: 164 筆(54.67%)
- [critical]: 131 筆(43.67%)
- [info]: 5 筆(1.67%)

告警最多的時段：11:00，共 20 筆
Critical 告警共有 131 筆
```

如果修改 `alarms.csv`，分析結果也會隨之改變。

## 程式處理流程

```text
alarms.csv
    ↓
load_alarms()
    ↓
告警嚴重程度統計 ──→ 筆數與百分比
每小時告警統計   ──→ 告警最多時段
critical 篩選     ──→ 顯示前 5 筆
```

## 主要函式

| 函式 | 用途 |
| --- | --- |
| `load_alarms(csv_path)` | 讀取 CSV，將每一列轉成字典並組成清單 |
| `get_hour(timestamp)` | 從時間字串取得小時，例如從 `08:11:14` 取得 `08` |
| `count_alarms_by_severity(alarms)` | 統計各嚴重程度的告警數量 |
| `count_alarms_by_hour(alarms)` | 統計每個小時的告警數量 |
| `find_busiest_hour(hour_count)` | 找出告警最多的小時及筆數 |
| `filter_alarms_by_severity(alarms, target_severity)` | 依指定嚴重程度篩選告警 |
| `calculate_percentage(part, total)` | 計算百分比，總數為 0 時回傳 `0.0` |
| `main()` | 串接資料載入、分析與命令列輸出 |

## 目前限制與注意事項

- CSV 檔名固定為 `alarms.csv`，目前不能從命令列指定其他檔案。
- 欄位名稱必須與既定格式一致，程式目前沒有欄位驗證或錯誤提示。
- `timestamp` 必須包含日期與時間，並以空格分隔；格式錯誤會造成解析失敗。
- `severity` 比對會區分大小寫，例如 `critical` 與 `Critical` 會被視為不同值。
- CSV 若只有標題而沒有資料，顯示第一筆與最後一筆資料時會發生錯誤。
- 如果多個時段並列最高，目前會回傳分析過程中最先遇到的時段。
- 分析結果只會顯示在終端機，尚未輸出成報表或圖表。

## 後續可擴充方向

- 支援從命令列指定 CSV 路徑與篩選條件。
- 加入 CSV 欄位、時間格式與空資料檢查。
- 增加設備別與告警類型統計。
- 將結果匯出為新的 CSV、JSON 或 HTML 報表。
- 加入趨勢圖與告警分布圖。
- 補上自動化測試與跨平台支援。
