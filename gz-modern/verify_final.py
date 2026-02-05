"""
现代粤语词典粵拼最終校對腳本
1. 查詢 API 獲取建議的粵拼
2. 在原有粵拼列右邊新增 API 建議列
3. 如無匹配提示可能是字頭問題
"""

import csv
import time
import requests
import re
from pathlib import Path
from collections import defaultdict

# 嘗試導入 OpenCC 進行簡繁轉換
try:
    import opencc
    s2t_converter = opencc.OpenCC('s2t')  # 簡體轉繁體
    HAS_OPENCC = True
    print("✓ OpenCC 簡繁轉換功能已啟用")
except ImportError:
    HAS_OPENCC = False
    print("⚠ 未安裝 opencc-python-reimplemented，將直接使用原字頭查詢")
    print("  建議安裝: pip install opencc-python-reimplemented")


# Configuration
API_BASE_URL = "http://localhost:3002/api/search"
INPUT_CSV = "./现代粤语词典_table_粤拼.csv"
OUTPUT_CSV = "./现代粤语词典_table_粤拼_已校对.csv"


def clean_headword(headword: str) -> str:
    """
    清理字頭，移除標注符號
    - 移除方括號及其內容：柏［栢］ -> 柏
    - 移除圓括號及其內容：摆（擺） -> 摆
    - 移除數字標記：摆1 -> 摆
    - 移除其他特殊符號
    """
    if not headword:
        return ""
    
    # 移除方括號及其內容（全角和半角）
    cleaned = re.sub(r'[［\[].*?[］\]]', '', headword)
    
    # 移除圓括號及其內容（全角和半角）
    cleaned = re.sub(r'[（(].*?[）)]', '', cleaned)
    
    # 移除數字標記（用於區分多義項的上標數字）
    cleaned = re.sub(r'\d+', '', cleaned)
    
    # 移除其他可能的特殊符號
    cleaned = cleaned.strip()
    
    return cleaned


def normalize_jyutping(jyutping: str) -> str:
    """
    標準化 jyutping 以便比較
    - 去除 1' 中的撇號（陰平乙標記，其他詞典可能沒有）
    - 移除變調標記：數字 + (* 或 - 號)（如 jyu1*2 -> jyu2，因為現代粵語詞典只標注最終聲調）
    - 統一為小寫
    - 移除多餘空格
    """
    if not jyutping:
        return ""
    
    normalized = " ".join(jyutping.split())
    
    # 去除所有撇號變體（1' -> 1）
    normalized = normalized.replace("ʼ", "").replace("'", "").replace("'", "")
    
    # 移除變調標記：數字 + (* 或 - 號)，保留變調後的數字
    # 例如：jyu1*2 -> jyu2, tiu4-2 -> tiu2
    normalized = re.sub(r'\d+[*\-]', '', normalized)
    
    return normalized.lower().strip()


def query_api_all_matches(headword: str) -> list[dict]:
    """
    通過 API 查詢字頭，返回所有完全匹配的結果
    注意：
    1. 先清理字頭（移除括號、數字等標注）
    2. 現代粵語詞典使用簡體字，需要轉換為繁體後查詢
    """
    try:
        # 先清理字頭
        cleaned_headword = clean_headword(headword)
        if not cleaned_headword:
            return []
        
        # 將簡體字頭轉換為繁體
        query_headword = cleaned_headword
        if HAS_OPENCC:
            query_headword = s2t_converter.convert(cleaned_headword)
        
        url = f"{API_BASE_URL}?q={requests.utils.quote(query_headword)}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if not data.get('success', False):
                return []
            
            results = data.get('results', [])
            matched_results = []
            
            # 收集所有完全匹配字頭的結果
            # 需要同時匹配簡體和繁體（使用清理後的字頭）
            for item in results:
                hw = item.get('headword', {})
                hw_display = hw.get('display', '') if isinstance(hw, dict) else hw
                hw_normalized = hw.get('normalized', '') if isinstance(hw, dict) else hw
                
                # 完全匹配字頭（簡體或繁體的清理版本）
                if (hw_display == cleaned_headword or hw_normalized == cleaned_headword or
                    hw_display == query_headword or hw_normalized == query_headword):
                    matched_results.append(item)
            
            return matched_results
        else:
            return []
            
    except Exception as e:
        print(f"  ⚠ API 查詢錯誤: {e}")
        return []


