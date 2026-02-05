## 廣州方言詞典（gz-dialect）

- **對應主項目 id**: `gz-dialect`
- **主項目文件名**: `gz-dialect.json`
- **最終 JSON 輸出路徑（喺主項目入面）**: `public/dictionaries/gz-dialect.json`

### 數據來源同使用限制

- **數據來源**：**《廣州方言詞典》**，白宛如編，江蘇教育出版社，1998 年版。
- **版權同用途**：詞表內容受版權保護，係嚟自互聯網公開掃描資源，只係用嚟做呢個項目嘅原型驗證同技術示範，**唔可以**用作商業用途或者再分發（同主項目 `index.json` 入面嘅 `license`／`usage_restriction` 保持一致）。

### 呢個目錄入面主要嘅文件

- `OCR_openrouter_gz-dialect.py`：調用 OCR 介面，生成呢本書嘅 OCR 文字或者圖像增強版本。
- `preprocess_gz-dialect.py`：對 OCR 輸出做預處理（切圖、去噪、版面修正等）。
- `convert_to_table_gz-dialect.py`：將處理完嘅數據轉做結構化表格／CSV。
- `verify_jyutping_gz-dialect.py` 同 `test_*`：用嚟驗證粵拼同流程正確性嘅腳本。
- `OCR_兩階段流程說明.md`、`廣州方言詞典_預處理說明.md`：關於 OCR 同預處理嘅說明文檔。

### 建議嘅構建流程（示意）

1. 運行 `OCR_openrouter_gz-dialect.py`，對原始掃描頁做 OCR（淨係喺本機生成，原始 PDF／圖片同 OCR 輸出都唔會入庫）。
2. 運行 `preprocess_gz-dialect.py`，對 OCR 結果做清洗、切分同整理。
3. 運行 `convert_to_table_gz-dialect.py`，生成結構化表格（CSV 或者類似格式）。
4. 將最終表格提交／同步去主項目可以讀到嘅位置（例如俾主項目腳本直接喺呢個倉庫讀嗰個 CSV）。
5. 喺主項目 `Jyutjyu` 入面運行 `scripts/adapters/gz-dialect.js`：

   - 由最終 CSV 讀數據；
   - 轉做符合主項目 `DictionaryEntry` 結構嘅 `DictionaryEntry[]`；
   - 寫入主項目倉庫嘅 `public/dictionaries/gz-dialect.json`。

呢個倉庫只係負責準備同維護 CSV／中間數據，出最終 JSON 嘅邏輯係放喺主項目嘅 `scripts/adapters/gz-dialect.js` 入面。
