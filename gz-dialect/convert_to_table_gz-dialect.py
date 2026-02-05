#!/usr/bin/env python3
"""
将广州方言词典OCR输出转换为表格形式（CSV）

词条格式示例：
【巴閉】baa1' bai3 ①副詞。表程度加深... ②興師動眾... ③了不起...

输出CSV列：
- 序号 (index)
- 词条 (headword)
- 拼音 (pronunciation)
- 释义 (definition)
- 页码 (page)
- 来源文件 (source_file)

注意：处理跨页接缝 - 当词条释义被分页断开时，需要合并
"""

import re
import csv
from pathlib import Path


def parse_entry(text: str) -> tuple[str, str, str] | None:
    """
    解析单个词条，提取词条、拼音和释义
    
    返回: (headword, pronunciation, definition) 或 None
    """
    # 匹配【词条】格式
    match = re.match(r'【(.+?)】\s*(.+)', text.strip(), re.DOTALL)
    if not match:
        return None
    
    headword = match.group(1)
    rest = match.group(2).strip()
    
    # 尝试分离拼音和释义
    # 拼音格式：粤拼音节（如 baa1', bai3 等），可能包含空格分隔的多个音节
    # 粤拼特征：字母+数字+可能的'或*符号
    
    # 寻找释义开始位置（通常是①或中文字符开始）
    # 先尝试找①②③这样的序号
    num_match = re.search(r'[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾❿]', rest)
    if num_match:
        # 有序号义项的情况
        pron_part = rest[:num_match.start()].strip()
        def_part = rest[num_match.start():].strip()
    else:
        # 没有序号的情况，拼音和释义之间可能直接连接
        # 尝试识别拼音部分结束位置
        # 拼音通常是 字母+数字+可选的变调标记 的组合，可能有空格
        # 例如: "baa1' bai3" 或 "maa4 maa4*2 dei6" 或 "juk6 waat6*2"
        # 变调标记格式：' 或 *数字（如 *2, *1, *5）
        
        # 策略：从头开始匹配连续的拼音模式
        # 音节格式：字母 + 数字 + 可选的(变调标记 *数字 或 ')
        pron_pattern = r'^((?:[a-z]+\d+(?:\*\d+|\')?\s*(?:\([^\)]+\)\s*)?)+)'
        pron_match = re.match(pron_pattern, rest, re.IGNORECASE)
        
        if pron_match:
            pron_part = pron_match.group(1).strip()
            def_part = rest[pron_match.end():].strip()
        else:
            # 无法识别拼音，整个作为释义
            pron_part = ""
            def_part = rest
    
    return (headword, pron_part, def_part)


def extract_page_info(line: str) -> tuple[str, int] | None:
    """
    从页面标题行提取文件名和页码
    
    格式: --- 廣州方言詞典.白宛如.1993_image50_out.png ---
    """
    match = re.match(r'---\s*(.+?_image(\d+)_out\.png)\s*---', line)
    if match:
        filename = match.group(1)
        page_num = int(match.group(2))
        return (filename, page_num)
    return None


def is_page_header(line: str) -> bool:
    """
    判断是否是页眉行
    
    页眉格式示例：
    - "麻嫲麻馬榪碼螞花 maa4-faa1 3"
    - "6 daa2 打"
    - "車斜扯 ce1-ce2 25"
    - "232  tou3 — tou6 倒妒毒度道渡"
    
    特征：包含拼音范围（如 maa4-faa1）或页码数字
    """
    line = line.strip()
    
    # 检查是否包含拼音范围格式（如 maa4-faa1, ce1-ce2, tou3 — tou6）
    if re.search(r'[a-z]+\d+[\*\']*\s*[-—]\s*[a-z]+\d+', line, re.IGNORECASE):
        return True
    
    # 检查是否是 "数字 拼音 汉字" 格式的页眉
    if re.match(r'^\d+\s+[a-z]+\d*', line, re.IGNORECASE):
        return True
    
    # 检查是否以数字结尾（页码）且包含拼音
    if re.match(r'.+\s+\d+$', line) and re.search(r'[a-z]+\d+', line, re.IGNORECASE):
        return True
    
    return False


