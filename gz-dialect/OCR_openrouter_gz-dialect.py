"""
OCR script for 廣州方言詞典 using OpenRouter API with Google Gemini 3 Pro Preview
Processes images 48-553 (inclusive) from the preprocessed directory
"""

import os
import base64
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image
import io

# Load environment variables
load_dotenv()

# Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Configuration for 廣州方言詞典
name_lang = '''粵語'''
name_lit = '''廣州方言詞典'''
req_extra_1 = '詞條偶爾會有字號偏小的釋義附著在例句之後，你需要用"<"">"來標記他們。'
setting_symble_tone = '''聲調記法是五度法，使用符號"˥、˦、˧、˨、˩"，文中顯示會將兩個符號連寫來表示非平調'''
setting_info_tone = '''但是，该符号使用不便，你應使用數字轉寫來寫调值。廣州話聲調調值是：陰平甲: 55(˥˥); 陰平乙: 53(˥˧); 陰上: 35(˧˥); 陰去: 33(˧˧); 陽平: 21(˨˩); 陽上: 13(˩˧); 陽去: 22(˨˨); 上陰入: 5(˥); 下陰入: 3(˧); 陽入: 2(˨)。文中變調的表達方式是先寫原調，後寫變調，但你紀錄下來的兩個調之間要加變調符號"*"'''
ex_1 = '''【巴閉】pa53 pɐi33 ①副詞。表程度加深加重或嚴重、緊張等（含有極力鋪張、渲染、小題大作的色彩）：家下都冇野咯，你使乜講得咁～啊！丨嘈喧～嘈雜聲吵得不得了 ②興師動眾：你自己做都得喇，使乜咁～啊！
'''
ex_2 = '''【豬頭骨】tsy53 tʻɐu21 kuɐt5 ①豬的頭骨，是豬骨中最差的部分 ②喻無利可圖的事，沒有油水的買賣：呢件事正～來嘅丨㖮[løn53]<啃>～<喻幹沒有油水的買賣>
'''
ex_3 = '''【條】tʻiu21 ①量詞。A)用於長形之物：一～棍丨開～支票 B)用於抽象事物：想～計仔<計策>丨恁～竅[kʻiu33*35]<想個法子>丨䏱住～氣<憋着一肚子氣> C)用於人：呢～友仔丨凈係我一～友喺處<就是我一個人在這兒>'''

# Build system prompt
system_prompt = f"""
你將擔任{name_lang}詞典《{name_lit}》電子化的工作，你將看到其中頁面的截圖，你隨之將其中的内容寫出來。
注意及要求：
- 內容包含國際音標IPA，{setting_symble_tone}。
- {setting_info_tone}
- 如果實在看不清原文的聲調，請以你自己的粵語知識來判斷該字的聲調。
- 內容可能包含罕見漢字，Unicode 未錄入的漢字需要使用表意文字描述序列（IDS）來表示；有些字頭沒有寫漢字，而使用了"□"，你應也寫一個"□"
- {req_extra_1}
- 圖中未截取到的前文或後文你不能擅自補充，除了上面我要求的處理的格式需要到的情況
這裏是三個例子：
{ex_1}{ex_2}{ex_3}
""".strip()


def encode_image_to_base64(image_path: str) -> str:
    """
    Encode image to base64 string for API transmission
    """
    with Image.open(image_path) as img:
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Save to bytes buffer
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Encode to base64
        return base64.b64encode(buffer.read()).decode('utf-8')


