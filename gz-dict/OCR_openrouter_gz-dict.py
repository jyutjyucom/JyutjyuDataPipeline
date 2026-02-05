"""
OCR script for 广州话词典 using OpenRouter API with Google Gemini 3 Flash Preview
Re-OCR to capture missing tilde symbols (~) and rare characters
Uses existing OCR results as reference for correction and supplementation

【重要原则】
以当前初版OCR结果为准，只在以下情况补充修正：
1. 补充缺失的波浪线符号（～）
2. 补充缺失或错误的生僻字
3. 修正换行格式（每个词条应为两行：字头读音行 + 释义行）
除此之外，完全保留已有OCR文本的内容！
"""

import os
import base64
import json
import re
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

# Configuration for 广州话词典
name_lang = '''粤语'''
name_lit = '''广州话词典（第2版）'''

# Example entries from the dictionary - from prompt file
ex_1 = '''【包剪𢱕】bɑo1 jin2 deb6 (𢱕，杜合切)'''

ex_2 = '''【𢳂】bed1 (毕)'''

ex_3 = '''【𡃇】bei6 (弊)'''

ex_4 = '''【乒铃𠾴唥】bing4 ling4 bɑng4 lɑng4 (乒，读音bing1;𠾴，罢盲切。）'''

ex_5 = '''【㩧】bog1 (薄1)'''

ex_6 = '''【㩧㩧斋】bog1 bog1 zɑi1'''

ex_7 = '''【补𤶸】bou2 nɑ1 (𤶸，拿1)'''

ex_8 = '''【𠼭𠼭车】bud1 bud1 cé1'''

ex_9 = '''【半㨢掯】bun3 leng3 keng3 (㨢，啦凳切; 掯，卡凳切)'''

ex_10 = '''【𩗴 (䭰) 】bung6 (罢哄切)'''

# Build system prompt
system_prompt_template = """
任务：补充{name_lang}词典《{name_lit}》OCR结果中缺失的波浪线和生僻字。

【核心原则】
以下方的「已有OCR文本」为准，只补充：
1. 缺失的波浪线符号（～）——例句中代替词头的符号
2. 缺失或错误的生僻字（如 𢱕、𢳂、𡃇、𠾴、𤶸、𠼭、㨢、㩗、㗎 等）
其他内容（字头、拼音、释义、标点等）完全保留原文，不做修改！

格式要求：
- 每个词条应为两行：
  第一行：【词头】拼音（注音说明）
  第二行：释义内容（含例句，例句用［］标记，波浪线～代替词头）
- 词条间用空行分隔
- 原OCR文本换行处理不佳，请按图片正确分行
- 保留所有标点符号、括号、丨等格式
- 如遇罕见字可用IDS表示，缺字用"□"
- 请直接输出结果，不要添加任何解释或说明

参考例子：
{ex_1}

{ex_2}

{ex_4}

{ex_6}

{ex_9}

---
已有OCR文本（第{page_num}页）：
{existing_ocr_text}
""".strip()


