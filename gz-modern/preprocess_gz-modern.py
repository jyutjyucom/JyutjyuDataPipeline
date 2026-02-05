"""
现代粤语词典图像预处理工具
专门针对已分割好的单页PNG图片进行OCR前的增强处理
"""
import os
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
from PIL import Image, ImageEnhance
from tqdm import tqdm


def enhance_image_basic(pil_img: Image.Image, brightness_factor=1.1, contrast_factor=1.3) -> Image.Image:
    """
    基础图像增强：调整亮度和对比度
    
    Args:
        pil_img: 输入的PIL图像
        brightness_factor: 亮度增强因子（1.0为原始，>1.0变亮）
        contrast_factor: 对比度增强因子（1.0为原始，>1.0对比度增强）
    
    Returns:
        增强后的PIL图像
    """
    # 亮度增强
    enhancer = ImageEnhance.Brightness(pil_img)
    img_enhanced = enhancer.enhance(brightness_factor)
    
    # 对比度增强
    enhancer = ImageEnhance.Contrast(img_enhanced)
    img_enhanced = enhancer.enhance(contrast_factor)
    
    return img_enhanced


def apply_clahe(pil_img: Image.Image, clip_limit=2.0, tile_grid_size=(8, 8)) -> Image.Image:
    """
    应用CLAHE（对比度受限的自适应直方图均衡化）
    
    Args:
        pil_img: 输入的PIL图像
        clip_limit: 对比度限制阈值
        tile_grid_size: 网格大小
    
    Returns:
        处理后的PIL图像
    """
    # 转换为OpenCV格式
    open_cv_image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    
    # 转换为灰度图
    gray_img = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
    
    # 创建CLAHE对象并应用
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    clahe_img = clahe.apply(gray_img)
    
    # 转换回PIL图像
    return Image.fromarray(clahe_img)


def apply_gamma_correction(pil_img: Image.Image, gamma=1.5) -> Image.Image:
    """
    Gamma校正增强对比度
    
    Args:
        pil_img: 输入的PIL图像
        gamma: gamma值，<1变暗，>1变亮
    
    Returns:
        处理后的PIL图像
    """
    img_array = np.array(pil_img)
    
    # 归一化到0-1
    img_normalized = img_array / 255.0
    
    # 应用gamma校正
    img_corrected = np.power(img_normalized, gamma)
    
    # 转换回0-255
    img_corrected = (img_corrected * 255).astype(np.uint8)
    
    return Image.fromarray(img_corrected)


def apply_adaptive_threshold(pil_img: Image.Image, block_size=11, c=2) -> Image.Image:
    """
    自适应阈值二值化，效果通常最好
    
    Args:
        pil_img: 输入的PIL图像
        block_size: 用于计算阈值的邻域大小（必须是奇数）
        c: 从平均值中减去的常数
    
    Returns:
        二值化后的PIL图像
    """
    img_array = np.array(pil_img)
    
    if img_array.ndim == 3:
        img_gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        img_gray = img_array
    
    # 自适应阈值二值化
    binary = cv2.adaptiveThreshold(
        img_gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        c
    )
    
    return Image.fromarray(binary)


def apply_otsu_threshold(pil_img: Image.Image) -> Image.Image:
    """
    Otsu自动阈值二值化
    
    Args:
        pil_img: 输入的PIL图像
    
    Returns:
        二值化后的PIL图像
    """
    img_array = np.array(pil_img)
    
    if img_array.ndim == 3:
        img_gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        img_gray = img_array
    
    # Otsu二值化
    _, binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return Image.fromarray(binary)


def apply_morphology(pil_img: Image.Image, operation='close', kernel_size=2) -> Image.Image:
    """
    形态学操作，去除噪点和连接断裂的文字
    
    Args:
        pil_img: 输入的PIL图像
        operation: 'erode', 'dilate', 'open', 'close'
        kernel_size: 核大小
    
    Returns:
        处理后的PIL图像
    """
    img_array = np.array(pil_img)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    
    if operation == 'erode':
        result = cv2.erode(img_array, kernel, iterations=1)
    elif operation == 'dilate':
        result = cv2.dilate(img_array, kernel, iterations=1)
    elif operation == 'open':
        result = cv2.morphologyEx(img_array, cv2.MORPH_OPEN, kernel)
    elif operation == 'close':
        result = cv2.morphologyEx(img_array, cv2.MORPH_CLOSE, kernel)
    else:
        result = img_array
    
    return Image.fromarray(result)


