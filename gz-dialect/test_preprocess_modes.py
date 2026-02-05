"""
测试不同预处理模式的效果
生成对比图，帮助选择最合适的预处理参数
"""
import os
from pathlib import Path
import matplotlib.pyplot as plt
from PIL import Image
from preprocess_guangzhou_dict import preprocess_for_ocr


def compare_preprocessing_modes(image_path: str, output_dir: str = "./test_comparison"):
    """
    对比不同预处理模式的效果
    
    Args:
        image_path: 测试图像路径
        output_dir: 对比结果输出目录
    """
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 读取原始图像
    original_img = Image.open(image_path)
    
    # 测试不同模式
    modes = ["balanced", "high_contrast", "binarize_adaptive", "binarize_otsu"]
    processed_images = {}
    
    print("正在处理不同模式...")
    for mode in modes:
        print(f"  - {mode} 模式")
        try:
            processed_images[mode] = preprocess_for_ocr(image_path, mode=mode)
        except Exception as e:
            print(f"    处理 {mode} 时出错: {e}")
            processed_images[mode] = original_img
    
    # 创建对比图 - 2x3布局
    fig, axes = plt.subplots(2, 3, figsize=(20, 13))
    fig.suptitle(f'预处理模式对比 - {Path(image_path).name}', fontsize=16)
    
    # 显示原始图像
    axes[0, 0].imshow(original_img, cmap='gray' if original_img.mode == 'L' else None)
    axes[0, 0].set_title('原始图像', fontsize=14)
    axes[0, 0].axis('off')
    
    # 显示light模式作为参考
    try:
        light_img = preprocess_for_ocr(image_path, mode="light")
        axes[0, 1].imshow(light_img, cmap='gray' if light_img.mode == 'L' else None)
        axes[0, 1].set_title('LIGHT 模式（参考）', fontsize=14)
        axes[0, 1].axis('off')
    except:
        axes[0, 1].axis('off')
    
    # 显示处理后的图像
    mode_positions = [(0, 2), (1, 0), (1, 1), (1, 2)]
    for idx, (mode, img) in enumerate(processed_images.items()):
        if idx < len(mode_positions):
            row, col = mode_positions[idx]
            axes[row, col].imshow(img, cmap='gray' if img.mode == 'L' else None)
            title = mode.replace('_', ' ').upper()
            axes[row, col].set_title(title, fontsize=14)
            axes[row, col].axis('off')
    
    plt.tight_layout()
    
    # 保存对比图
    comparison_file = output_path / f"comparison_{Path(image_path).stem}.png"
    plt.savefig(comparison_file, dpi=150, bbox_inches='tight')
    print(f"\n对比图已保存: {comparison_file}")
    
    # 显示图像
    plt.show()
    
    # 保存单独的处理结果
    print("\n保存各模式处理结果:")
    original_img.save(output_path / f"0_original_{Path(image_path).stem}.png")
    print(f"  - 原始图像")
    
    for mode, img in processed_images.items():
        output_file = output_path / f"{mode}_{Path(image_path).stem}.png"
        img.save(output_file)
        print(f"  - {mode} 模式: {output_file}")
    
    print("\n完成！请查看图像效果并选择最合适的模式。")
    
    # 输出建议
    print("\n" + "="*70)
    print("模式选择建议:")
    print("="*70)
    print("• balanced 模式         - 灰度增强（推荐起点）")
    print("                           适合：大多数情况，保留灰度信息")
    print()
    print("• high_contrast 模式    - 高对比度增强")
    print("                           适合：需要更强对比度，但保留灰度")
    print()
    print("• binarize_adaptive 模式 - 自适应二值化（推荐OCR）")
    print("                            适合：OCR识别，黑白分明")
    print("                            优点：自适应局部亮度，效果通常最好")
    print()
    print("• binarize_otsu 模式    - Otsu二值化")
    print("                           适合：OCR识别，全局阈值")
    print("                           优点：速度快，适合光照均匀的图像")
    print()
    print("对比度提升建议：")
    print("  1. 如果需要人眼阅读：选择 balanced 或 high_contrast")
    print("  2. 如果用于OCR识别：选择 binarize_adaptive（效果最好）")
    print("  3. 二值化后文字更锐利，对比度最高，OCR识别率通常提升20-40%")
    print("="*70)


def test_multiple_samples(input_dir: str, sample_indices: list, output_dir: str = "./test_comparison"):
    """
    测试多个样本图像
    
    Args:
        input_dir: 输入目录
        sample_indices: 要测试的图像编号列表，如 [1, 50, 100, 200]
        output_dir: 输出目录
    """
    input_path = Path(input_dir)
    
    # 获取所有图像文件
    image_files = sorted([f for f in input_path.iterdir() if f.suffix.lower() in ['.jpg', '.jpeg', '.png']])
    
    print(f"找到 {len(image_files)} 张图片")
    print(f"将测试以下样本: {sample_indices}\n")
    
    # 为每个样本编号找到对应的文件
    for idx in sample_indices:
        # 查找包含该编号的文件
        matching_files = [f for f in image_files if f"image{idx}_" in f.name or f"image{idx}." in f.name]
        
        if matching_files:
            img_file = matching_files[0]
            print(f"\n{'='*60}")
            print(f"测试图像 {idx}: {img_file.name}")
            print(f"{'='*60}")
            compare_preprocessing_modes(str(img_file), output_dir=output_dir)
        else:
            print(f"警告: 未找到编号为 {idx} 的图像")


if __name__ == '__main__':
    # ============= 配置区域 =============
    
    # 方式1: 测试单张图片
    SINGLE_TEST = True
    SINGLE_IMAGE_PATH = "./input/现代粤语词典/现代粤语词典（广州音 第一版）.范俊军.范兰德.2021_页面_0138.png"
    
    # 方式2: 测试多张样本（不同类型的页面）
    MULTIPLE_TEST = False
    INPUT_DIR = "./input/现代粤语词典"
    SAMPLE_INDICES = [1, 50, 100, 200, 300]  # 测试这些编号的图片
    
    # 输出目录
    OUTPUT_DIR = "./test_comparison"
    
    # ===================================
    
    if SINGLE_TEST:
        if os.path.exists(SINGLE_IMAGE_PATH):
            compare_preprocessing_modes(SINGLE_IMAGE_PATH, OUTPUT_DIR)
        else:
            print(f"错误: 找不到图像文件 {SINGLE_IMAGE_PATH}")
            print("请修改 SINGLE_IMAGE_PATH 为实际存在的图像路径")
    
    if MULTIPLE_TEST:
        test_multiple_samples(INPUT_DIR, SAMPLE_INDICES, OUTPUT_DIR)