def load_json_pages(json_file_path: str) -> dict:
    """
    Load the JSON file containing page data
    
    Args:
        json_file_path: Path to the JSON file containing page data
        
    Returns:
        dict: Dictionary mapping actual_page_num -> page_data (with 'content' key)
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Build a dictionary mapping actual_page_num to page content
        pages_dict = {}
        for page in data.get('pages', []):
            actual_page_num = page.get('actual_page_num')
            if actual_page_num:
                pages_dict[actual_page_num] = page.get('content', '')
        
        return pages_dict
    except FileNotFoundError:
        print(f"警告：找不到JSON文件 {json_file_path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"警告：JSON文件格式错误: {e}")
        return {}
    except Exception as e:
        print(f"警告：读取JSON文件时发生错误: {e}")
        return {}


def get_page_content(pages_dict: dict, page_num: int) -> str:
    """
    Get the content for a specific page number from the pages dictionary
    
    Args:
        pages_dict: Dictionary mapping actual_page_num -> page content
        page_num: Actual page number (121-659)
        
    Returns:
        str: Page content, or a message if not found
    """
    if not pages_dict:
        return "（无已有OCR文本参考）"
    
    if page_num in pages_dict:
        content = pages_dict[page_num]
        # Truncate if too long (to avoid excessive prompt length)
        if len(content) > 3000:
            content = content[:3000] + "\n...(后续内容省略)"
        return content
    else:
        return f"（未找到第{page_num}页对应的内容）"


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


def process_image_with_openrouter(image_path: str, page_num: int, existing_ocr_context: str) -> tuple[str, str]:
    """
    Process a single image using single-stage Flash model with existing OCR text as reference
    
    Args:
        image_path: Path to the image file
        page_num: Page number being processed
        existing_ocr_context: Existing OCR text for this page as reference
    
    Returns:
        tuple: (generated_text, metadata_text)
    """
    try:
        # Encode image
        base64_image = encode_image_to_base64(image_path)
        
        # Build system prompt with existing OCR context
        system_prompt = system_prompt_template.format(
            name_lang=name_lang,
            name_lit=name_lit,
            ex_1=ex_1,
            ex_2=ex_2,
            ex_4=ex_4,
            ex_6=ex_6,
            ex_9=ex_9,
            page_num=page_num,
            existing_ocr_text=existing_ocr_context
        )
        
        # Single-stage processing with Flash model
        messages = [
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
                        "text": "请以已有OCR文本为基础，对照图片补充缺失的波浪线（～）和生僻字，并修正换行格式（每个词条应为两行），用空行分隔相邻词条。其他内容保持原样。"
                    }
                ]
            }
        ]
        
        response = client.chat.completions.create(
            model="google/gemini-3-flash-preview",
            messages=messages,
        )
        
        generated_text = response.choices[0].message.content if response.choices[0].message.content else ""
        usage = response.usage
        
        # Build metadata string
        metadata_text = f"<Token Count: {usage.total_tokens} (Prompt:{usage.prompt_tokens} Completion:{usage.completion_tokens})>"
        
        return generated_text, metadata_text
        
    except Exception as e:
        print(f"处理图片 {image_path} 时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return "", f"错误: {e}"


def process_folder_and_save_to_txt(image_root: str, output_file: str, json_file_path: str, 
                                   start_idx: int = 1, end_idx: int = 999):
    """
    Process images in the specified range and save results to a text file
    Real-time saving: each page is saved immediately after processing
    Uses JSON file containing page data as reference for each page
    
    Args:
        image_root: Path to the folder containing preprocessed images
        output_file: Path to save the output text file
        json_file_path: Path to JSON file containing page data
        start_idx: Starting page index (inclusive)
        end_idx: Ending page index (inclusive)
    """
    # Ensure image folder exists
    if not os.path.isdir(image_root):
        print(f"错误：图片资料夹不存在 - {image_root}")
        return
    
    # Load JSON file with page data
    print(f"正在加载JSON分页数据: {json_file_path}")
    pages_dict = load_json_pages(json_file_path)
    if pages_dict:
        print(f"✓ 已加载JSON数据，包含 {len(pages_dict)} 页")
        if pages_dict:
            min_page = min(pages_dict.keys())
            max_page = max(pages_dict.keys())
            print(f"  页码范围：第{min_page}页 - 第{max_page}页")
    else:
        print("⚠ 未能加载JSON数据，将继续处理但没有参考文本")
        pages_dict = {}
    
    # Get all PNG files and filter by index range
    all_files = sorted([f for f in os.listdir(image_root) if f.endswith('.png')])
    
    # Filter files based on index (assuming format: ...页面_{number}...)
    selected_files = []
    for file in all_files:
        # Extract number from filename - try multiple patterns
        try:
            # Pattern 1: 页面_XXXX
            if '页面_' in file:
                num_str = file.split('页面_')[1].split('.')[0]
                num = int(num_str)
                if start_idx <= num <= end_idx:
                    selected_files.append((file, num))
            # Pattern 2: imageXXX
            elif 'image' in file:
                num_str = file.split('image')[1].split('_')[0].split('.')[0]
                num = int(num_str)
                if start_idx <= num <= end_idx:
                    selected_files.append((file, num))
        except (ValueError, IndexError):
            continue
    
    # Sort by page number
    selected_files.sort(key=lambda x: x[1])
    
    print(f"找到 {len(selected_files)} 张图片 (页面{start_idx}-页面{end_idx})，开始处理...")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    
    # Clear/create output file at start
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("")  # Initialize empty file
    
    # Process images and save results (real-time saving)
    for idx, (image_name, page_num) in enumerate(selected_files, 1):
        full_image_path = os.path.join(image_root, image_name)
        
        print(f"处理中 ({idx}/{len(selected_files)}): {image_name} [第{page_num}页]")
        
        # Get page content from JSON data
        existing_ocr_context = get_page_content(pages_dict, page_num)
        
        # Process image with existing OCR context
        generated_text, metatext = process_image_with_openrouter(
            full_image_path, 
            page_num, 
            existing_ocr_context
        )
        
        # Write results immediately in append mode (real-time saving)
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"--- {image_name} (第{page_num}页) ---\n")
            f.write(f"{metatext}\n\n")
            f.write(generated_text)
            f.write("\n\n" + "="*80 + "\n\n")
        
        print(f"✓ 完成并已保存: {image_name}")
        print(f"  {metatext}")
    
    print(f"\n所有图片处理完成！")
    print(f"输出已储存至: {output_file}")


def main():
    """Main execution function"""
    # Configuration - adjust these paths and ranges as needed
    image_root = "./input/广州话词典/"
    json_file_path = "./output/广州话词典_分页结果.json"
    output_file = "./output/广州话词典_重新OCR_输出.txt"
    start_idx = 121  # Start from page 121
    end_idx = 659    # End at page 659
    
    print("="*80)
    print("广州话词典 重新OCR处理 (基于已有文本校正)")
    print(f"处理范围: 页面{start_idx} - 页面{end_idx}")
    print(f"输入图片资料夹: {image_root}")
    print(f"JSON分页数据: {json_file_path}")
    print(f"输出档案: {output_file}")
    print("="*80)
    print("【核心工作原则】")
    print("  以已有OCR文本为准，只补充修正以下内容：")
    print("    1. 补充缺失的波浪线符号（～）")
    print("    2. 补充缺失的生僻字（𢱕、𢳂、𡃇、𠾴、𤶸、𠼭、㨢、㩗、㗎 等）")
    print("    3. 修正换行格式（每个词条应为两行：字头读音 + 释义）")
    print("  其他内容（字头、拼音、释义、标点等）完全保留原样！")
    print("="*80)
    print()
    
    # Check API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your_openrouter_api_key_here":
        print("❌ 错误: 请在 .env 文件中设置 OPENROUTER_API_KEY")
        print("   取得 API key: https://openrouter.ai/keys")
        return
    
    # Check if JSON file exists
    if not os.path.exists(json_file_path):
        print(f"⚠ 警告: JSON文件不存在: {json_file_path}")
        print("   将继续处理但没有参考文本")
    
    # Start processing
    process_folder_and_save_to_txt(image_root, output_file, json_file_path, start_idx, end_idx)


if __name__ == '__main__':
    main()