def is_phonetic_section_header(line: str) -> bool:
    """
    判断是否是音节分区标题
    
    格式示例：
    - "pa"
    - "ma"
    - "pʻa"
    - "tou"
    - "**pɔ**"
    - "jje"
    - "oe"
    """
    line = line.strip()
    
    # 纯拼音行（可能带IPA符号或markdown格式）
    # 通常很短，只有1-10个字符
    if len(line) > 15:
        return False
    
    # 去掉markdown格式
    clean = re.sub(r'\*+', '', line).strip()
    
    # 检查是否是纯拼音/IPA（允许音标符号）
    if re.match(r'^[a-zɐɛəɔʻʰŋ]+$', clean, re.IGNORECASE):
        return True
    
    # 检查是否是带声调的拼音
    if re.match(r'^[a-z]+\d*$', clean, re.IGNORECASE):
        return True
    
    return False


def is_skip_line(line: str) -> bool:
    """
    判断是否应该跳过的行（页眉、音节标题、分隔符等）
    """
    line = line.strip()
    
    if not line:
        return True
    
    if line.startswith('==='):
        return True
    
    if line.startswith('---') and line.endswith('---'):
        return True
    
    if line.startswith('<Two-Stage Token Count:'):
        return True
    
    if is_page_header(line):
        return True
    
    if is_phonetic_section_header(line):
        return True
    
    return False


def is_continuation_content(line: str) -> bool:
    """
    判断是否是词条释义的续行内容
    
    续行特征：
    - 不以【开头
    - 包含中文释义内容
    - 可能以义项序号开头（如②③）
    - 可能是上一页词条释义的延续
    """
    line = line.strip()
    
    if not line:
        return False
    
    if line.startswith('【'):
        return False
    
    # 以义项序号开头
    if re.match(r'^[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾❿]', line):
        return True
    
    # 包含中文字符，且不是页眉
    if re.search(r'[\u4e00-\u9fff]', line):
        if not is_page_header(line) and not is_phonetic_section_header(line):
            return True
    
    return False


def preprocess_lines(lines: list[str]) -> list[tuple[str, int, str]]:
    """
    预处理所有行，识别每行的类型和所属页面
    
    返回: [(line_content, page_num, source_file), ...]
    """
    result = []
    current_page = 0
    current_source = ""
    
    for line in lines:
        line = line.rstrip('\n')
        
        # 检查是否是页面标题
        page_info = extract_page_info(line)
        if page_info:
            current_source, current_page = page_info
            continue
        
        # 跳过分隔符和token统计
        if line.startswith('===') or line.startswith('<Two-Stage Token Count:'):
            continue
        
        result.append((line, current_page, current_source))
    
    return result


