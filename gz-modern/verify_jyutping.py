"""
預處理第二步：驗證詞頭和粵拼正確性
1. 通過後端 API 查詢字頭，比較 jyutping
2. 使用 LLM 結合原圖片核對差異
3. 逐頁處理，每頁完成後立即更新 CSV
"""

import os
import csv
import json
import re
import base64
import time
import io
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image

# 嘗試導入 OpenCC 進行簡繁轉換
try:
    import opencc
    s2t_converter = opencc.OpenCC('s2t')  # 簡體轉繁體
    t2s_converter = opencc.OpenCC('t2s')  # 繁體轉簡體
    HAS_OPENCC = True
except ImportError:
    HAS_OPENCC = False
    print("⚠ 未安裝 opencc-python-reimplemented，簡繁轉換功能不可用")
    print("  安裝方式: pip install opencc-python-reimplemented")

# Load environment variables
load_dotenv()

# Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Configuration
API_BASE_URL = "http://localhost:3002/api/search"
CSV_FILE = "./output/廣州方言詞典_table.csv"
IMAGE_DIR = "./廣州方言詞典_preprocessed"
OUTPUT_DIR = "./output/verification"
OUTPUT_CSV = "./output/verification/廣州方言詞典_verified.csv"


@dataclass
class VerifiedRecord:
    """核對後的記錄"""
    index: int
    headword: str
    verified_headword: str  # 核對後的字頭（如有修改）
    pronunciation: str
    verified_jyutping: str  # 核對後的讀音（如有修改）
    definition: str
    page: int
    source_file: str
    verification_status: str  # "API匹配" | "正確" | "字頭錯誤" | "讀音錯誤" | "未核對"
    verification_notes: str


def normalize_jyutping(jyutping: str) -> str:
    """
    標準化 jyutping 以便比較
    - 去除 1' 中的撇號（陰平乙標記，其他詞典可能沒有）
    - 統一變調符號：* 和 - 都統一為 *
    - 統一為小寫
    - 移除多餘空格
    """
    if not jyutping:
        return ""
    normalized = " ".join(jyutping.split())
    # 去除所有撇號變體（1' -> 1）
    normalized = normalized.replace("ʼ", "").replace("'", "").replace("'", "")
    # 統一變調符號：其他詞典用 "-"，這部詞典用 "*"
    normalized = normalized.replace("-", "*")
    return normalized.lower().strip()


def query_api_all_matches(headword: str) -> list[dict]:
    """
    通過 API 查詢字頭，返回所有完全匹配的結果
    查詢整個詞，不是只查第一個字
    """
    try:
        url = f"{API_BASE_URL}?q={requests.utils.quote(headword)}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if not data.get('success', False):
                return []
            
            results = data.get('results', [])
            matched_results = []
            
            # 收集所有完全匹配字頭的結果
            for item in results:
                hw = item.get('headword', {})
                hw_display = hw.get('display', '') if isinstance(hw, dict) else hw
                hw_normalized = hw.get('normalized', '') if isinstance(hw, dict) else hw
                
                # 完全匹配字頭
                if hw_display == headword or hw_normalized == headword:
                    matched_results.append(item)
            
            return matched_results
        else:
            return []
            
    except Exception as e:
        return []


def get_all_jyutpings_from_results(results: list[dict]) -> list[str]:
    """
    從多個 API 結果中提取所有 jyutping
    注意：只使用 phonetic.jyutping 字段，不使用 phonetic.original
    因為 original 可能包含 IPA 格式（如 Wiktionary 的 /paː⁵⁵ pɐi̯³³/）
    """
    jyutpings = []
    
    for result in results:
        phonetic = result.get('phonetic', {})
        if phonetic:
            # 只使用 jyutping 字段，這是規整後的粵拼
            jyutping_list = phonetic.get('jyutping', [])
            if jyutping_list:
                for jp in jyutping_list:
                    if jp and jp not in jyutpings:
                        jyutpings.append(jp)
    
    return jyutpings


