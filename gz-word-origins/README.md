## 粵語辭源（gz-word-origins）

- **對應主項目 id**: `gz-word-origins`
- **主項目文件名**: `gz-word-origins.json`
- **最終 JSON 輸出路徑（喺主項目入面）**: `public/dictionaries/gz-word-origins.json`

### 數據來源同使用限制

- **數據來源**：**《粵語辭源》**，譚步云編，廣東人民出版社，2025 年版，加埋線上協作表格。
- **版權同用途**：詞表內容受版權保護，係嚟自互聯網公開掃描資源，只係用嚟做呢個項目嘅原型驗證同技術示範，**唔可以**用作商業用途或者再分發（同主項目 `index.json` 入面嘅 `license`／`usage_restriction` 保持一致）。

### 呢個目錄入面主要嘅文件

- `《粵語辭源》在線協作.xlsx`：協作用嘅原始表格。
- `《粵語辭源》在線協作.csv`：匯出出嚟嘅 CSV 版本。
- `《粵語辭源》在線協作_粵拼.csv`：已經帶粵拼嘅結構化版本。
- `convert_to_jyutping.py`：用嚟生成粵拼欄位嘅腳本。

### 建議嘅構建流程（示意）

1. 喺呢個目錄入面維護一份最終認可嘅表格（通常係帶粵拼嘅 CSV，例如 `《粵語辭源》在線協作_粵拼.csv`）。
2. 將最終表格提交／同步去主項目可以讀到嘅位置（例如俾主項目腳本直接喺呢個倉庫讀嗰個 CSV）。
3. 喺主項目 `Jyutjyu` 入面運行 `scripts/adapters/gz-word-origins.js`：

   - 由最終 CSV 讀數據；
   - 轉做符合主項目 `DictionaryEntry` 結構嘅 `DictionaryEntry[]`；
   - 寫入主項目倉庫嘅 `public/dictionaries/gz-word-origins.json`。

呢個倉庫只係負責準備同維護 CSV／中間數據，出最終 JSON 嘅邏輯係放喺主項目嘅 `scripts/adapters/gz-word-origins.js` 入面。
