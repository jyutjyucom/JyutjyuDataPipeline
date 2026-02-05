#!/usr/bin/env python3
"""
将现代粤语词典OCR输出转换为表格形式（CSV）

词条格式特点：
1. 字头（单字）：不用【】标记，如"吖 六画 (一) aa1 ①..."
2. 词头（多字词）：用【】标记，如"【吖啶】aa1 ding6 ..."
3. 多音字：可能有(一)(二)等标记

输出CSV列：
- 序号 (index)
- 类型 (entry_type): "字头" 或 "词头"
- 词条 (headword)
- 拼音 (pronunciation)
- 释义 (definition)
- 页码 (page)
- 来源文件 (source_file)
"""

import re
import csv
from pathlib import Path

# 汉字Unicode范围（支持基本汉字、扩展A-G和兼容汉字）
# 基本汉字: U+4E00-U+9FFF
# 扩展A: U+3400-U+4DBF
# 扩展B: U+20000-U+2A6DF
# 扩展C: U+2A700-U+2B73F
# 扩展D: U+2B740-U+2B81F
# 扩展E: U+2B820-U+2CEAF
# 扩展F: U+2CEB0-U+2EBEF
# 扩展G: U+30000-U+3134F
# 兼容汉字: U+F900-U+FAFF
# 兼容扩展: U+2F800-U+2FA1F
# 使用非捕获组包裹以避免优先级问题
HANZI_PATTERN = r'(?:[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]|[\U00020000-\U0002A6DF]|[\U0002A700-\U0002B73F]|[\U0002B740-\U0002B81F]|[\U0002B820-\U0002CEAF]|[\U0002CEB0-\U0002EBEF]|[\U00030000-\U0003134F]|[\U0002F800-\U0002FA1F])'


def extract_page_info(line: str) -> tuple[str, int] | None:
    """
    从页面标题行提取文件名和页码
    
    格式: --- 现代粤语词典（广州音 第一版）.范俊军.范兰德.2021_页面_0138.png ---
    """
    match = re.match(r'---\s*(.+?页面_(\d+)\.png)\s*---', line)
    if match:
        filename = match.group(1)
        page_num = int(match.group(2))
        return (filename, page_num)
    return None


def is_page_header(line: str) -> bool:
    """
    判断是否是页眉行
    
    页眉格式示例：
    - "22 ｜ bàn - bāng ｜ 扮伴拌绊样湴𩎓瓣邦帮"
    - "3 ｜ ā - áo ｜ 吖阿啊锕腌啊埃挨哀唉锿皑"
    - "10 ｜ ào，aad-am ｜ 奡傲奥骜澳薁懊鏊，𫇓𬬩捂"
    - "182 ｜ è ｜ 恶饿鄂谔竭萼遏崿愕噁腭碍鹗锷颚噩"
    
    注意：normalize_text已将半角竖线|转换为全角竖线｜
    """
    line = line.strip()
    
    # 检查是否是"页码 ｜ 拼音... ｜ ..."格式（全角竖线）
    # 支持：破折号连接、逗号分隔、单个拼音等多种格式
    # 注意：破折号可能是普通减号-（U+002D）或En Dash–（U+2013）或Em Dash—（U+2014）
    # 拼音中可能包含数字（如gung1）
    if re.match(r'^\d+\s*｜\s*[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ0-9\s\-–—,，、]+\s*｜', line, re.IGNORECASE):
        return True
    
    return False


def is_phonetic_section_header(line: str) -> bool:
    """
    判断是否是音节分区标题
    
    格式示例：
    - "A/a"
    - "ā"
    - "āi"
    - "ǎ"
    """
    line = line.strip()
    
    # 非常短的行
    if len(line) > 20:
        return False
    
    # 检查是否是纯拼音/声调标记
    if re.match(r'^[A-Za-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜɑɐɛəɔʻ/]+$', line):
        return True
    
    return False


def is_skip_line(line: str) -> bool:
    """
    判断是否应该跳过的行
    """
    line = line.strip()
    
    if not line:
        return True
    
    if line.startswith('==='):
        return True
    
    if line.startswith('---') and line.endswith('---'):
        return True
    
    # 注意：normalize_text已经将<>转换为〈〉
    if line.startswith('〈Token Count:') or line.startswith('<Token Count:'):
        return True
    
    if is_page_header(line):
        return True
    
    if is_phonetic_section_header(line):
        return True
    
    return False