def compare_jyutping(ocr_jyutping: str, api_jyutpings: list[str]) -> tuple[bool, str]:
    """
    比較 OCR 粵拼和 API 粵拼列表
    只要有一個匹配就算正確
    """
    ocr_normalized = normalize_jyutping(ocr_jyutping)
    
    for api_jp in api_jyutpings:
        api_normalized = normalize_jyutping(api_jp)
        if ocr_normalized == api_normalized:
            return True, api_jp
    
    return False, api_jyutpings[0] if api_jyutpings else ""


def load_csv_data(csv_file: str) -> list[dict]:
    """載入 CSV 數據"""
    data = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def get_image_path(source_file: str) -> str:
    """根據 source_file 獲取圖片路徑"""
    return os.path.join(IMAGE_DIR, source_file)


def encode_image_to_base64(image_path: str) -> str:
    """將圖片編碼為 base64"""
    with Image.open(image_path) as img:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode('utf-8')


def build_llm_prompt(page: int, discrepancy_items: list[dict]) -> str:
    """構建 LLM 核對的 prompt"""
    # 構建差異描述
    discrepancy_list = []
    for i, item in enumerate(discrepancy_items, 1):
        if item['type'] == "not_found":
            desc = f"{i}. 【{item['headword']}】OCR讀音: {item['ocr_jyutping']}\n   問題：API 未找到此字，可能是字頭 OCR 識別錯誤"
        else:
            desc = f"{i}. 【{item['headword']}】OCR讀音: {item['ocr_jyutping']} | API讀音: {item['api_jyutping']}\n   問題：讀音不一致"
        discrepancy_list.append(desc)
    
    discrepancy_text = "\n".join(discrepancy_list)
    
    prompt = f"""你是粵語語言學專家，請幫我核對以下詞條。

這是《廣州方言詞典》第 {page} 頁的掃描圖片。以下是 OCR 識別結果中需要核對的詞條：

{discrepancy_text}

請根據圖片中的原文，對每個詞條進行核對：
1. **字頭核對**：確認 OCR 識別的字頭（【】內的字）是否正確
2. **讀音核對**：確認 OCR 識別的粵拼讀音是否正確

## ⚠️ 核心重點：讀音核對原則
**除非 OCR 讀音明顯錯誤，否則請維持原樣！**

你是在**核對**已完成的轉換，不是重新轉換。只有在以下情況下才需要修改：
1. OCR 轉換明顯錯誤（如聲母、韻母錯誤）
2. OCR 與圖片原文不一致
3. 存在技術性錯誤（如多音節詞少了一個讀音）

## 原書標音格式說明
原書使用**國際音標 IPA + 五度標記法**，OCR 已將其轉換為**粵拼 + 數字調號**。

你不需要重新進行 IPA→粵拼的轉換，只需要**核對轉換是否正確**。

## 粵拼格式規範（必須嚴格遵守）

### 1. 調號規則（最易出錯部分）
- **陰平甲 (高平調)**：`˥˥` → **`1`**（如：`siu1`）
- **陰平乙 (高降調)**：`˥˧` → **`1'`**（如：`siu1'`）
- ⚠️ 注意：這是**1後面加單引號**，不是數字7
- **陰上**：`˧˥` → **`2`**
- **陰去**：`˧˧` → **`3`**
- **陽平**：`˨˩` → **`4`**
- **陽上**：`˩˧` → **`5`**
- **陽去**：`˨˨` → **`6`**
- **上陰入**：`˥` → **`1`**（與陰平甲相同）
- **下陰入**：`˧` → **`3`**（與陰去相同）
- **陽入**：`˨` → **`6`**（與陽去相同）

### 轉換示例（原書IPA → 調值 → 粵拼調號）：
- 【巴閉】pa˥˧ pɐi˧˧ → pa53 pɐi33 → baa1' bai3
- 【豬頭骨】tsy˥˧ tʻɐu˨˩ kuɐt˥ → tsy53 tʻɐu21 kuɐt5 → zyu1' tau4 gwat1
- 【條】tʻiu˨˩ → tʻiu21 → tiu4
- 【竅】kʻiu˧˧˧˥ → kʻiu33*35 → kiu3*2（變調）

### ✅ 不需修改的情況：
1. OCR 轉換正確，即使與你記憶中的讀音不同
2. OCR 已正確使用 `1'` 標記高降調
3. 多音節詞的讀音連接方式（空格或連字符）與你習慣不同

請用以下 JSON 格式回覆：
```json
[
  {{
    "headword_ocr": "OCR識別的詞頭",
    "headword_correct": "正確的詞頭（如果OCR錯誤則填正確的，否則與OCR相同）",
    "headword_ocr_correct": true/false,
    "jyutping_ocr": "OCR識別的讀音",
    "jyutping_correct": "正確的粵拼讀音（必須是粵拼格式，不是IPA格式）",
    "jyutping_ocr_correct": true/false,
    "notes": "備註說明（可選）"
  }}
]
```"""
    return prompt


