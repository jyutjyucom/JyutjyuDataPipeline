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

# Configuration for 现代粤语词典
name_lang = '''粤语'''
name_lit = '''现代粤语词典（广州音 第一版）'''

# Example entries from the dictionary
ex_1 = '''【阿崩吹箫】aa⁵ bang¹ coey¹ siu¹ 俗语。比喻白费口舌：点讲佢都唔听，真系～啰［怎么说他都不听，真是白费唇舌］。'''

ex_2 = '''【阿崩叫狗，越叫越走】aa⁵ bang¹ giu⁵ gau³，yud⁹ giu⁵ yud⁹ zau³ 俗语。比喻不听劝、对着干：佢哋都惊你，个个都系～［他们都怕你，都越叫越不愿来］。'''

ex_3 = '''【阿】aa⁵ 七画 ①放在姓、名、排行前，构成称谓词：～黄丨～红丨～二。②用在某些亲属称谓前，表示称谓：～叔丨～妈。
另见 ē（179 页）。'''

ex_4 = '''【阿爸】aa⁵ baa² 父亲。又说"爸爸"（13 页）。'''

ex_5 = '''【阿伯】aa⁵ baag⁸ 对老年男性的尊称。又说“伯父”（48页）、“老伯”（422页）。'''

# Build system prompt
system_prompt = f"""
你将担任{name_lang}词典《{name_lit}》电子化的工作，你将看到其中页面的截图，你随之将其中的内容写出来。

词典格式特点：
- 字头不使用【】标记，直接写汉字，如“阿”、“爸”等
- 词头使用【】标记，如【阿崩吹箫】、【阿爸】等
- 有些字头后可能会附注繁体字，请保留这种标注
- 音标使用该书的拼音方案，使用上标数字表示声调（¹²³⁴⁵⁶⁷⁸⁹），但在输出时请使用正常数字表示：123456789，如aa⁵改为aa5
- 特别要注意该书拼音方案的声调排序与常规粤语拼音声调的排序不同，如阴平为¹，阳平为²，阴上为³，阳上为⁴，阴去为⁵，阳去为⁶，高入声为⁷，中入声为⁸，低入声为⁹，请特别注意，不要写错
- 内容以简体中文为主，但字头后可能有繁体标注

注意及要求：
- 请完整准确地识别所有内容，包括汉字、拼音、声调、标点符号
- 保持原文格式，包括【】、［］、丨、～等符号
- 音标中的上标数字（声调），在输出时请使用正常数字表示，不要使用上标数字：123456789，如aa⁵改为aa5
- 如遇到罕见字或Unicode未收录的汉字，使用表意文字描述序列（IDS）表示
- 如果原文使用"□"表示缺字，也应写"□"
- 图中未截取到的前文或后文不能擅自补充

输出格式：
- 直接输出识别的文字内容，保持原文格式，但不要加粗、斜体、下划线等格式
- 每个词条单独成段
- 保持原文的所有格式标记和符号

以下是几个例子：
{ex_1}

{ex_2}

{ex_3}

{ex_4}

{ex_5}
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
    image_root = "./input/现代粤语词典_preprocessed/"
    output_file = "./output/现代粤语词典_OCR_output.txt"
    start_idx = 138  # Adjust start page
    end_idx = 1129  # Adjust end page
    
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
