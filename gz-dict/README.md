## 廣州話詞典（第 2 版）（gz-dict）

- **對應主項目 id**: `gz-dict`
- **主項目文件名**: `gz-dict.json`
- **最終 JSON 輸出路徑（喺主項目入面）**: `public/dictionaries/gz-dict.json`

### 數據來源同使用限制

- **數據來源**：**《廣州話詞典（第 2 版）》**，饒秉才、歐陽覺亞、周無忌編，廣東人民出版社，2020 年版。
- **版權同用途**：詞表內容受版權保護，係嚟自互聯網公開掃描資源，只係用嚟做呢個項目嘅原型驗證同技術示範，**唔可以**用作商業用途或者再分發（同主項目 `index.json` 入面嘅 `license`／`usage_restriction` 保持一致）。

### 呢個目錄入面主要嘅文件

- `OCR_openrouter_gz-dict.py`：調用 OCR 介面，生成呢本書嘅 OCR 文字或者圖像增強版本。
- `convert_to_table_gz-dict.py`：將 OCR／預處理結果轉做結構化表格。
- `convert_to_jyutping.py`：幫表格補充或者規範化粵拼。
- `extract_pages_to_json.py`：由 PDF／圖像頁提取內容，寫入 JSON。
- `README_OCR修改說明.md`：關於 OCR／預處理修改嘅說明。
- `requirements.txt`：處理呢本書流程用到嘅依賴。

### 建議嘅構建流程（示意）

1. 用 `OCR_openrouter_gz-dict.py` 同相關預處理步驟喺本機生成 OCR 同中間結果（原始 PDF／圖片同 OCR 輸出都唔會入庫）。
2. 運行 `convert_to_table_gz-dict.py`，生成結構化表格（CSV 或者類似格式）。
3. 運行 `convert_to_jyutping.py`，生成帶粵拼嘅最終表格。
4. 將最終表格提交／同步去主項目可以讀到嘅位置（例如俾主項目腳本直接喺呢個倉庫讀嗰個 CSV）。
5. 喺主項目 `Jyutjyu` 入面運行 `scripts/adapters/gz-dict.js`：

   - 由最終 CSV 讀數據；
   - 轉做符合主項目 `DictionaryEntry` 結構嘅 `DictionaryEntry[]`；
   - 寫入主項目倉庫嘅 `public/dictionaries/gz-dict.json`。

呢個倉庫只係負責準備同維護 CSV／中間數據，出最終 JSON 嘅邏輯係放喺主項目嘅 `scripts/adapters/gz-dict.js` 入面。