def verify_page_with_llm(page: int, source_file: str, discrepancy_items: list[dict]) -> dict:
    """
    使用 LLM 核對單頁的差異
    返回 headword -> verification 的映射
    """
    image_path = get_image_path(source_file)
    if not os.path.exists(image_path):
        print(f"  ⚠ 圖片不存在: {image_path}")
        return {}
    
    try:
        base64_image = encode_image_to_base64(image_path)
        prompt = build_llm_prompt(page, discrepancy_items)
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
        
        response = client.chat.completions.create(
            model="google/gemini-3-flash-preview",
            messages=messages,
        )
        
        llm_result = response.choices[0].message.content if response.choices[0].message.content else ""
        
        # 解析 LLM 回覆
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', llm_result)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = llm_result
        
        verifications = json.loads(json_str)
        
        # 建立映射，處理簡繁體
        verification_map = {}
        for v in verifications:
            hw_ocr = v.get('headword_ocr', '')
            hw_clean = hw_ocr.replace('【', '').replace('】', '').strip()
            verification_map[hw_clean] = v
            
            if HAS_OPENCC and hw_clean:
                hw_t = s2t_converter.convert(hw_clean)
                if hw_t != hw_clean:
                    verification_map[hw_t] = v
                hw_s = t2s_converter.convert(hw_clean)
                if hw_s != hw_clean:
                    verification_map[hw_s] = v
        
        return verification_map
        
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON 解析失敗: {e}")
        return {}
    except Exception as e:
        print(f"  ⚠ LLM 核對失敗: {e}")
        return {}


def process_verification_result(headword: str, verification_map: dict) -> tuple[str, str, str, str]:
    """
    處理單個詞條的驗證結果
    返回: (verified_headword, verified_jyutping, verification_status, verification_notes)
    """
    # 嘗試匹配
    matched_v = verification_map.get(headword)
    
    if not matched_v and HAS_OPENCC:
        hw_t = s2t_converter.convert(headword)
        hw_s = t2s_converter.convert(headword)
        matched_v = verification_map.get(hw_t) or verification_map.get(hw_s)
    
    if matched_v:
        hw_correct = matched_v.get('headword_ocr_correct', True)
        jp_correct = matched_v.get('jyutping_ocr_correct', True)
        
        if hw_correct and jp_correct:
            status = "正確"
        elif not hw_correct:
            status = "字頭錯誤"
        else:
            status = "讀音錯誤"
        
        correct_hw = matched_v.get('headword_correct', '')
        correct_hw = correct_hw.replace('【', '').replace('】', '').strip()
        correct_jp = matched_v.get('jyutping_correct', '')
        notes = matched_v.get('notes', '')
        
        verified_hw = correct_hw if not hw_correct and correct_hw else ''
        verified_jp = correct_jp if not jp_correct and correct_jp else ''
        
        return verified_hw, verified_jp, status, notes
    else:
        return '', '', '未核對', ''