def get_all_jyutpings_from_results(results: list[dict]) -> list[str]:
    """
    從多個 API 結果中提取所有 jyutping
    只使用 phonetic.jyutping 字段
    """
    jyutpings = []
    
    for result in results:
        phonetic = result.get('phonetic', {})
        if phonetic:
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
    返回: (是否匹配, 建議的粵拼)
    """
    if not api_jyutpings:
        return False, ""
    
    ocr_normalized = normalize_jyutping(ocr_jyutping)
    
    for api_jp in api_jyutpings:
        api_normalized = normalize_jyutping(api_jp)
        if ocr_normalized == api_normalized:
            return True, api_jp
    
    # 沒有匹配，返回第一個建議
    return False, api_jyutpings[0]


def process_row(row: dict) -> tuple[str, str]:
    """
    處理單行數據
    返回: (API建議的粵拼, 狀態說明)
    """
    headword = row.get('headword', '').strip()
    current_jyutping = row.get('jyutping', '').strip()
    
    if not headword:
        return "", "無字頭"
    
    # 查詢 API
    matched_results = query_api_all_matches(headword)
    
    if not matched_results:
        # API 未找到，可能是字頭有問題
        return "", "⚠️ API未找到，請檢查字頭"
    
    # 獲取所有粵拼
    api_jyutpings = get_all_jyutpings_from_results(matched_results)
    
    if not api_jyutpings:
        return "", "⚠️ API無粵拼數據"
    
    # 比較粵拼
    is_match, suggested_jp = compare_jyutping(current_jyutping, api_jyutpings)
    
    if is_match:
        # 完全匹配
        return suggested_jp, "✓ 匹配"
    else:
        # 不匹配，提供建議
        all_suggestions = " / ".join(api_jyutpings)
        return all_suggestions, "建議"
    
    # 避免 API 速率限制
    time.sleep(0.05)


def process_page(page_num: int, page_rows: list[dict], fieldnames: list[str], 
                output_file: str, is_first_page: bool) -> dict:
    """
    處理單頁數據
    返回: 本頁統計結果
    """
    page_stats = {
        'matched': 0,
        'suggested': 0,
        'not_found': 0,
        'no_data': 0,
        'no_headword': 0
    }
    
    results = []
    total = len(page_rows)
    
    print(f"\n{'='*60}")
    print(f"📄 處理第 {page_num} 頁 ({total} 條記錄)")
    print(f"{'='*60}")
    
    for i, row in enumerate(page_rows, 1):
        headword = row.get('headword', '').strip()
        
        # 顯示進度
        if i % 10 == 0 or i == total:
            print(f"  進度: {i}/{total} ({i/total*100:.0f}%) - 當前: {headword}")
        
        api_suggestion, status = process_row(row)
        
        # 更新統計
        if status == "✓ 匹配":
            page_stats['matched'] += 1
        elif status == "建議":
            page_stats['suggested'] += 1
        elif status == "⚠️ API未找到，請檢查字頭":
            page_stats['not_found'] += 1
        elif status == "⚠️ API無粵拼數據":
            page_stats['no_data'] += 1
        elif status == "無字頭":
            page_stats['no_headword'] += 1
        
        # 添加新欄位
        new_row = row.copy()
        new_row['api_suggestion'] = api_suggestion
        new_row['verification_status'] = status
        results.append(new_row)
    
    # 寫入本頁結果
    mode = 'w' if is_first_page else 'a'
    with open(output_file, mode, encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if is_first_page:
            writer.writeheader()
        writer.writerows(results)
    
    # 顯示本頁統計
    print(f"\n  本頁統計:")
    print(f"    ✓ 匹配: {page_stats['matched']}")
    print(f"    建議: {page_stats['suggested']}")
    print(f"    ⚠️ 未找到: {page_stats['not_found']}")
    print(f"    ⚠️ 無數據: {page_stats['no_data']}")
    print(f"  ✅ 第 {page_num} 頁已保存")
    
    return page_stats


def main():
    """主執行函數"""
    print("="*80)
    print("現代粵語詞典粵拼最終校對腳本")
    print("按頁處理，實時輸出結果")
    print("="*80)
    
    # 檢查輸入文件
    if not Path(INPUT_CSV).exists():
        print(f"❌ 錯誤: 輸入文件不存在 - {INPUT_CSV}")
        return
    
    print(f"\n📂 讀取文件: {INPUT_CSV}")
    
    # 讀取 CSV 並按頁分組
    pages_data = defaultdict(list)
    fieldnames = None
    
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        
        for row in reader:
            page_num = int(row.get('page', 0))
            pages_data[page_num].append(row)
    
    total_rows = sum(len(rows) for rows in pages_data.values())
    sorted_pages = sorted(pages_data.keys())
    
    print(f"✓ 共 {total_rows} 條記錄")
    print(f"✓ 共 {len(sorted_pages)} 頁 (第 {sorted_pages[0]} 頁 - 第 {sorted_pages[-1]} 頁)")
    
    # 新增欄位名
    new_fieldnames = fieldnames.copy()
    jyutping_idx = new_fieldnames.index('jyutping')
    new_fieldnames.insert(jyutping_idx + 1, 'api_suggestion')
    new_fieldnames.insert(jyutping_idx + 2, 'verification_status')
    
    print(f"\n📄 輸出文件: {OUTPUT_CSV}")
    print(f"\n📡 開始逐頁查詢 API...")
    
    # 總統計
    total_stats = {
        'matched': 0,
        'suggested': 0,
        'not_found': 0,
        'no_data': 0,
        'no_headword': 0
    }
    
    # 逐頁處理
    for idx, page_num in enumerate(sorted_pages):
        is_first_page = (idx == 0)
        page_rows = pages_data[page_num]
        
        page_stats = process_page(
            page_num, 
            page_rows, 
            new_fieldnames, 
            OUTPUT_CSV, 
            is_first_page
        )
        
        # 累加統計
        for key in total_stats:
            total_stats[key] += page_stats[key]
        
        # 顯示累計進度
        processed_rows = sum(len(pages_data[p]) for p in sorted_pages[:idx+1])
        print(f"\n  累計進度: {idx+1}/{len(sorted_pages)} 頁, "
              f"{processed_rows}/{total_rows} 條記錄 ({processed_rows/total_rows*100:.1f}%)")
        
        # 避免 API 速率限制
        time.sleep(0.2)
    
    # 顯示最終統計
    print("\n" + "="*80)
    print("校對完成！")
    print("="*80)
    print(f"\n📊 最終統計:")
    print(f"  總記錄數: {total_rows}")
    print(f"  ✓ API 匹配: {total_stats['matched']} ({total_stats['matched']/total_rows*100:.1f}%)")
    print(f"  建議修改: {total_stats['suggested']} ({total_stats['suggested']/total_rows*100:.1f}%)")
    print(f"  ⚠️ API 未找到: {total_stats['not_found']} ({total_stats['not_found']/total_rows*100:.1f}%)")
    print(f"  ⚠️ API 無數據: {total_stats['no_data']} ({total_stats['no_data']/total_rows*100:.1f}%)")
    print(f"  無字頭: {total_stats['no_headword']}")
    
    print(f"\n📄 輸出文件: {OUTPUT_CSV}")
    print("\n說明:")
    print("  - api_suggestion 列: API 建議的粵拼")
    print("  - verification_status 列:")
    print("    * ✓ 匹配: 當前粵拼與 API 完全匹配（已移除變調標記比較）")
    print("    * 建議: API 有不同建議，請核對")
    print("    * ⚠️ API未找到: 可能字頭有誤，請檢查")
    print("    * ⚠️ API無粵拼數據: API 找到詞條但無粵拼")


if __name__ == '__main__':
    main()
