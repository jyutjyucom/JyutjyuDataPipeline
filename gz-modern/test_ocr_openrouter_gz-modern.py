"""
临时测试脚本 - 测试 OpenRouter API 处理《现代粤语词典》
只处理 1-3 张图片用于快速测试
单阶段处理（简体中文 + 拼音）
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

ex_5 = '''【阿伯】aa⁵ baag⁸ 对老年男性的尊称。又说"伯父"（48页）、"老伯"（422页）。'''

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
    """Encode image to base64 string for API transmission"""
    with Image.open(image_path) as img:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.read()).decode('utf-8')


def test_single_image(image_path: str):
    """Test processing a single image with single-stage approach"""
    print("\n" + "="*80)
    print(f"测试图片: {os.path.basename(image_path)}")
    print("="*80)
    
    if not os.path.exists(image_path):
        print(f"❌ 错误: 图片不存在 - {image_path}")
        return
    
    try:
        print("📤 正在编码图片...")
        base64_image = encode_image_to_base64(image_path)
        print(f"✓ 图片编码完成 (大小: {len(base64_image)} bytes)")
        
        # ========== 单阶段处理：Flash 模型直接 OCR ==========
        print("\n" + "="*80)
        print("📡 使用 Flash 模型进行 OCR 处理")
        print("="*80)
        print(f"   模型: google/gemini-3-flash-preview")
        print(f"   策略: 单阶段处理（简体中文 + 拼音）")
        
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
        
        print("✓ Flash 模型处理完成！")
        print(f"   Token 使用: {usage.total_tokens} (Prompt: {usage.prompt_tokens}, Completion: {usage.completion_tokens})")
        
        # Build metadata string
        metadata_text = f"<Token Count: {usage.total_tokens} (Prompt:{usage.prompt_tokens} Completion:{usage.completion_tokens})>"
        
        print("\n" + "-"*80)
        print("📊 Token 使用情况:")
        print(f"   总计: {usage.total_tokens}")
        print(f"   Prompt: {usage.prompt_tokens}")
        print(f"   Completion: {usage.completion_tokens}")
        print("-"*80)
        
        print("\n📄 OCR 结果:")
        print("-"*80)
        print(generated_text)
        print("-"*80)
        
        return generated_text, metadata_text
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def main():
    """Main test function"""
    print("="*80)
    print("OpenRouter API 测试脚本")
    print("现代粤语词典 OCR 测试（单阶段处理）")
    print("="*80)
    
    # Check API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your_openrouter_api_key_here":
        print("\n❌ 错误: 请先设置 OPENROUTER_API_KEY")
        print("   1. 从 https://openrouter.ai/keys 获取 API key")
        print("   2. 创建 .env 文件并添加:")
        print("      OPENROUTER_API_KEY=your_actual_key_here")
        return
    
    print(f"\n✓ API Key 已加载: {api_key[:20]}...")
    
    # Test image paths - 测试特定页面的图片
    image_root = "./input/现代粤语词典_preprocessed/"
    
    if not os.path.isdir(image_root):
        print(f"\n❌ 错误: 找不到预处理图片资料夹 - {image_root}")
        return
    
    # Get test images (页面_0138 到 页面_0140)
    all_files = sorted([f for f in os.listdir(image_root) if f.endswith('.png')])
    
    test_files = []
    for file in all_files:
        # Try pattern: 页面_XXXX
        if '页面_' in file:
            try:
                num_str = file.split('页面_')[1].split('.')[0]
                num = int(num_str)
                if 138 <= num <= 140:  # 测试前 3 张
                    test_files.append(file)
            except (ValueError, IndexError):
                continue
        # Try pattern: imageXXX
        elif 'image' in file:
            try:
                num_str = file.split('image')[1].split('_')[0].split('.')[0]
                num = int(num_str)
                if 138 <= num <= 140:  # 测试前 3 张
                    test_files.append(file)
            except (ValueError, IndexError):
                continue
    
    # Sort by page number
    def extract_number(filename):
        if '页面_' in filename:
            return int(filename.split('页面_')[1].split('.')[0])
        elif 'image' in filename:
            return int(filename.split('image')[1].split('_')[0].split('.')[0])
        return 0
    
    test_files.sort(key=extract_number)
    
    if not test_files:
        print(f"\n❌ 错误: 找不到测试图片 (页面138-140)")
        print(f"   资料夹内容示例: {all_files[:5]}...")
        return
    
    print(f"\n找到 {len(test_files)} 张测试图片:")
    for f in test_files:
        print(f"  - {f}")
    
    # Test each image
    results = []
    for image_name in test_files:
        full_path = os.path.join(image_root, image_name)
        text, meta = test_single_image(full_path)
        if text:
            results.append((image_name, text, meta))
        
        # Ask if continue
        if len(results) < len(test_files):
            print("\n" + "="*80)
            response = input("继续测试下一张图片? (Enter 继续 / n 停止): ").strip().lower()
            if response == 'n':
                break
    
    # Summary
    print("\n" + "="*80)
    print("测试完成总结")
    print("="*80)
    print(f"成功处理: {len(results)}/{len(test_files)} 张图片")
    
    if results:
        print("\n✅ API 测试成功！可以开始批量处理了。")
        print("\n运行完整 OCR 处理:")
        print("   python OCR_openrouter_gz-modern.py")
    else:
        print("\n❌ 测试失败，请检查上述错误信息。")


if __name__ == '__main__':
    main()
