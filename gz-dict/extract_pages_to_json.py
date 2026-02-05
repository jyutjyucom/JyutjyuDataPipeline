"""
将广州话词典（提取文字）.txt 按页码分割并输出为JSON格式
参考 OCR_openrouter_gz-dict.py 的算法，确保页码一一对应
"""

import json
import os
from pathlib import Path


def load_existing_ocr_text(ocr_file_path: str) -> str:
    """
    Load the existing OCR text file
    
    Args:
        ocr_file_path: Path to the existing OCR text file
        
    Returns:
        str: Content of the existing OCR text
    """
    try:
        with open(ocr_file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"错误：找不到OCR文本文件 {ocr_file_path}")
        return ""
    except Exception as e:
        print(f"错误：读取OCR文本时发生错误: {e}")
        return ""


def build_page_index(full_ocr_text: str) -> dict:
    """
    Build an index of page numbers and their line positions in the OCR text
    Page numbers appear as standalone lines (e.g., "1", "2", "3", etc.)
    
    Args:
        full_ocr_text: The complete existing OCR text
        
    Returns:
        dict: Mapping of page_num -> line_index
    """
    if not full_ocr_text:
        return {}
    
    lines = full_ocr_text.split('\n')
    page_index = {}
    
    for i, line in enumerate(lines):
        # Check if line is a standalone number (page marker)
        stripped = line.strip()
        if stripped.isdigit():
            page_num = int(stripped)
            # Only add if it's in reasonable page range (1-1000)
            if 1 <= page_num <= 1000:
                page_index[page_num] = i
    
    return page_index


def extract_page_content(full_ocr_text: str, ocr_page_num: int, page_index: dict) -> str:
    """
    Extract complete content for the specified OCR page number
    
    Page extraction rules:
    - Page 1: from file start to page marker "1" (including marker "1")
    - Page N (N>1): from after page marker "N-1" to page marker "N" (including marker "N")
    
    Args:
        full_ocr_text: The complete existing OCR text
        ocr_page_num: OCR page number (1-539)
        page_index: Dictionary mapping page numbers to line positions
        
    Returns:
        str: Extracted content text for this page
    """
    if not full_ocr_text:
        return ""
    
    if not page_index:
        return ""
    
    if ocr_page_num not in page_index:
        return ""
    
    lines = full_ocr_text.split('\n')
    
    if ocr_page_num == 1:
        # Page 1: from file start to page marker "1" (including marker "1")
        end_line = page_index[1] + 1  # Include the marker line
        content_lines = lines[0:end_line]
    else:
        # Page N: from after page marker "N-1" to page marker "N" (including marker "N")
        prev_page_num = ocr_page_num - 1
        if prev_page_num not in page_index:
            return ""
        
        start_line = page_index[prev_page_num] + 1  # After previous marker
        end_line = page_index[ocr_page_num] + 1  # Include current marker
        content_lines = lines[start_line:end_line]
    
    content = '\n'.join(content_lines)
    
    # Remove trailing empty lines
    content = content.rstrip('\n')
    
    return content


def extract_all_pages_to_json(ocr_file_path: str, output_json_path: str):
    """
    Extract all pages from OCR text and save as JSON
    
    Args:
        ocr_file_path: Path to the existing OCR text file
        output_json_path: Path to save the JSON output file
    """
    print(f"正在加载OCR文本: {ocr_file_path}")
    full_ocr_text = load_existing_ocr_text(ocr_file_path)
    
    if not full_ocr_text:
        print("错误：无法加载OCR文本")
        return
    
    print(f"✓ 已加载OCR文本 ({len(full_ocr_text)} 字符)")
    
    # Build page index
    print("正在构建页码索引...")
    page_index = build_page_index(full_ocr_text)
    
    if not page_index:
        print("错误：未找到任何页码标记")
        return
    
    print(f"✓ 已构建页码索引，找到 {len(page_index)} 个页码标记")
    
    if page_index:
        min_page = min(page_index.keys())
        max_page = max(page_index.keys())
        print(f"  OCR文本页码范围：第{min_page}页 - 第{max_page}页")
        print(f"  对应实际书页：第{min_page+120}页 - 第{max_page+120}页")
    
    # Extract all pages
    print("\n正在提取各页内容...")
    pages_data = []
    
    # Sort page numbers
    sorted_page_nums = sorted(page_index.keys())
    
    for ocr_page_num in sorted_page_nums:
        actual_page_num = ocr_page_num + 120  # OCR页码1-539对应实际页码121-659
        
        # Extract page content
        page_content = extract_page_content(full_ocr_text, ocr_page_num, page_index)
        
        page_entry = {
            "ocr_page_num": ocr_page_num,  # OCR文本中的页码 (1-539)
            "actual_page_num": actual_page_num,  # 实际书页页码 (121-659)
            "content": page_content,
            "content_length": len(page_content),
            "line_count": len(page_content.split('\n')) if page_content else 0
        }
        
        pages_data.append(page_entry)
        
        if ocr_page_num % 50 == 0 or ocr_page_num == sorted_page_nums[-1]:
            print(f"  已处理: OCR页码 {ocr_page_num} (实际页码 {actual_page_num})")
    
    # Create output structure
    output_data = {
        "source_file": ocr_file_path,
        "total_pages": len(pages_data),
        "ocr_page_range": {
            "min": min_page,
            "max": max_page
        },
        "actual_page_range": {
            "min": min_page + 120,
            "max": max_page + 120
        },
        "pages": pages_data
    }
    
    # Save to JSON file
    print(f"\n正在保存JSON文件: {output_json_path}")
    os.makedirs(os.path.dirname(output_json_path) if os.path.dirname(output_json_path) else '.', exist_ok=True)
    
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 完成！已保存 {len(pages_data)} 页数据到 {output_json_path}")
    
    # Print summary statistics
    total_chars = sum(page['content_length'] for page in pages_data)
    total_lines = sum(page['line_count'] for page in pages_data)
    print(f"\n统计信息:")
    print(f"  总页数: {len(pages_data)}")
    print(f"  总字符数: {total_chars:,}")
    print(f"  总行数: {total_lines:,}")
    print(f"  平均每页字符数: {total_chars // len(pages_data) if pages_data else 0:,}")
    print(f"  平均每页行数: {total_lines // len(pages_data) if pages_data else 0}")


def main():
    """Main execution function"""
    # Configuration
    ocr_file_path = "./input/广州话词典（提取文字）.txt"
    output_json_path = "./output/广州话词典_分页结果.json"
    
    print("="*80)
    print("广州话词典 分页提取工具")
    print(f"输入文件: {ocr_file_path}")
    print(f"输出文件: {output_json_path}")
    print("="*80)
    print()
    
    # Check if input file exists
    if not os.path.exists(ocr_file_path):
        print(f"❌ 错误: 输入文件不存在: {ocr_file_path}")
        return
    
    # Process and extract pages
    extract_all_pages_to_json(ocr_file_path, output_json_path)


if __name__ == '__main__':
    main()