def sharpen_image(pil_img: Image.Image, kernel_size=3, amount=1.0) -> Image.Image:
    """
    图像锐化增强
    
    Args:
        pil_img: 输入的PIL图像
        kernel_size: 锐化核大小
        amount: 锐化程度（0.0-2.0）
    
    Returns:
        锐化后的PIL图像
    """
    # 转换为OpenCV格式
    img_array = np.array(pil_img)
    if img_array.ndim == 3:
        img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    else:
        img_cv = img_array
    
    # 应用高斯模糊
    blurred = cv2.GaussianBlur(img_cv, (kernel_size, kernel_size), 0)
    
    # 锐化 = 原图 + amount * (原图 - 模糊图)
    sharpened = cv2.addWeighted(img_cv, 1.0 + amount, blurred, -amount, 0)
    
    # 转换回PIL
    if sharpened.ndim == 3:
        sharpened_rgb = cv2.cvtColor(sharpened, cv2.COLOR_BGR2RGB)
        return Image.fromarray(sharpened_rgb)
    else:
        return Image.fromarray(sharpened)


def denoise_image(pil_img: Image.Image, h=10) -> Image.Image:
    """
    去噪处理
    
    Args:
        pil_img: 输入的PIL图像
        h: 滤波强度（推荐范围：3-15）
    
    Returns:
        去噪后的PIL图像
    """
    img_array = np.array(pil_img)
    
    if img_array.ndim == 3:
        img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        denoised = cv2.fastNlMeansDenoisingColored(img_cv, None, h, h, 7, 21)
        denoised_rgb = cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB)
        return Image.fromarray(denoised_rgb)
    else:
        denoised = cv2.fastNlMeansDenoising(img_array, None, h, 7, 21)
        return Image.fromarray(denoised)


def preprocess_for_ocr(
    image_path: str, 
    mode: str = "balanced",
    custom_params: Optional[dict] = None
) -> Image.Image:
    """
    OCR预处理主函数
    
    Args:
        image_path: 输入图像路径
        mode: 预处理模式
            - "light": 轻度处理，适合质量较好的图片
            - "balanced": 平衡模式（推荐）
            - "aggressive": 强力处理，适合质量较差的图片
            - "custom": 自定义参数
        custom_params: 自定义参数字典
    
    Returns:
        处理后的PIL图像
    """
    # 读取图像
    img = Image.open(image_path)
    
    # 预设参数
    params = {
        "light": {
            "brightness": 1.05,
            "contrast": 1.2,
            "clahe_clip": 1.5,
            "clahe_grid": (8, 8),
            "gamma": None,
            "sharpen": False,
            "denoise": False,
            "binarize": None
        },
        "balanced": {
            "brightness": 1.1,
            "contrast": 1.4,
            "clahe_clip": 2.5,
            "clahe_grid": (12, 12),
            "gamma": None,
            "sharpen": False,
            "denoise": False,
            "binarize": None
        },
        "aggressive": {
            "brightness": 1.15,
            "contrast": 1.6,
            "clahe_clip": 3.0,
            "clahe_grid": (16, 16),
            "gamma": 1.2,
            "sharpen": True,
            "sharpen_amount": 0.5,
            "denoise": True,
            "denoise_h": 8,
            "binarize": None
        },
        "high_contrast": {
            "brightness": 1.2,
            "contrast": 1.8,
            "clahe_clip": 3.5,
            "clahe_grid": (16, 16),
            "gamma": 1.3,
            "sharpen": True,
            "sharpen_amount": 0.8,
            "denoise": False,
            "binarize": None
        },
        "binarize_adaptive": {
            "brightness": 1.1,
            "contrast": 1.3,
            "clahe_clip": 2.5,
            "clahe_grid": (12, 12),
            "gamma": None,
            "sharpen": False,
            "denoise": True,
            "denoise_h": 5,
            "binarize": "adaptive",
            "adaptive_block_size": 15,
            "adaptive_c": 8
        },
        "binarize_otsu": {
            "brightness": 1.1,
            "contrast": 1.3,
            "clahe_clip": 2.5,
            "clahe_grid": (12, 12),
            "gamma": None,
            "sharpen": False,
            "denoise": True,
            "denoise_h": 5,
            "binarize": "otsu"
        }
    }
    
    # 选择参数
    if mode == "custom" and custom_params:
        p = custom_params
    else:
        p = params.get(mode, params["balanced"])
    
    # 应用处理流程
    # 1. 基础增强
    img_enhanced = enhance_image_basic(
        img, 
        brightness_factor=p.get("brightness", 1.1),
        contrast_factor=p.get("contrast", 1.3)
    )
    
    # 2. CLAHE增强
    img_enhanced = apply_clahe(
        img_enhanced,
        clip_limit=p.get("clahe_clip", 2.0),
        tile_grid_size=p.get("clahe_grid", (12, 12))
    )
    
    # 3. 可选的Gamma校正
    if p.get("gamma"):
        img_enhanced = apply_gamma_correction(img_enhanced, gamma=p.get("gamma"))
    
    # 4. 可选的去噪
    if p.get("denoise", False):
        img_enhanced = denoise_image(img_enhanced, h=p.get("denoise_h", 10))
    
    # 5. 可选的锐化
    if p.get("sharpen", False):
        img_enhanced = sharpen_image(img_enhanced, amount=p.get("sharpen_amount", 1.0))
    
    # 6. 可选的二值化
    binarize_method = p.get("binarize")
    if binarize_method == "adaptive":
        img_enhanced = apply_adaptive_threshold(
            img_enhanced,
            block_size=p.get("adaptive_block_size", 15),
            c=p.get("adaptive_c", 8)
        )
    elif binarize_method == "otsu":
        img_enhanced = apply_otsu_threshold(img_enhanced)
    
    # 7. 可选的形态学操作
    if p.get("morphology"):
        img_enhanced = apply_morphology(
            img_enhanced,
            operation=p.get("morphology_op", "close"),
            kernel_size=p.get("morphology_kernel", 2)
        )
    
    return img_enhanced


