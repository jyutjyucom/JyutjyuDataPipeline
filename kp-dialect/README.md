## 開平方言（kp-dialect）

- **對應主項目 id**: `kp-dialect`
- **主項目文件名**: `kp-dialect.json`
- **最終 JSON 輸出路徑（喺主項目入面）**: `public/dictionaries/kp-dialect.json`

### 數據來源同使用限制

- **數據來源**：**《開平方言》**，鄧鈞編，湖南電子音像出版社，2000 年版。
- **版權同用途**：詞表內容受版權保護，係嚟自互聯網公開掃描資源，只係用嚟做呢個項目嘅原型驗證同技術示範，**唔可以**用作商業用途或者再分發（同主項目 `index.json` 入面嘅 `license`／`usage_restriction` 保持一致）。

### 呢個目錄入面主要嘅文件

- `OCR_openrouter_kp-dialect.py`：調用 OCR 介面，生成呢本書嘅 OCR 文字或者圖像增強版本。
- `txt_to_csv_kp_dialect.py`：將文字形式嘅數據整理成 CSV。
- `convert_kaiping_ipa_to_jyutping.py`：將開平方言嘅國際音標轉成粵拼。
- `requirements.txt`：處理呢本書流程用到嘅依賴。

### 建議嘅構建流程（示意）

1. 視乎需要，用 `OCR_openrouter_kp-dialect.py` 同相關步驟喺本機生成 OCR 同中間結果（原始 PDF／圖片同 OCR 輸出都唔會入庫）。
2. 運行 `txt_to_csv_kp_dialect.py`，將原始或者 OCR 文字轉成結構化 CSV。
3. 運行 `convert_kaiping_ipa_to_jyutping.py`，幫詞條補充或者規範化粵拼。
4. 將最終表格提交／同步去主項目可以讀到嘅位置（例如俾主項目腳本直接喺呢個倉庫讀嗰個 CSV）。
5. 喺主項目 `Jyutjyu` 入面運行 `scripts/adapters/kp-dialect.js`：

   - 由最終 CSV 讀數據；
   - 轉做符合主項目 `DictionaryEntry` 結構嘅 `DictionaryEntry[]`；
   - 寫入主項目倉庫嘅 `public/dictionaries/kp-dialect.json`。

呢個倉庫只係負責準備同維護 CSV／中間數據，出最終 JSON 嘅邏輯係放喺主項目嘅 `scripts/adapters/kp-dialect.js` 入面。
