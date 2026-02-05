## 現代粵語詞典（gz-modern）

- **對應主項目 id**: `gz-modern`
- **主項目文件名**: `gz-modern.json`
- **最終 JSON 輸出路徑（喺主項目入面）**: `public/dictionaries/gz-modern.json`

### 數據來源同使用限制

- **數據來源**：**《現代粵語詞典（廣州音 第一版）》**，范俊軍、范蘭德等編，廣東人民出版社，2021 年版。
- **版權同用途**：詞表內容受版權保護，係嚟自互聯網公開掃描資源，只係用嚟做呢個項目嘅原型驗證同技術示範，**唔可以**用作商業用途或者再分發（同主項目 `index.json` 入面嘅 `license`／`usage_restriction` 保持一致）。

### 呢個目錄入面主要嘅文件

- `OCR_openrouter_gz-modern.py`：調用 OCR 介面，生成呢本書嘅 OCR 文字或者圖像增強版本。
- `preprocess_gz-modern.py`：對 OCR 輸出做預處理（切圖、去噪、版面修正等）。
- `convert_to_table_gz-modern.py`：將處理完嘅數據轉做結構化表格。
- `convert_to_jyutping.py`：幫表格補充或者規範化粵拼。
- `verify_jyutping.py`、`verify_final.py` 同 `test_*`：用嚟驗證粵拼同成個流程。
- `現代粵語詞典_table.csv` ／ `現代粵語詞典_table_粵拼.csv` ／ `現代粵語詞典_table_粵拼_已校對.csv`：唔同階段嘅結構化表格。

### 建議嘅構建流程（示意）

1. 運行 `OCR_openrouter_gz-modern.py`，對原始掃描頁做 OCR（淨係喺本機生成，原始 PDF／圖片同 OCR 輸出都唔會入庫）。
2. 運行 `preprocess_gz-modern.py`，對 OCR 結果做清洗、切分同整理。
3. 運行 `convert_to_table_gz-modern.py`，生成基礎表格 `現代粵語詞典_table.csv`。
4. 運行 `convert_to_jyutping.py`，再做人手／腳本校對，攞到 `現代粵語詞典_table_粵拼_已校對.csv` 作為最終表格。
5. 將最終表格提交／同步去主項目可以讀到嘅位置（例如俾主項目腳本直接喺呢個倉庫讀嗰個 CSV）。
6. 喺主項目 `Jyutjyu` 入面運行 `scripts/adapters/gz-modern.js`：

   - 由最終 CSV 讀數據；
   - 轉做符合主項目 `DictionaryEntry` 結構嘅 `DictionaryEntry[]`；
   - 寫入主項目倉庫嘅 `public/dictionaries/gz-modern.json`。

呢個倉庫只係負責準備同維護 CSV／中間數據，出最終 JSON 嘅邏輯係放喺主項目嘅 `scripts/adapters/gz-modern.js` 入面。
