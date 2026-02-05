"""
測試版本：驗證第一頁（page 48）的詞頭和粵拼正確性
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

# 測試配置：只處理第一頁
TEST_PAGE = 48


@dataclass
class DiscrepancyRecord:
    """記錄差異的數據類"""
    index: int
    headword: str
    ocr_jyutping: str
    api_jyutping: Optional[str]
    source_file: str
    page: int
    discrepancy_type: str
    definition: str = ""
    llm_verification: str = ""
    llm_suggestion: str = ""
    # 核對後的修正值
    verified_headword: str = ""  # 核對後的字頭（如有修改）
    verified_jyutping: str = ""  # 核對後的讀音（如有修改）
    verification_notes: str = ""  # 核對注釋


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
        print(f"  ⚠ API 查詢錯誤: {headword} - {e}")
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
    
    Returns:
        (is_match, matched_api_jyutping or None)
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


def verify_with_llm(discrepancies: list[DiscrepancyRecord]) -> list[DiscrepancyRecord]:
    """使用 LLM 核對差異"""
    if not discrepancies:
        print("沒有需要核對的差異")
        return discrepancies
    
    # 獲取該頁的圖片
    source_file = discrepancies[0].source_file
    page = discrepancies[0].page
    
    print(f"\n📡 使用 LLM 核對第 {page} 頁的 {len(discrepancies)} 個差異...")
    
    image_path = get_image_path(source_file)
    if not os.path.exists(image_path):
        print(f"  ⚠ 圖片不存在: {image_path}")
        return discrepancies
    
    try:
        base64_image = encode_image_to_base64(image_path)
        
        # 構建差異描述
        discrepancy_list = []
        for i, item in enumerate(discrepancies, 1):
            if item.discrepancy_type == "not_found":
                desc = f"{i}. 【{item.headword}】OCR讀音: {item.ocr_jyutping}\n   問題：API 未找到此字，可能是字頭 OCR 識別錯誤"
            else:
                desc = f"{i}. 【{item.headword}】OCR讀音: {item.ocr_jyutping} | API讀音: {item.api_jyutping}\n   問題：讀音不一致"
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

        print(f"  發送請求到 LLM...")
        
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
        
        print(f"\n📝 LLM 原始回覆:")
        print("-"*60)
        print(llm_result)
        print("-"*60)
        
        # 解析 LLM 回覆
        try:
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', llm_result)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = llm_result
            
            verifications = json.loads(json_str)
            
            # 建立映射時去掉【】符號，並建立簡繁體變體
            verification_map = {}
            for v in verifications:
                hw_ocr = v.get('headword_ocr', '')
                # 去掉【】符號
                hw_clean = hw_ocr.replace('【', '').replace('】', '').strip()
                verification_map[hw_clean] = v
                
                # 如果有 OpenCC，也添加簡繁轉換後的版本
                if HAS_OPENCC and hw_clean:
                    # 簡體轉繁體
                    hw_t = s2t_converter.convert(hw_clean)
                    if hw_t != hw_clean:
                        verification_map[hw_t] = v
                    # 繁體轉簡體
                    hw_s = t2s_converter.convert(hw_clean)
                    if hw_s != hw_clean:
                        verification_map[hw_s] = v
            
            for item in discrepancies:
                # 嘗試直接匹配
                matched_v = verification_map.get(item.headword)
                
                # 如果沒匹配到，嘗試簡繁轉換後匹配
                if not matched_v and HAS_OPENCC:
                    hw_t = s2t_converter.convert(item.headword)
                    hw_s = t2s_converter.convert(item.headword)
                    matched_v = verification_map.get(hw_t) or verification_map.get(hw_s)
                
                if matched_v:
                    v = matched_v
                    
                    hw_correct = v.get('headword_ocr_correct', True)
                    jp_correct = v.get('jyutping_ocr_correct', True)
                    
                    if hw_correct and jp_correct:
                        item.llm_verification = "正確"
                    elif not hw_correct:
                        item.llm_verification = "字頭錯誤"
                    else:
                        item.llm_verification = "讀音錯誤"
                    
                    # 提取核對後的修正值
                    correct_hw = v.get('headword_correct', '')
                    # 去掉【】符號
                    correct_hw = correct_hw.replace('【', '').replace('】', '').strip()
                    correct_jp = v.get('jyutping_correct', '')
                    notes = v.get('notes', '')
                    
                    # 設置核對後的字頭（如果有修改）
                    if not hw_correct and correct_hw:
                        item.verified_headword = correct_hw
                    
                    # 設置核對後的讀音（如果有修改）
                    if not jp_correct and correct_jp:
                        item.verified_jyutping = correct_jp
                    
                    # 設置核對注釋
                    item.verification_notes = notes
                    
                    # 也保留舊的 suggestion 格式
                    suggestions = []
                    if not hw_correct and correct_hw:
                        suggestions.append(f"正確字頭: {correct_hw}")
                    if not jp_correct and correct_jp:
                        suggestions.append(f"正確讀音: {correct_jp}")
                    if notes:
                        suggestions.append(notes)
                    item.llm_suggestion = " | ".join(suggestions) if suggestions else ""
                else:
                    item.llm_verification = "未核對"
                    
        except json.JSONDecodeError as e:
            print(f"  ⚠ JSON 解析失敗: {e}")
            for item in discrepancies:
                item.llm_verification = "解析失敗"
                item.llm_suggestion = llm_result[:200]
        
        print(f"\n✓ LLM 核對完成")
        
    except Exception as e:
        print(f"  ⚠ LLM 核對失敗: {e}")
        import traceback
        traceback.print_exc()
        for item in discrepancies:
            item.llm_verification = f"錯誤: {e}"
    
    return discrepancies


def save_verified_csv(original_data: list[dict], discrepancies: list[DiscrepancyRecord], output_file: str):
    """
    保存核對結果到新的 CSV 文件
    在原有列的基礎上新增：verified_headword, verified_jyutping, verification_notes
    """
    # 建立差異記錄的索引映射
    discrepancy_map = {d.index: d for d in discrepancies}
    
    # 確保輸出目錄存在
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        # 新的列標題
        fieldnames = [
            'index', 'headword', 'verified_headword',
            'pronunciation', 'verified_jyutping',
            'definition', 'page', 'source_file',
            'verification_status', 'verification_notes'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in original_data:
            idx = int(row.get('index', 0))
            
            # 檢查是否有對應的差異記錄
            if idx in discrepancy_map:
                d = discrepancy_map[idx]
                new_row = {
                    'index': idx,
                    'headword': d.headword,
                    'verified_headword': d.verified_headword if d.verified_headword else '',
                    'pronunciation': d.ocr_jyutping,
                    'verified_jyutping': d.verified_jyutping if d.verified_jyutping else '',
                    'definition': row.get('definition', ''),
                    'page': d.page,
                    'source_file': d.source_file,
                    'verification_status': d.llm_verification,
                    'verification_notes': d.verification_notes
                }
            else:
                # 沒有差異，表示 API 匹配成功
                new_row = {
                    'index': idx,
                    'headword': row.get('headword', ''),
                    'verified_headword': '',
                    'pronunciation': row.get('pronunciation', ''),
                    'verified_jyutping': '',
                    'definition': row.get('definition', ''),
                    'page': row.get('page', ''),
                    'source_file': row.get('source_file', ''),
                    'verification_status': 'API匹配',
                    'verification_notes': ''
                }
            
            writer.writerow(new_row)
    
    print(f"\n📄 已保存核對結果: {output_file}")


def main():
    """測試主函數"""
    print("="*80)
    print(f"測試版本：驗證第 {TEST_PAGE} 頁的詞條")
    print("="*80)
    
    # 檢查 API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ 錯誤: 請設置 OPENROUTER_API_KEY")
        return
    
    # 載入數據
    print(f"\n📂 載入 CSV 數據...")
    all_data = load_csv_data(CSV_FILE)
    
    # 只保留測試頁的數據
    data = [row for row in all_data if int(row.get('page', 0)) == TEST_PAGE]
    print(f"✓ 第 {TEST_PAGE} 頁共有 {len(data)} 條記錄")
    
    # 顯示該頁的所有詞條
    print(f"\n📋 第 {TEST_PAGE} 頁的詞條:")
    print("-"*60)
    for row in data:
        print(f"  【{row.get('headword', '')}】{row.get('pronunciation', '')}")
    print("-"*60)
    
    # 通過 API 查詢並比較
    print(f"\n📡 通過 API 查詢整個詞條並比較粵拼...")
    print(f"   (比較時會去除聲調撇號，如 baa1' → baa1)")
    
    not_found_records = []
    mismatch_records = []
    matched_records = []
    
    for row in data:
        headword = row.get('headword', '')
        ocr_jyutping = row.get('pronunciation', '')
        
        if not headword:
            continue
        
        # 查詢整個詞，不是只查第一個字
        matched_results = query_api_all_matches(headword)
        
        if not matched_results:
            print(f"  ❌ 未找到: 【{headword}】{ocr_jyutping}")
            not_found_records.append(DiscrepancyRecord(
                index=int(row.get('index', 0)),
                headword=headword,
                ocr_jyutping=ocr_jyutping,
                api_jyutping=None,
                source_file=row.get('source_file', ''),
                page=int(row.get('page', 0)),
                discrepancy_type="not_found",
                definition=row.get('definition', '')[:100]
            ))
        else:
            # 獲取所有匹配結果的粵拼
            api_jyutpings = get_all_jyutpings_from_results(matched_results)
            
            if api_jyutpings:
                # 比較 OCR 粵拼和所有 API 粵拼，只要有一個匹配就算正確
                is_match, matched_jp = compare_jyutping(ocr_jyutping, api_jyutpings)
                
                if is_match:
                    print(f"  ✓ 匹配: 【{headword}】{ocr_jyutping}")
                    matched_records.append(headword)
                else:
                    api_jp_display = " / ".join(api_jyutpings[:3])  # 最多顯示3個
                    if len(api_jyutpings) > 3:
                        api_jp_display += f" (+{len(api_jyutpings)-3}個)"
                    print(f"  ⚠ 不匹配: 【{headword}】OCR: {ocr_jyutping} vs API: {api_jp_display}")
                    mismatch_records.append(DiscrepancyRecord(
                        index=int(row.get('index', 0)),
                        headword=headword,
                        ocr_jyutping=ocr_jyutping,
                        api_jyutping=" / ".join(api_jyutpings),  # 保存所有 API 粵拼
                        source_file=row.get('source_file', ''),
                        page=int(row.get('page', 0)),
                        discrepancy_type="mismatch",
                        definition=row.get('definition', '')[:100]
                    ))
            else:
                print(f"  ⚠ API 無粵拼: 【{headword}】")
                not_found_records.append(DiscrepancyRecord(
                    index=int(row.get('index', 0)),
                    headword=headword,
                    ocr_jyutping=ocr_jyutping,
                    api_jyutping=None,
                    source_file=row.get('source_file', ''),
                    page=int(row.get('page', 0)),
                    discrepancy_type="not_found",
                    definition=row.get('definition', '')[:100]
                ))
        
        time.sleep(0.1)
    
    print(f"\n📊 API 查詢結果:")
    print(f"  - 完全匹配: {len(matched_records)}")
    print(f"  - 未找到:   {len(not_found_records)}")
    print(f"  - 不匹配:   {len(mismatch_records)}")
    
    all_discrepancies = not_found_records + mismatch_records
    
    if all_discrepancies:
        print(f"\n🔍 共 {len(all_discrepancies)} 個差異需要 LLM 核對")
        
        # 直接進行 LLM 核對（測試版本不詢問）
        verified = verify_with_llm(all_discrepancies)
        
        # 顯示結果
        print("\n" + "="*80)
        print("📋 LLM 核對結果:")
        print("="*80)
        
        for d in verified:
            status_icon = "✓" if d.llm_verification == "正確" else "✗"
            print(f"\n{status_icon} 【{d.headword}】")
            print(f"   OCR 讀音: {d.ocr_jyutping}")
            if d.api_jyutping:
                print(f"   API 讀音: {d.api_jyutping}")
            print(f"   差異類型: {d.discrepancy_type}")
            print(f"   LLM 判定: {d.llm_verification}")
            if d.verified_headword:
                print(f"   ✏️ 修正字頭: {d.verified_headword}")
            if d.verified_jyutping:
                print(f"   ✏️ 修正讀音: {d.verified_jyutping}")
            if d.verification_notes:
                print(f"   📝 注釋: {d.verification_notes}")
        
        # 保存核對結果到 CSV
        output_csv = f"./output/verification/page{TEST_PAGE}_verified.csv"
        save_verified_csv(data, verified, output_csv)
    else:
        verified = []
        print("\n✓ 所有詞條都匹配，無需 LLM 核對")
        
        # 即使全部匹配也保存 CSV
        output_csv = f"./output/verification/page{TEST_PAGE}_verified.csv"
        save_verified_csv(data, verified, output_csv)
    
    print("\n" + "="*80)
    print("測試完成！")
    print("="*80)


if __name__ == '__main__':
    main()
