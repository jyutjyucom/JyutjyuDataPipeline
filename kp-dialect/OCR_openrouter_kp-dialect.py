"""
OCR script for 现代粤语词典 using OpenRouter API with Google Gemini 3 Flash Preview
Single-stage processing optimized for simplified Chinese and Jyutping romanization
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

# Configuration for 《开平方言》
name_lang = '''开平方言'''
name_lit = '''开平方言'''

# Build system prompt for 《开平方言》
system_prompt = f"""
你将担任《{name_lit}》电子化的工作，你将看到其中页面的截图，请把其中的所有内容完整、准确地誊写出来。

本书词条内容结构非常简单，通常包括：
- 开平话词条或短语（一般在最前面）
- 紧跟的读音说明：多使用国际音标（IPA）表示声母、韵母，声调用上标数字表示
- 后面是简体中文的普通话解释，有时可能有例句或补充说明

注意与要求：
- 请完整识别并输出所有汉字、IPA 音标、声调数字、标点符号及其它符号
- 如果原书中声调是上标数字，请在输出时改用正常数字：123456789（例如 [a⁵⁵] 要输出为 [a55]）
- 非常注意不要改变或遗漏任何 IPA 符号（包括元音、辅音、长度符号、连字符、括号等）
- 词条之间应保持原有的换行与段落结构，不要自行合并或拆分段落
- 不要添加任何你自己的注释、解释或标点，只输出图片中原有的内容
- 如遇到罕见字或 Unicode 未收录的汉字，请保持书中原样（例如用“□”等占位符），不要自行替换或推断
- 图中未截取到的前文或后文不能擅自补充，只抄录你能看到的内容

输出格式：
- 直接输出识别到的文字内容，保持原文的行内顺序和段落顺序
- 不要使用任何加粗、斜体、下划线或其它富文本格式
- 每个词条或自然段落保持为单独一段，与原书版式尽量接近
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
    Process a single image using single-stage Flash model
    
    Returns:
        tuple: (generated_text, metadata_text)
    """
    try:
        # Encode image
        base64_image = encode_image_to_base64(image_path)
        
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
                        "text": "请根据系统提示处理这张图片，识别并输出所有词条内容。"
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


def process_folder_and_save_to_txt(image_root: str, output_file: str, start_idx: int = 1, end_idx: int = 999):
    """
    Process images in the specified range and save results to a text file
    Real-time saving: each page is saved immediately after processing
    
    Args:
        image_root: Path to the folder containing preprocessed images
        output_file: Path to save the output text file
        start_idx: Starting page index (inclusive)
        end_idx: Ending page index (inclusive)
    """
    # Ensure image folder exists
    if not os.path.isdir(image_root):
        print(f"错误：图片资料夹不存在 - {image_root}")
        return
    
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
                    selected_files.append(file)
            # Pattern 2: imageXXX
            elif 'image' in file:
                num_str = file.split('image')[1].split('_')[0].split('.')[0]
                num = int(num_str)
                if start_idx <= num <= end_idx:
                    selected_files.append(file)
        except (ValueError, IndexError):
            continue
    
    # Sort by page number
    def extract_number(filename):
        if '页面_' in filename:
            return int(filename.split('页面_')[1].split('.')[0])
        elif 'image' in filename:
            return int(filename.split('image')[1].split('_')[0].split('.')[0])
        return 0
    
    selected_files.sort(key=extract_number)
    
    print(f"找到 {len(selected_files)} 张图片 (页面{start_idx}-页面{end_idx})，开始处理...")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    
    # Clear/create output file at start
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("")  # Initialize empty file
    
    # Process images and save results (real-time saving)
    for idx, image_name in enumerate(selected_files, 1):
        full_image_path = os.path.join(image_root, image_name)
        
        print(f"处理中 ({idx}/{len(selected_files)}): {image_name}")
        
        # Process image
        generated_text, metatext = process_image_with_openrouter(full_image_path)
        
        # Write results immediately in append mode (real-time saving)
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"--- {image_name} ---\n")
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
    image_root = "./input/开平方言/"
    output_file = "./output/开平方言_OCR_106-268.txt"
    start_idx = 106  # 起始页码（含）
    end_idx = 268   # 结束页码（含）
    
    print("="*80)
    print("现代粤语词典 OCR 处理 (单阶段 Flash 模型)")
    print(f"处理范围: 页面{start_idx} - 页面{end_idx}")
    print(f"输入资料夹: {image_root}")
    print(f"输出档案: {output_file}")
    print("="*80)
    print()
    
    # Check API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your_openrouter_api_key_here":
        print("❌ 错误: 请在 .env 文件中设置 OPENROUTER_API_KEY")
        print("   取得 API key: https://openrouter.ai/keys")
        return
    
    # Start processing
    process_folder_and_save_to_txt(image_root, output_file, start_idx, end_idx)


if __name__ == '__main__':
    main()
