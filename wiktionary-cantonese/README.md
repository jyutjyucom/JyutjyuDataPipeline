## 維基詞典粵語數據（wiktionary-cantonese）

- **對應主項目 id**: `wiktionary-cantonese`
- **主項目文件名（整包 debug 用，可選）**: `wiktionary-cantonese.json`
- **主項目分片配置**：
  - `chunked: true`
  - `chunk_dir: "wiktionary"`
- **最終 JSON 輸出路徑（喺主項目入面）**：
  - （可選整包）`public/dictionaries/wiktionary-cantonese.json`
  - （主項目實際用）`public/dictionaries/wiktionary/manifest.json`
  - （主項目實際用）`public/dictionaries/wiktionary/<initial>.json`，例如 `a.json`、`b.json` 等

### 數據來源同使用限制

- **數據來源**：維基詞典（Wiktionary）入面同粵語有關嘅詞條，JSONL 檔係喺 kaik̈ki.org 等鏡像下載返嚟。
- **版權同用途**：數據遵守 **CC BY-SA 4.0** 牌照，使用同再分發嘅時候要跟 CC BY-SA 4.0 條款，並且正確寫明維基詞典貢獻者同維基媒體基金會（同主項目 `index.json` 入面嘅 `license`／`usage_restriction` 保持一致）。

### 呢個目錄入面主要嘅文件

- `kaikki.org-dictionary-Chinese.jsonl`：上游完整中文詞典嘅 JSONL（體積好大，建議當 raw 輸入）。
- `cantonese_entries.jsonl`：由上游數據篩出嚟嘅粵語詞條子集。
- `extract_cantonese.py`：喺上游 JSONL 入面抽粵語相關詞條。
- `analyze_cantonese.py`：對抽出嚟嘅粵語數據做統計同結構分析。
- `show_structure.py`、`structure_analysis.txt`、`README_詞條結構說明.md`：幫手理解 Wiktionary 詞條結構嘅說明同示例。

### 建議嘅構建流程（示意）

1. 用 `extract_cantonese.py` 喺 `kaikki.org-dictionary-Chinese.jsonl` 抽粵語相關詞條，生成 `cantonese_entries.jsonl`（淨係本地用，大文件唔建議入庫）。
2. 用 `analyze_cantonese.py`、`show_structure.py` 等腳本去理解同驗證結構，需要嘅話再派生中間 CSV／表格俾主項目用。
3. 將中間結果提交／同步去主項目可以讀到嘅位置（例如俾主項目腳本直接喺呢個倉庫讀 `cantonese_entries` 或者相應 CSV）。
4. 喺主項目 `Jyutjyu` 入面運行 `scripts/adapters/wiktionary-cantonese.js`（個名可以自定，但建議帶 `wiktionary` 呢個標識）：

   - 由中間結果讀數據；
   - 規範化成主項目用嘅 `DictionaryEntry[]` 結構；
   - 根據詞頭首字母（或者其他合適嘅 key）幫 `DictionaryEntry[]` 分片；
   - 寫分片 JSON 去 `public/dictionaries/wiktionary/<initial>.json`；
   - 生成 `public/dictionaries/wiktionary/manifest.json`，入面包含 `chunks`、`headwordIndex` 等主項目要用嘅 metadata；
   - 如果有需要，可以額外整一份整包 JSON `public/dictionaries/wiktionary-cantonese.json`（主要俾 debug 用）。

呢個倉庫只係負責準備同維護原始 JSONL 同必要嘅中間數據，真正嘅分片同 manifest 導出邏輯係放喺主項目嘅 `scripts/adapters/wiktionary-cantonese.js`（或者同類適配腳本）入面。