def parse_headword_entry(text: str) -> tuple[str, str, str, str] | None:
    """
    解析词头条目（带【】标记）
    
    格式：【词条】拼音 释义内容
    返回: (entry_type, headword, pronunciation, definition)
    """
    # 匹配【词条】格式
    match = re.match(r'【(.+?)】\s*(.+)', text.strip(), re.DOTALL)
    if not match:
        return None
    
    headword = match.group(1)
    rest = match.group(2).strip()
    
    # 分离拼音和释义
    # 拼音格式：字母+数字（普通数字或上标数字），可能有多个音节，可能有逗号、顿号等分隔
    # 上标数字：¹²³⁴⁵⁶⁷⁸⁹
    # 释义通常以①、汉字词汇、〈外〉等标记开始
    
    # 寻找释义开始位置
    # 优先尝试匹配拼音模式，避免误将释义中的义项序号当作分隔点
    # 拼音可能的格式：aa5 bang1 giu5 gau3，yud9 giu5 yud9 zau3
    # 或者: aa1 naa2 / aa1 laa2
    # 或者带上标数字: baau¹ bou³
    # 支持普通数字 \d 和上标数字 ¹²³⁴⁵⁶⁷⁸⁹
    # 支持半角逗号,和全角逗号，
    pron_pattern = r'^((?:[a-z]+[\d¹²³⁴⁵⁶⁷⁸⁹]+(?:\*[\d¹²³⁴⁵⁶⁷⁸⁹]+|\')?\s*(?:,|，|、|丨|\/|\s)*)+)'
    pron_match = re.match(pron_pattern, rest, re.IGNORECASE)
    
    if pron_match:
        pron_part = pron_match.group(1).strip()
        def_part = rest[pron_match.end():].strip()
        
        # 如果提取的拼音后面紧跟中文词汇（非标点），可能提取过多
        # 需要在中文词汇开始前截断
        # 查找第一个连续的中文词汇（2个及以上汉字）
        chinese_match = re.search(rf'{HANZI_PATTERN}{{2,}}', pron_part)
        if chinese_match:
            # 在中文词汇前截断
            actual_pron = pron_part[:chinese_match.start()].strip()
            def_part = pron_part[chinese_match.start():] + def_part
            pron_part = actual_pron
    else:
        # 如果拼音模式匹配失败，尝试寻找释义常见开头
        def_start_match = re.search(r'(?:〈外〉|俗语[。，：]|见【|同"|\b[①②③④⑤⑥⑦⑧⑨⑩]|地名用字)', rest)
        if def_start_match:
            pron_part = rest[:def_start_match.start()].strip()
            def_part = rest[def_start_match.start():].strip()
        else:
            # 最后尝试用义项序号分割
            num_match = re.search(r'[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾❿]', rest)
            if num_match:
                pron_part = rest[:num_match.start()].strip()
                def_part = rest[num_match.start():].strip()
            else:
                # 无法识别拼音，整个作为释义
                pron_part = ""
                def_part = rest
    
    # 清理拼音部分末尾的标点
    pron_part = re.sub(r'[，、。；：]+$', '', pron_part).strip()
    
    # 将上标数字转换为普通数字（可选，便于后续处理）
    superscript_map = str.maketrans('¹²³⁴⁵⁶⁷⁸⁹', '123456789')
    pron_part = pron_part.translate(superscript_map)
    
    # 对释义部分再次应用阿拉伯数字转圆形序号（因为normalize_text是在整行调用的）
    def_part = convert_arabic_to_circle_in_definition(def_part)
    
    return ("词头", headword, pron_part, def_part)


