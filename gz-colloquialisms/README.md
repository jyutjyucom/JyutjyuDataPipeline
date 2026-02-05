## 廣州話俗語詞典（gz-colloquialisms）

- **對應主項目 id**: `gz-colloquialisms`
- **主項目文件名**: `gz-colloquialisms.json`
- **最終 JSON 輸出路徑（喺主項目入面）**: `public/dictionaries/gz-colloquialisms.json`

### 數據來源同使用限制

- **數據來源**：**《廣州話俗語詞典》**，歐陽覺亞、周無忌、饒秉才編，廣東人民出版社，2010 年版。
- **版權同用途**：詞表內容受版權保護，係嚟自互聯網公開掃描資源，只係用嚟做呢個項目嘅原型驗證同技術示範，**唔可以**用作商業用途或者再分發（同主項目 `index.json` 入面嘅 `license` / `usage_restriction` 保持一致）。

### 呢個目錄入面主要嘅文件

- `0_廣州話俗語詞典.csv`：原始表格版本（結構化程度比較低）。
- `1_廣州話俗語詞典_updated.csv`：清洗／修訂之後嘅版本。
- `2_廣州話俗語詞典_粵拼.csv`：已經帶粵拼嘅版本。
- `convert_to_jyutping.py`：由原始／更新版生成帶粵拼數據嘅腳本。
- `update_index.py`：同索引或者統計相關嘅腳本。

### 建議嘅構建流程（示意）

1. 用 `convert_to_jyutping.py`（同／或者你之後加嘅腳本）喺呢個目錄入面生成最終認可嘅結構化表格（建議喺 `2_廣州話俗語詞典_粵拼.csv` 基礎上整理）。
2. 將最終表格提交／同步去主項目可以讀到嘅位置（例如俾主項目嘅腳本直接喺呢個倉庫讀嗰個 CSV）。
3. 喺主項目 `Jyutjyu` 入面運行 `scripts/adapters/gz-colloquialisms.js`：

   - 由最終嘅 CSV 讀數據；
   - 轉做符合主項目 `DictionaryEntry` 結構嘅 `DictionaryEntry[]`；
   - 寫入主項目倉庫嘅 `public/dictionaries/gz-colloquialisms.json`（文件名要同主項目 `index.json` 入面嘅 `file` 字段對應）。

呢個倉庫只係負責準備同維護 CSV／中間數據，出最終 JSON 嘅邏輯係放喺主項目嘅 `scripts/adapters/gz-colloquialisms.js` 入面。