def batch_preprocess(
    input_dir: str,
    output_dir: str,
    mode: str = "balanced",
    image_format: str = "png",
    skip_existing: bool = True,
    start_file: Optional[str] = None,
    end_file: Optional[str] = None
):
    """
    批量处理图像
    
    Args:
        input_dir: 输入目录
        output_dir: 输出目录
        mode: 预处理模式
        image_format: 输出格式（png/jpg）
        skip_existing: 是否跳过已存在的文件
        start_file: 起始文件名（可选）
        end_file: 结束文件名（可选）
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 获取所有JPG文件
    image_files = sorted([f for f in input_path.iterdir() if f.suffix.lower() in ['.jpg', '.jpeg', '.png']])
    
    # 确定处理范围
    if start_file or end_file:
        start_idx = 0
        end_idx = len(image_files) - 1
        
        if start_file:
            for i, f in enumerate(image_files):
                if start_file in f.name:
                    start_idx = i
                    break
        
        if end_file:
            for i in range(len(image_files) - 1, -1, -1):
                if end_file in image_files[i].name:
                    end_idx = i
                    break
        
        image_files = image_files[start_idx:end_idx + 1]
    
    print(f"找到 {len(image_files)} 张图片")
    print(f"处理模式: {mode}")
    print(f"输出格式: {image_format}")
    print(f"输出目录: {output_dir}")
    
    # 批量处理
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for img_file in tqdm(image_files, desc="处理进度"):
        try:
            # 生成输出文件名
            output_file = output_path / f"{img_file.stem}.{image_format}"
            
            # 检查是否跳过
            if skip_existing and output_file.exists():
                skip_count += 1
                continue
            
            # 处理图像
            processed_img = preprocess_for_ocr(str(img_file), mode=mode)
            
            # 保存
            if image_format.lower() == 'jpg' or image_format.lower() == 'jpeg':
                processed_img.save(output_file, quality=95)
            else:
                processed_img.save(output_file)
            
            success_count += 1
            
        except Exception as e:
            print(f"\n处理 {img_file.name} 时出错: {e}")
            error_count += 1
    
    print(f"\n处理完成！")
    print(f"成功: {success_count} 张")
    print(f"跳过: {skip_count} 张")
    print(f"失败: {error_count} 张")


# 主程序
if __name__ == '__main__':
    # ============= 配置区域 =============
    
    # 输入输出路径
    INPUT_DIR = "./input/现代粤语词典"
    OUTPUT_DIR = "./input/现代粤语词典_preprocessed"
    
    # 处理模式：
    # - balanced: 灰度增强，对比度适中
    # - high_contrast: 高对比度灰度增强（推荐用于现代粤语词典）
    # - binarize_adaptive: 自适应二值化（推荐OCR，效果最好）
    # - binarize_otsu: Otsu二值化（速度快）
    MODE = "high_contrast"  # 推荐用于OCR
    
    # 输出格式：png / jpg
    OUTPUT_FORMAT = "png"
    
    # 是否跳过已存在的文件
    SKIP_EXISTING = True
    
    # 处理范围（可选，None表示处理全部）
    START_FILE = None  # 例如: "image50"
    END_FILE = None    # 例如: "image100"
    
    # ===================================
    
    batch_preprocess(
        input_dir=INPUT_DIR,
        output_dir=OUTPUT_DIR,
        mode=MODE,
        image_format=OUTPUT_FORMAT,
        skip_existing=SKIP_EXISTING,
        start_file=START_FILE,
        end_file=END_FILE
    )
