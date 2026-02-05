## 台山話英文字典（ts-english-dict）

- **對應主項目 id**: `ts-english-dict`
- **主項目文件名**: `ts-english-dict.json`
- **最終 JSON 輸出路徑（喺主項目入面）**: `public/dictionaries/ts-english-dict.json`

### 數據來源同使用限制

- **數據來源**：**台山話英文字典 (Taishanese–English Dictionary)**，Gene M. Chin，網上詞典，來源網址如下：
  - `https://www.chinfamilytree.com/hed/index.htm`
- **版權同用途**：數據係嚟自公開網上詞典，版權 © 2005–2024 Gene M. Chin。授權條款未完全明確，使用同再分發嘅時候請尊重原作者，並且標明出處（同主項目 `index.json` 入面嘅 `license`／`usage_restriction` 保持一致）。

### 呢個目錄入面主要嘅文件

- `HED Alphabetically (A-Y) October 2024.html`：網頁形式嘅原始數據。
- `HED Alphabetically (A-Y) October 2024.csv`：由網頁解析出嚟嘅詞條數據。
- `HED Alphabetically (A-Y) October 2024_phrases.csv` ／ `_phrases_jyutping.csv`：短語同對應粵拼數據。
- `hed_html_to_csv.py`：將 HTML 轉做 CSV 嘅腳本。
- `hed_extract_phrases.py`：喺詞條數據入面抽短語同相關資訊。
- `convert_gps_to_jyutping.py`：將原本標註轉換／對齊去目標粵拼系統。

### 建議嘅構建流程（示意）

1. 運行 `hed_html_to_csv.py`，由網頁 HTML 提取基礎 CSV 數據。
2. 運行 `hed_extract_phrases.py` 同 `convert_gps_to_jyutping.py`，攞到帶台山話羅馬字／粵拼等資訊嘅最終 CSV。
3. 將最終表格提交／同步去主項目可以讀到嘅位置（例如俾主項目腳本直接喺呢個倉庫讀嗰個 CSV）。
4. 喺主項目 `Jyutjyu` 入面運行 `scripts/adapters/ts-english-dict.js`：

   - 由最終 CSV 讀數據；
   - 轉做符合主項目 `DictionaryEntry` 結構嘅 `DictionaryEntry[]`（英文釋義可以擺喺 `senses` 入面嘅英文 gloss；台山話羅馬字／拼音可以擺喺 `phonetic` 或者 `meta` 入面）；
   - 寫入主項目倉庫嘅 `public/dictionaries/ts-english-dict.json`。

呢個倉庫只係負責準備同維護 CSV／中間數據，出最終 JSON 嘅邏輯係放喺主項目嘅 `scripts/adapters/ts-english-dict.js` 入面。