def parse_character_entry(text: str) -> tuple[str, str, str, str] | None:
    """
    解析字头条目（不带【】标记）
    
    格式示例：
    - "吖 六画 (一) aa1 ①表示同意..."
    - "阿 aa5 七画 ①放在姓、名..."
    - "扮 七画 （一）baan6 ①装扮... （二）baan5 拿长棍..."
    - "办（辦） baan6 四画 ①处理..."
    - "锿 (鎄) oi1 十四画 金属元素..."
    - "挨 [捱] ngaai2/aai2 十画 ①遭受..."
    
    返回: (entry_type, headword, pronunciation, definition)
    """
    text = text.strip()
    
    # 提取字头（可能带繁体标注和同音字序号）
    # 繁体标注格式：（繁体）、(繁体)、［繁体］、【繁体】
    # 注意：［］是全角方括号（U+FF3B/FF3D），不是半角[]
    # 可能有多个繁体标注，如：诉（訴）［愬］
    # 繁体标注内可能包含多个字，用顿号或逗号分隔，如：暗［唵、闇］
    # 可能有同音字序号，如：摆1（擺）
    # 首先提取字头（第一个或前几个汉字，包含可能的多个繁体标注和序号）
    # 繁体标注模式：允许括号内有汉字和分隔符（、，等）
    char_match = re.match(rf'^({HANZI_PATTERN}+[0-9]?(?:\s*[（(【［](?:{HANZI_PATTERN}+[、，\s]*)+[）)】］]\s*)*)\s*(.+)', text)
    if not char_match:
        return None
    
    headword = char_match.group(1).strip()
    rest = char_match.group(2).strip()
    
    # 收集所有拼音和释义
    # 可能的格式：
    # 1. "拼音 笔画 释义"
    # 2. "笔画 拼音 释义"
    # 3. "笔画 (一) 拼音 释义 (二) 拼音 释义"
    
    # 移除"X画"标记
    rest = re.sub(r'[一二三四五六七八九十百]+画\s*', '', rest)
    
    # 处理多音字情况 (一)、(二)、（一）、（二）
    # 收集所有读音部分
    pronunciations = []
    definitions = []
    
    # 分割多音部分
    parts = re.split(r'[（(][一二三四五六七八九十][)）]', rest)
    
    if len(parts) > 1:
        # 有多音标记
        for part in parts:
            if not part.strip():
                continue
            
            # 从这部分提取拼音和释义
            part = part.strip()
            
            # 尝试找到拼音（支持普通数字和上标数字，支持斜杠分隔）
            pron_match = re.match(r'^([a-z]+[\d¹²³⁴⁵⁶⁷⁸⁹]+(?:[/\s]+[a-z]+[\d¹²³⁴⁵⁶⁷⁸⁹]+)*)\s+(.+)', part, re.IGNORECASE | re.DOTALL)
            if pron_match:
                pron = pron_match.group(1).strip()
                # 转换上标数字为普通数字
                superscript_map = str.maketrans('¹²³⁴⁵⁶⁷⁸⁹', '123456789')
                pron = pron.translate(superscript_map)
                pronunciations.append(pron)
                definitions.append(pron_match.group(2).strip())
            else:
                # 可能整个都是释义
                if part:
                    definitions.append(part)
    else:
        # 单音字或没有多音标记
        part = parts[0].strip()
        
        # 优先尝试匹配拼音模式（支持普通数字和上标数字，支持斜杠分隔）
        # 这样可以避免误将释义中的义项序号当作分隔点
        pron_match = re.match(r'^([a-z]+[\d¹²³⁴⁵⁶⁷⁸⁹]+(?:[/\s]+[a-z]+[\d¹²³⁴⁵⁶⁷⁸⁹]+)*)\s+(.+)', part, re.IGNORECASE | re.DOTALL)
        if pron_match:
            pron = pron_match.group(1).strip()
            def_text = pron_match.group(2).strip()
            # 转换上标数字为普通数字
            superscript_map = str.maketrans('¹²³⁴⁵⁶⁷⁸⁹', '123456789')
            pron = pron.translate(superscript_map)
            pronunciations.append(pron)
            definitions.append(def_text)
        else:
            # 如果拼音模式匹配失败，尝试用义项序号分割
            num_match = re.search(r'[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾❿]', part)
            if num_match:
                pron_part = part[:num_match.start()].strip()
                def_part = part[num_match.start():].strip()
                
                if pron_part:
                    # 转换上标数字为普通数字
                    superscript_map = str.maketrans('¹²³⁴⁵⁶⁷⁸⁹', '123456789')
                    pron_part = pron_part.translate(superscript_map)
                    pronunciations.append(pron_part)
                definitions.append(def_part)
            else:
                # 整个作为释义
                definitions.append(part)
    
    # 合并拼音和释义
    pron_str = ' / '.join(pronunciations) if pronunciations else ""
    def_str = ' '.join(definitions) if definitions else ""
    
    # 对释义部分再次应用阿拉伯数字转圆形序号（因为normalize_text是在整行调用的）
    def_str = convert_arabic_to_circle_in_definition(def_str)
    
    return ("字头", headword, pron_str, def_str)


