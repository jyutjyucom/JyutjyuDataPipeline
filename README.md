## JyutjyuDataPipeline

呢個倉庫用於存放各本粤语/方言词典嘅數據提取、清洗同導出腳本，目前按「每本書一個子目錄」組織，例如：

- `gz-dialect/`：廣州方言詞典
- `gz-modern/`：現代粵語詞典
- `gz-dict/`：廣州話詞典（第2版）
- `gz-colloquialisms/`：廣州話俗語詞典
- `gz-word-origins/`：粵語辭源
- `kp-dialect/`：開平方言
- `ts-english-dict/`：台山話英文字典
- `wiktionary-cantonese/`：維基詞典粵語數據

### 數據分層約定

- 原始 PDF、圖片等大型中間文件只喺本地生成，唔會進入 Git 倉庫。
- 每本書可以喺自己子目錄下維護中間 CSV/表格（例如 `*_粵拼.csv` 等）。
- 本倉庫嘅主要職責係：**為主項目準備好結構化、乾淨嘅中間數據（CSV/表格等）**，唔係直接生成主項目要用嘅 JSON。

### 與主項目 Jyutjyu 的對接

- 主項目 `Jyutjyu` 中，喺 `scripts/adapters/` 目錄下為每本詞典維護一個適配腳本，例如：

  - `scripts/adapters/gz-dict.js`
  - `scripts/adapters/gz-modern.js`
  - `scripts/adapters/gz-dialect.js`
  - `scripts/adapters/gz-colloquialisms.js`
  - …

- 呢啲適配腳本負責：

  1. 由本倉庫導出嘅 CSV / 中間表中讀取數據（例如 `gz-dict/`、`gz-modern/` 等目錄下嘅最終 CSV）。
  2. 生成符合主項目 `DictionaryEntry` 結構嘅 `DictionaryEntry[]` 或分片 JSON。
  3. 將 JSON 寫入主項目倉庫嘅 `public/dictionaries/` 目錄中，文件名同結構與主項目 `content/dictionaries/index.json` 中嘅 `file` / `chunk_dir` 對齊。