def process_image_with_openrouter(image_path: str) -> tuple[str, str]:
    """
    Process a single image using two-stage approach:
    1. Flash model for initial OCR
    2. Flash model for IPA to Jyutping conversion
    
    Returns:
        tuple: (generated_text, metadata_text)
    """
    try:
        # Encode image
        base64_image = encode_image_to_base64(image_path)
        
        # ========== Stage 1: Flash model for initial OCR ==========
        messages_flash = [
            {
                "role": "system",
                "content": system_prompt
            },
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
                        "text": "請根據系統提示處理這張圖片。"
                    }
                ]
            }
        ]
        
        response_flash = client.chat.completions.create(
            model="google/gemini-3-flash-preview",
            messages=messages_flash,
        )
        
        flash_result = response_flash.choices[0].message.content if response_flash.choices[0].message.content else ""
        usage_flash = response_flash.usage
        
        # ========== Stage 2: Flash model for IPA to Jyutping conversion ==========
        conversion_prompt = f"""你現在需要將以下 OCR 結果轉換為香港語言學學會粵語拼音（jyutping）標音。

核心要求：
1. **優先根據漢字反推粵語讀音**：作為粵語專家，請根據詞條中的漢字來判斷正確的粵語發音，而不是機械地轉換 IPA
2. 保持所有漢字、標點符號、格式標記（【】、<>、丨等）完全不變
3. 將原文的 IPA + 調值標音 轉換為 香港語言學學會粵語拼音（jyutping）+ 調號

聲調轉換（調值 → 調號）：
- 55 → 1 (陰平甲)
- 53 → 1' (陰平乙，注意是 1 加撇號)
- 35 → 2 (陰上) 
- 33 → 3 (陰去)
- 21 → 4 (陽平)
- 13 → 5 (陽上)
- 22 → 6 (陽去)
- 5 → 1 (上陰入)
- 3 → 3 (下陰入)
- 2 → 6 (陽入)
- 變調保留 * 標記（如：33*35 → 3*2）

粵拼拼寫規則（香港語言學學會方案）：
- 聲母：b, p, m, f, d, t, n, l, g, k, ng, h, gw, kw, w, z, c, s, j
- 韻母：
  * 單韻母：aa, a, e, i, o, u, yu, oe, eo
  * 複韻母：aai, ai, aau, au, ei, eoi, iu, oi, ou, ui
  * 鼻音韻尾：aam, am, aan, an, aang, ang, em, en, eng, im, in, ing, on, ong, un, ung, yun, yung, oen, oeng
  * 塞音韻尾：aap, ap, aat, at, aak, ak, ep, et, ek, ip, it, ik, op, ot, ok, up, ut, uk, yut, oet, oek
  * 成音節鼻音：m, ng

轉換示例：
- pa53 pɐi33 → baa1' baai3（注意：53 要寫成 1'）
- tsy53 tʻɐu21 kuɐt5 → zyu1' tau4 gwat1
- tʻiu21 → tiu4
- kʻiu33*35 → kiu3*2
- pa55 → baa1（55 寫成 1）

工作流程：
1. 識別每個詞條的漢字
2. 根據漢字判斷其標準粵語讀音
3. 將讀音寫成香港語言學學會粵語拼音
4. 將調值轉換為調號（1-6）
5. 如果 IPA 明顯錯誤，以漢字讀音為準

OCR 原始結果：
{flash_result}

請輸出轉換後的結果，格式與原文完全一致，只是音標變為粵拼+調號。"""

        messages_conversion = [
            {
                "role": "user",
                "content": conversion_prompt
            }
        ]
        
        response_conversion = client.chat.completions.create(
            model="google/gemini-3-flash-preview",
            messages=messages_conversion,
        )
        
        final_result = response_conversion.choices[0].message.content if response_conversion.choices[0].message.content else ""
        usage_conversion = response_conversion.usage
        
        # Build metadata string
        total_tokens = usage_flash.total_tokens + usage_conversion.total_tokens
        metadata_text = f"<Two-Stage Token Count: {total_tokens} | "
        metadata_text += f"[Flash OCR: {usage_flash.total_tokens} (P:{usage_flash.prompt_tokens} C:{usage_flash.completion_tokens})] + "
        metadata_text += f"[Flash Conversion: {usage_conversion.total_tokens} (P:{usage_conversion.prompt_tokens} C:{usage_conversion.completion_tokens})]>"
        
        return final_result, metadata_text
        
    except Exception as e:
        print(f"處理圖片 {image_path} 時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return "", f"錯誤: {e}"


def process_folder_and_save_to_txt(image_root: str, output_file: str, start_idx: int = 48, end_idx: int = 553):
    """
    Process images in the specified range and save results to a text file
    Real-time saving: each page is saved immediately after processing
    
    Args:
        image_root: Path to the folder containing preprocessed images
        output_file: Path to save the output text file
        start_idx: Starting image index (inclusive)
        end_idx: Ending image index (inclusive)
    """
    # Ensure image folder exists
    if not os.path.isdir(image_root):
        print(f"錯誤：圖片資料夾不存在 - {image_root}")
        return
    
    # Get all PNG files and filter by index range
    all_files = sorted([f for f in os.listdir(image_root) if f.endswith('.png')])
    
    # Filter files based on index (assuming format: ...image{number}...)
    selected_files = []
    for file in all_files:
        # Extract number from filename
        if 'image' in file:
            try:
                num_str = file.split('image')[1].split('_')[0].split('.')[0]
                num = int(num_str)
                if start_idx <= num <= end_idx:
                    selected_files.append(file)
            except (ValueError, IndexError):
                continue
    
    # Sort by image number
    selected_files.sort(key=lambda x: int(x.split('image')[1].split('_')[0].split('.')[0]))
    
    print(f"找到 {len(selected_files)} 張圖片 (image{start_idx}-image{end_idx})，開始處理...")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    
    # Clear/create output file at start
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("")  # Initialize empty file
    
    # Process images and save results (real-time saving)
    for idx, image_name in enumerate(selected_files, 1):
        full_image_path = os.path.join(image_root, image_name)
        
        print(f"處理中 ({idx}/{len(selected_files)}): {image_name}")
        
        # Process image
        generated_text, metatext = process_image_with_openrouter(full_image_path)
        
        # Write results immediately in append mode (real-time saving)
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"--- {image_name} ---\n")
            f.write(f"{metatext}\n\n")
            f.write(generated_text)
            f.write("\n\n" + "="*80 + "\n\n")
        
        print(f"✓ 完成並已保存: {image_name}")
        print(f"  {metatext}")
    
    print(f"\n所有圖片處理完成！")
    print(f"輸出已儲存至: {output_file}")


def main():
    """Main execution function"""
    # Configuration
    image_root = "./廣州方言詞典_preprocessed/"
    output_file = "./output/廣州方言詞典_OCR_output.txt"
    start_idx = 48
    end_idx = 553
    
    print("="*80)
    print("廣州方言詞典 OCR 處理 (兩階段 Flash 模型)")
    print(f"階段 1: Flash OCR (IPA 標音)")
    print(f"階段 2: Flash 轉換 (IPA → 粵拼)")
    print(f"處理範圍: image{start_idx} - image{end_idx}")
    print(f"輸入資料夾: {image_root}")
    print(f"輸出檔案: {output_file}")
    print("="*80)
    print()
    
    # Check API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your_openrouter_api_key_here":
        print("❌ 錯誤: 請在 .env 文件中設置 OPENROUTER_API_KEY")
        print("   取得 API key: https://openrouter.ai/keys")
        return
    
    # Start processing
    process_folder_and_save_to_txt(image_root, output_file, start_idx, end_idx)


if __name__ == '__main__':
    main()