def is_continuation_content(line: str) -> bool:
    """
    判断是否是词条释义的续行内容
    """
    line = line.strip()
    
    if not line:
        return False
    
    # 新词条的开始
    if line.startswith('【'):
        return False
    
    # "另见"和"又读"通常是字头条目的最后部分，但仍然是当前条目的一部分
    # 必须在字头模式检查之前检查，否则会被误判为新字头
    if line.startswith('另见') or line.startswith('又读'):
        return True
    
    # 可能是新字头的开始（汉字 + 拼音/笔画）
    # 需要考虑多种繁体标注格式：（繁体）、(繁体)、［繁体］、【繁体】
    # 注意：［］是全角方括号
    # 可能有多个繁体标注
    # 繁体标注内可能包含多个字，用顿号或逗号分隔，如：暗［唵、闇］
    # 拼音可能使用普通数字或上标数字 ¹²³⁴⁵⁶⁷⁸⁹
    # 支持扩展汉字（如㨘 U+3A18）
    # 支持同音字序号（如"摆1"）和无空格格式（如"摆（襬）baai3"）
    pattern = rf'^{HANZI_PATTERN}+[0-9]?(?:\s*[（(【［](?:{HANZI_PATTERN}+[、，\s]*)+[）)】］]\s*)*\s*(?:[a-z]+[\d¹²³⁴⁵⁶⁷⁸⁹]+|[一二三四五六七八九十百]+画)'
    if re.match(pattern, line, re.IGNORECASE):
        return False
    
    # 以义项序号开头 - 是续行
    if re.match(r'^[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾❿]', line):
        return True
    
    # 包含中文字符，且不是页眉或音节标题
    if re.search(HANZI_PATTERN, line):
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
        # 注意：此时已经过normalize_text，尖括号已转换为全角〈〉
        if line.startswith('===') or line.startswith('〈Token Count:'):
            continue
        
        result.append((line, current_page, current_source))
    
    return result


def convert_arabic_to_circle_in_definition(text: str) -> str:
    """
    将释义中的阿拉伯数字序号转换为圆形序号
    
    转换规则：
    - 文本开头的 "数字 空格" 
    - 句号、方括号等后面的 "数字 空格"
    
    不转换：
    - "10 分为 1 寸" 这样的单位换算
    - "在 7 月 6、7 或 8 日" 这样的日期
    """
    # 阿拉伯数字到圆形数字的映射
    arabic_to_circle = {
        '1': '①', '2': '②', '3': '③', '4': '④', '5': '⑤',
        '6': '⑥', '7': '⑦', '8': '⑧', '9': '⑨', '10': '⑩'
    }
    
    # 模式1：文本开头的"数字 空格"
    # 匹配：^1 梓树 或 ^2 雕版
    for num in ['10', '9', '8', '7', '6', '5', '4', '3', '2', '1']:  # 先匹配10，避免先匹配1
        pattern = rf'^{num}\s+'
        if re.match(pattern, text):
            text = re.sub(pattern, arabic_to_circle[num], text)
            break
    
    # 模式2：标点符号后的"数字 空格"（不包括顿号、逗号，避免误转换日期）
    # 匹配：。2 或 ］。2
    for num in ['10', '9', '8', '7', '6', '5', '4', '3', '2', '1']:
        # 在句号、右方括号、右圆括号等后面
        pattern = rf'([。］）\]])\s*{num}\s+'
        replacement = r'\1' + arabic_to_circle[num]
        text = re.sub(pattern, replacement, text)
    
    return text


