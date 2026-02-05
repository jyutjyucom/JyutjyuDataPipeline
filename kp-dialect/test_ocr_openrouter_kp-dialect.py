"""
临时测试脚本 - 测试 OpenRouter API 处理《开平方言》
只处理少量图片用于快速测试
单阶段处理（开平话词条 + IPA 读音 + 普通话解释）
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
    print("《开平方言》 OCR 测试（单阶段处理）")
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
    image_root = "./input/开平方言/"
    
    if not os.path.isdir(image_root):
        print(f"\n❌ 错误: 找不到预处理图片资料夹 - {image_root}")
        return
    
    # Get test images (例如：页面_0106 到 页面_0108，用于快速测试)
    all_files = sorted([f for f in os.listdir(image_root) if f.endswith('.png')])
    
    test_files = []
    for file in all_files:
        # Try pattern: 页面_XXXX
        if '页面_' in file:
            try:
                num_str = file.split('页面_')[1].split('.')[0]
                num = int(num_str)
                if 106 <= num <= 108:  # 测试 3 张
                    test_files.append(file)
            except (ValueError, IndexError):
                continue
        # Try pattern: imageXXX
        elif 'image' in file:
            try:
                num_str = file.split('image')[1].split('_')[0].split('.')[0]
                num = int(num_str)
                if 106 <= num <= 108:  # 测试 3 张
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
        print(f"\n❌ 错误: 找不到测试图片 (页面106-108)")
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
        print("   python OCR_openrouter_kp-dialect.py")
    else:
        print("\n❌ 测试失败，请检查上述错误信息。")


if __name__ == '__main__':
    main()
