"""
測試後端 API 格式，確保主驗證腳本能正確解析
"""

import requests
import json

API_BASE_URL = "http://localhost:3002/api/search"

def test_api():
    """測試 API 並顯示響應格式"""
    test_words = ["食", "巴", "閉", "孖"]
    
    print("="*80)
    print("測試後端 API 格式")
    print(f"API 端點: {API_BASE_URL}")
    print("="*80)
    
    for word in test_words:
        print(f"\n查詢: {word}")
        print("-"*40)
        
        try:
            url = f"{API_BASE_URL}?q={requests.utils.quote(word)}"
            response = requests.get(url, timeout=10)
            
            print(f"狀態碼: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"響應類型: {type(data).__name__}")
                
                # Pretty print JSON
                print("響應內容:")
                print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])
                
                # 嘗試識別字段
                if isinstance(data, list) and len(data) > 0:
                    first_item = data[0]
                    print(f"\n首個結果的字段: {list(first_item.keys())}")
                elif isinstance(data, dict):
                    if 'results' in data:
                        print(f"results 字段類型: {type(data['results']).__name__}")
                        if data['results'] and len(data['results']) > 0:
                            print(f"首個結果的字段: {list(data['results'][0].keys())}")
                    elif 'data' in data:
                        print(f"data 字段類型: {type(data['data']).__name__}")
                    else:
                        print(f"頂層字段: {list(data.keys())}")
            else:
                print(f"錯誤響應: {response.text[:500]}")
                
        except requests.exceptions.ConnectionError:
            print("❌ 連接失敗 - 請確保後端服務正在運行")
            print(f"   嘗試啟動服務或檢查端口 3002")
            return False
        except Exception as e:
            print(f"❌ 錯誤: {e}")
    
    print("\n" + "="*80)
    print("測試完成")
    print("="*80)
    print("\n根據上面的輸出，你可能需要調整 verify_jyutping.py 中的以下函數:")
    print("1. query_api() - 調整如何從響應中找到匹配的字頭")
    print("2. get_jyutping_from_api_result() - 調整如何提取 jyutping 字段")
    return True


if __name__ == '__main__':
    test_api()