def normalize_text(text: str) -> str:
    """
    标准化文本：
    1. 将各种格式的序号统一为圆圈数字
    2. 统一括号格式（圆括号统一为全角（），方括号统一为全角［］）
    3. 统一尖括号格式（统一为全角〈〉）
    4. 将释义中的阿拉伯数字序号转换为圆形序号
    """
    # Emoji数字转圆圈数字
    emoji_to_circle = {
        '1️⃣': '①', '2️⃣': '②', '3️⃣': '③', '4️⃣': '④', '5️⃣': '⑤',
        '6️⃣': '⑥', '7️⃣': '⑦', '8️⃣': '⑧', '9️⃣': '⑨', '🔟': '⑩'
    }
    for emoji, circle in emoji_to_circle.items():
        text = text.replace(emoji, circle)
    
    # 实心序号转空心序号
    solid_to_hollow = {
        '❶': '①', '❷': '②', '❸': '③', '❹': '④', '❺': '⑤',
        '❻': '⑥', '❼': '⑦', '❽': '⑧', '❾': '⑨', '❿': '⑩'
    }
    for solid, hollow in solid_to_hollow.items():
        text = text.replace(solid, hollow)
    
    # 将释义中的阿拉伯数字序号转换为圆形序号
    text = convert_arabic_to_circle_in_definition(text)
    
    # 统一括号格式
    # 半角圆括号 () 转全角圆括号 （）
    text = text.replace('(', '（').replace(')', '）')
    # 半角方括号 [] 转全角方括号 ［］
    text = text.replace('[', '［').replace(']', '］')
    # 半角尖括号 <> 转全角尖括号 〈〉
    text = text.replace('<', '〈').replace('>', '〉')
    # 将释义例句的半角竖线转换为全角竖线
    text = text.replace('|', '｜')
    return text