def initialize_output_csv(output_file: str):
    """初始化輸出 CSV 文件"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'index', 'headword', 'verified_headword',
            'pronunciation', 'verified_jyutping',
            'definition', 'page', 'source_file',
            'verification_status', 'verification_notes'
        ])


def append_to_output_csv(output_file: str, records: list[VerifiedRecord]):
    """追加記錄到輸出 CSV"""
    with open(output_file, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for r in records:
            writer.writerow([
                r.index, r.headword, r.verified_headword,
                r.pronunciation, r.verified_jyutping,
                r.definition, r.page, r.source_file,
                r.verification_status, r.verification_notes
            ])


def process_single_page(page: int, page_data: list[dict]) -> list[VerifiedRecord]:
    """
    處理單頁的完整流程：
    1. 查詢 API
    2. 詢問 LLM（如有差異）
    3. 生成核對記錄
    """
    source_file = page_data[0].get('source_file', '')
    print(f"\n{'='*60}")
    print(f"處理第 {page} 頁 ({len(page_data)} 個詞條)")
    print(f"{'='*60}")
    
    verified_records = []
    discrepancy_items = []  # 需要 LLM 核對的項目
    
    # 第一步：查詢 API
    print(f"  📡 查詢 API...")
    for row in page_data:
        headword = row.get('headword', '')
        ocr_jyutping = row.get('pronunciation', '')
        
        if not headword:
            continue
        
        # 查詢整個詞
        matched_results = query_api_all_matches(headword)
        
        if not matched_results:
            # API 未找到
            discrepancy_items.append({
                'row': row,
                'headword': headword,
                'ocr_jyutping': ocr_jyutping,
                'api_jyutping': None,
                'type': 'not_found'
            })
        else:
            api_jyutpings = get_all_jyutpings_from_results(matched_results)
            
            if api_jyutpings:
                is_match, matched_jp = compare_jyutping(ocr_jyutping, api_jyutpings)
                
                if is_match:
                    # API 匹配成功
                    verified_records.append(VerifiedRecord(
                        index=int(row.get('index', 0)),
                        headword=headword,
                        verified_headword='',
                        pronunciation=ocr_jyutping,
                        verified_jyutping='',
                        definition=row.get('definition', ''),
                        page=page,
                        source_file=source_file,
                        verification_status='API匹配',
                        verification_notes=''
                    ))
                else:
                    # 讀音不匹配
                    discrepancy_items.append({
                        'row': row,
                        'headword': headword,
                        'ocr_jyutping': ocr_jyutping,
                        'api_jyutping': ' / '.join(api_jyutpings),
                        'type': 'mismatch'
                    })
            else:
                discrepancy_items.append({
                    'row': row,
                    'headword': headword,
                    'ocr_jyutping': ocr_jyutping,
                    'api_jyutping': None,
                    'type': 'not_found'
                })
        
        time.sleep(0.05)  # 避免 API 速率限制
    
    api_matched = len(verified_records)
    api_discrepancy = len(discrepancy_items)
    print(f"  ✓ API 匹配: {api_matched}, 需核對: {api_discrepancy}")
    
    # 第二步：如有差異，詢問 LLM
    if discrepancy_items:
        print(f"  📡 詢問 LLM 核對 {len(discrepancy_items)} 個差異...")
        verification_map = verify_page_with_llm(page, source_file, discrepancy_items)
        
        # 處理差異項目
        for item in discrepancy_items:
            row = item['row']
            headword = item['headword']
            
            verified_hw, verified_jp, status, notes = process_verification_result(
                headword, verification_map
            )
            
            verified_records.append(VerifiedRecord(
                index=int(row.get('index', 0)),
                headword=headword,
                verified_headword=verified_hw,
                pronunciation=item['ocr_jyutping'],
                verified_jyutping=verified_jp,
                definition=row.get('definition', ''),
                page=page,
                source_file=source_file,
                verification_status=status,
                verification_notes=notes
            ))
        
        # 統計核對結果
        llm_correct = sum(1 for r in verified_records if r.verification_status == '正確')
        llm_hw_error = sum(1 for r in verified_records if r.verification_status == '字頭錯誤')
        llm_jp_error = sum(1 for r in verified_records if r.verification_status == '讀音錯誤')
        llm_not_verified = sum(1 for r in verified_records if r.verification_status == '未核對')
        
        print(f"  ✓ LLM 核對完成: 正確={llm_correct}, 字頭錯誤={llm_hw_error}, 讀音錯誤={llm_jp_error}, 未核對={llm_not_verified}")
    
    # 按 index 排序
    verified_records.sort(key=lambda x: x.index)
    
    return verified_records


def main():
    """主執行函數"""
    print("="*80)
    print("廣州方言詞典 OCR 驗證腳本")
    print("逐頁處理：查詢API → 詢問LLM → 更新CSV")
    print("="*80)
    
    # 檢查 API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your_openrouter_api_key_here":
        print("❌ 錯誤: 請在 .env 文件中設置 OPENROUTER_API_KEY")
        return
    
    # 檢查 CSV 文件
    if not os.path.exists(CSV_FILE):
        print(f"❌ 錯誤: CSV 文件不存在 - {CSV_FILE}")
        return
    
    # 載入數據
    print(f"\n📂 載入 CSV 數據: {CSV_FILE}")
    all_data = load_csv_data(CSV_FILE)
    print(f"✓ 載入 {len(all_data)} 條記錄")
    
    # 按頁碼分組
    pages_data = {}
    for row in all_data:
        page = int(row.get('page', 0))
        if page not in pages_data:
            pages_data[page] = []
        pages_data[page].append(row)
    
    sorted_pages = sorted(pages_data.keys())
    print(f"✓ 共 {len(sorted_pages)} 頁 (第 {sorted_pages[0]} 頁 - 第 {sorted_pages[-1]} 頁)")
    
    # 詢問處理範圍
    print(f"\n請輸入要處理的頁碼範圍:")
    start_page = int(input(f"  起始頁碼 (默認 {sorted_pages[0]}): ").strip() or sorted_pages[0])
    end_page = int(input(f"  結束頁碼 (默認 {sorted_pages[-1]}): ").strip() or sorted_pages[-1])
    
    pages_to_process = [p for p in sorted_pages if start_page <= p <= end_page]
    print(f"\n將處理 {len(pages_to_process)} 頁 (第 {start_page} 頁 - 第 {end_page} 頁)")
    
    # 初始化輸出 CSV
    initialize_output_csv(OUTPUT_CSV)
    print(f"\n📄 輸出文件: {OUTPUT_CSV}")
    
    # 統計
    total_records = 0
    total_api_matched = 0
    total_llm_correct = 0
    total_hw_error = 0
    total_jp_error = 0
    total_not_verified = 0
    
    # 逐頁處理
    for page_idx, page in enumerate(pages_to_process, 1):
        print(f"\n[{page_idx}/{len(pages_to_process)}]", end="")
        
        page_data = pages_data[page]
        verified_records = process_single_page(page, page_data)
        
        # 追加到 CSV
        append_to_output_csv(OUTPUT_CSV, verified_records)
        print(f"  📄 已保存第 {page} 頁 ({len(verified_records)} 條記錄)")
        
        # 更新統計
        total_records += len(verified_records)
        total_api_matched += sum(1 for r in verified_records if r.verification_status == 'API匹配')
        total_llm_correct += sum(1 for r in verified_records if r.verification_status == '正確')
        total_hw_error += sum(1 for r in verified_records if r.verification_status == '字頭錯誤')
        total_jp_error += sum(1 for r in verified_records if r.verification_status == '讀音錯誤')
        total_not_verified += sum(1 for r in verified_records if r.verification_status == '未核對')
        
        # 避免 LLM API 速率限制
        time.sleep(0.5)
    
    # 最終統計
    print("\n" + "="*80)
    print("驗證完成！")
    print("="*80)
    print(f"\n📊 統計結果:")
    print(f"  總記錄數: {total_records}")
    print(f"  API 匹配: {total_api_matched} ({total_api_matched/total_records*100:.1f}%)")
    print(f"  LLM 確認正確: {total_llm_correct}")
    print(f"  字頭錯誤: {total_hw_error}")
    print(f"  讀音錯誤: {total_jp_error}")
    print(f"  未核對: {total_not_verified}")
    print(f"\n📄 輸出文件: {OUTPUT_CSV}")


if __name__ == '__main__':
    main()