def parse_ocr_file(input_path: str) -> list[dict]:
    """
    解析OCR输出文件，返回词条列表
    处理跨页接缝：将跨页的词条释义合并
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 预处理：标记每行的页码
    processed_lines = preprocess_lines(lines)
    
    # 第一遍：收集所有词条起始位置
    entry_starts = []
    for i, (line, page, source) in enumerate(processed_lines):
        if line.strip().startswith('【'):
            entry_starts.append(i)
    
    # 第二遍：为每个词条收集所有相关行（包括跨页续行）
    entries = []
    
    for idx, start_pos in enumerate(entry_starts):
        # 确定这个词条的结束位置（下一个词条开始前）
        if idx + 1 < len(entry_starts):
            end_pos = entry_starts[idx + 1]
        else:
            end_pos = len(processed_lines)
        
        # 收集这个词条的所有内容
        entry_lines = []
        entry_page = processed_lines[start_pos][1]
        entry_source = processed_lines[start_pos][2]
        
        for i in range(start_pos, end_pos):
            line, page, source = processed_lines[i]
            
            # 跳过应该忽略的行
            if is_skip_line(line):
                continue
            
            # 跳过空行（但记录词条可能跨页了）
            if not line.strip():
                continue
            
            # 添加内容行
            if line.strip().startswith('【') or is_continuation_content(line):
                entry_lines.append(line)
        
        # 合并所有行并解析
        if entry_lines:
            full_text = ''.join(entry_lines)
            parsed = parse_entry(full_text)
            if parsed:
                entries.append({
                    'headword': parsed[0],
                    'pronunciation': parsed[1],
                    'definition': parsed[2],
                    'page': entry_page,
                    'source_file': entry_source
                })
    
    return entries


def save_to_csv(entries: list[dict], output_path: str):
    """
    将词条保存为CSV文件
    """
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'index', 'headword', 'pronunciation', 'definition', 'page', 'source_file'
        ])
        writer.writeheader()
        for idx, entry in enumerate(entries, 1):
            entry['index'] = idx
            writer.writerow(entry)


def verify_seams(entries: list[dict], sample_headwords: list[str] = None):
    """
    验证跨页接缝是否正确合并
    """
    if sample_headwords is None:
        sample_headwords = ['扒龍舟', '麻甩仔', '花墩', '打硪']
    
    print("\n接缝验证：")
    print("-" * 80)
    for hw in sample_headwords:
        found = [e for e in entries if e['headword'] == hw]
        if found:
            entry = found[0]
            print(f"【{entry['headword']}】")
            print(f"  拼音: {entry['pronunciation']}")
            defn = entry['definition']
            if len(defn) > 100:
                print(f"  释义: {defn[:100]}...")
            else:
                print(f"  释义: {defn}")
            print(f"  页码: {entry['page']}")
            # 检查是否完整
            if defn.rstrip().endswith((',', '，', '、')):
                print(f"  ⚠️ 警告: 释义可能不完整（以标点结尾）")
            elif '‖' in defn and not defn.rstrip().endswith(('"', '"', '」', '）', ')')):
                # 有注释但可能不完整
                pass
            print()
        else:
            print(f"【{hw}】未找到")
            print()


def main():
    input_path = Path(__file__).parent / 'output' / '廣州方言詞典_OCR_output.txt'
    output_path = Path(__file__).parent / 'output' / '廣州方言詞典_table.csv'
    
    print(f"读取OCR输出文件: {input_path}")
    entries = parse_ocr_file(str(input_path))
    
    print(f"解析得到 {len(entries)} 个词条")
    
    # 验证跨页接缝
    verify_seams(entries)
    
    # 显示前几个词条作为示例
    print("\n前10个词条示例：")
    print("-" * 80)
    for entry in entries[:10]:
        print(f"【{entry['headword']}】")
        print(f"  拼音: {entry['pronunciation']}")
        print(f"  释义: {entry['definition'][:60]}..." if len(entry['definition']) > 60 else f"  释义: {entry['definition']}")
        print(f"  页码: {entry['page']}")
        print()
    
    # 保存为CSV
    save_to_csv(entries, str(output_path))
    print(f"\n已保存到: {output_path}")
    
    # 统计信息
    print(f"\n统计信息：")
    print(f"  总词条数: {len(entries)}")
    pages = set(e['page'] for e in entries)
    print(f"  涵盖页数: {len(pages)} ({min(pages)} - {max(pages)})")
    
    # 检查拼音提取情况
    with_pron = sum(1 for e in entries if e['pronunciation'])
    print(f"  有拼音的词条: {with_pron} ({with_pron/len(entries)*100:.1f}%)")
    
    # 检查可能不完整的词条
    incomplete = [e for e in entries if e['definition'].rstrip().endswith((',', '，', '、'))]
    print(f"  可能不完整的词条: {len(incomplete)}")
    if incomplete:
        print("  示例:")
        for e in incomplete[:5]:
            print(f"    【{e['headword']}】p.{e['page']}: ...{e['definition'][-30:]}")


if __name__ == '__main__':
    main()