def parse_ocr_file(input_path: str) -> list[dict]:
    """
    解析OCR输出文件，返回词条列表
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 标准化所有行
    lines = [normalize_text(line) for line in lines]
    
    # 预处理：标记每行的页码
    processed_lines = preprocess_lines(lines)
    
    # 收集所有词条
    entries = []
    i = 0
    
    while i < len(processed_lines):
        line, page, source = processed_lines[i]
        
        # 跳过应该忽略的行
        if is_skip_line(line):
            i += 1
            continue
        
        # 跳过孤立的"又读"和"另见"行（这些应该是上一个条目的延续，但被OCR单独识别了）
        if line.strip().startswith('又读') or line.strip().startswith('另见'):
            print(f"警告：发现孤立的特殊行（第{i}行）: {line.strip()[:50]}")
            i += 1
            continue
        
        # 检查是否是词头（带【】）
        if line.strip().startswith('【'):
            # 收集这个词条的所有内容（包括续行）
            entry_lines = [line]
            j = i + 1
            
            while j < len(processed_lines):
                next_line, next_page, next_source = processed_lines[j]
                
                # 遇到新词条，停止
                if next_line.strip().startswith('【'):
                    break
                
                # 遇到新字头，停止（支持同音字序号、无空格格式、繁体标注中的分隔符）
                # 但"又读"和"另见"不算新字头
                if next_line.strip() and not next_line.strip().startswith('又读') and not next_line.strip().startswith('另见'):
                    pattern = rf'^{HANZI_PATTERN}+[0-9]?(?:\s*[（(【［](?:{HANZI_PATTERN}+[、，\s]*)+[）)】］]\s*)*\s*(?:[a-z]+[\d¹²³⁴⁵⁶⁷⁸⁹]+|[一二三四五六七八九十百]+画)'
                    if re.match(pattern, next_line.strip(), re.IGNORECASE):
                        break
                
                # 如果是续行内容，添加
                if is_continuation_content(next_line):
                    entry_lines.append(next_line)
                    j += 1
                elif is_skip_line(next_line):
                    j += 1
                else:
                    break
            
            # 解析词头条目
            full_text = ''.join(entry_lines)
            parsed = parse_headword_entry(full_text)
            if parsed:
                entry_type, headword, pron, defn = parsed
                entries.append({
                    'entry_type': entry_type,
                    'headword': headword,
                    'pronunciation': pron,
                    'definition': defn,
                    'page': page,
                    'source_file': source
                })
            
            i = j
            
        # 检查是否是字头（不带【】，但以汉字开头）
        # 可能有多个繁体标注（注意：［］是全角方括号）
        # 繁体标注内可能包含多个字，用顿号或逗号分隔，如：暗［唵、闇］
        # 支持扩展汉字
        # 支持同音字序号（如"摆1"）和无空格格式（如"摆（襬）baai3"）
        elif re.match(rf'^{HANZI_PATTERN}+[0-9]?(?:\s*[（(【［](?:{HANZI_PATTERN}+[、，\s]*)+[）)】］]\s*)*\s*(?:[a-z]+[\d¹²³⁴⁵⁶⁷⁸⁹]+|[一二三四五六七八九十百]+画)', line.strip(), re.IGNORECASE):
            # 收集这个字头的所有内容
            entry_lines = [line]
            j = i + 1
            
            while j < len(processed_lines):
                next_line, next_page, next_source = processed_lines[j]
                
                # 遇到新词条，停止
                if next_line.strip().startswith('【'):
                    break
                
                # "另见"和"又读"行是字头的一部分
                if next_line.strip().startswith('另见') or next_line.strip().startswith('又读'):
                    entry_lines.append(next_line)
                    j += 1
                    continue
                
                # 遇到新字头，停止（支持同音字序号、无空格格式、繁体标注中的分隔符）
                pattern = rf'^{HANZI_PATTERN}+[0-9]?(?:\s*[（(【［](?:{HANZI_PATTERN}+[、，\s]*)+[）)】］]\s*)*\s*(?:[a-z]+[\d¹²³⁴⁵⁶⁷⁸⁹]+|[一二三四五六七八九十百]+画)'
                if next_line.strip() and re.match(pattern, next_line.strip(), re.IGNORECASE):
                    break
                
                # 如果是续行内容，添加
                if is_continuation_content(next_line):
                    entry_lines.append(next_line)
                    j += 1
                elif is_skip_line(next_line):
                    j += 1
                else:
                    break
            
            # 解析字头条目
            full_text = ''.join(entry_lines)
            parsed = parse_character_entry(full_text)
            if parsed:
                entry_type, headword, pron, defn = parsed
                entries.append({
                    'entry_type': entry_type,
                    'headword': headword,
                    'pronunciation': pron,
                    'definition': defn,
                    'page': page,
                    'source_file': source
                })
            
            i = j
        else:
            i += 1
    
    return entries


def save_to_csv(entries: list[dict], output_path: str):
    """
    将词条保存为CSV文件
    """
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'index', 'entry_type', 'headword', 'pronunciation', 'definition', 'page', 'source_file'
        ])
        writer.writeheader()
        for idx, entry in enumerate(entries, 1):
            entry['index'] = idx
            writer.writerow(entry)


def main():
    input_path = Path(__file__).parent / 'output' / '现代粤语词典_OCR_output.txt'
    output_path = Path(__file__).parent / 'output' / '现代粤语词典_table.csv'
    
    print(f"读取OCR输出文件: {input_path}")
    entries = parse_ocr_file(str(input_path))
    
    print(f"解析得到 {len(entries)} 个词条")
    
    # 显示前几个词条作为示例
    print("\n前20个词条示例：")
    print("-" * 80)
    for entry in entries[:20]:
        type_mark = "字" if entry['entry_type'] == "字头" else "词"
        headword_display = f"{entry['headword']}"
        if entry['entry_type'] == "词头":
            headword_display = f"【{headword_display}】"
        
        print(f"[{type_mark}] {headword_display}")
        print(f"  拼音: {entry['pronunciation']}")
        defn_preview = entry['definition'][:80] + "..." if len(entry['definition']) > 80 else entry['definition']
        print(f"  释义: {defn_preview}")
        print(f"  页码: {entry['page']}")
        print()
    
    # 保存为CSV
    save_to_csv(entries, str(output_path))
    print(f"\n已保存到: {output_path}")
    
    # 统计信息
    print(f"\n统计信息：")
    print(f"  总词条数: {len(entries)}")
    
    char_entries = [e for e in entries if e['entry_type'] == '字头']
    word_entries = [e for e in entries if e['entry_type'] == '词头']
    print(f"  字头数量: {len(char_entries)}")
    print(f"  词头数量: {len(word_entries)}")
    
    pages = set(e['page'] for e in entries if e['page'] > 0)
    if pages:
        print(f"  涵盖页数: {len(pages)} ({min(pages)} - {max(pages)})")
    
    # 检查拼音提取情况
    with_pron = sum(1 for e in entries if e['pronunciation'])
    print(f"  有拼音的词条: {with_pron} ({with_pron/len(entries)*100:.1f}%)")


if __name__ == '__main__':
    main()
