"""
将《开平方言》OCR 结果 TXT 转为 CSV。

输入：output/开平方言_OCR_106-268.txt
输出：output/开平方言_OCR_106-268.csv

注意：
- 书内 106–247 页为单行词条格式：开平话 + IPA + 普通话解释
- 书内 248 页开始为另一种格式，多为“汉字行 + IPA 行”成对出现（有时 IPA 在前，有时在后）
- 本脚本通过检测书页页码（行中只有数字）来判断格式区间：
  - 书页 < 248 视为“词汇”区（lexicon）
  - 书页 >= 248 视为“谚语 / 歇后语等”区（proverb）

CSV 字段：
- image_page  ：PNG 文件名中的页码编号（如 106）
- book_page   ：书内页码（如 92、248）
- section     ："lexicon" 或 "proverb"
- kp_text     ：开平话（汉字部分 / 词条）
- ipa         ：IPA 读音（数字声调已在 OCR 时转换）
- mandarin    ：普通话解释或括号中的释义（若有）
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


INPUT_TXT = "./output/开平方言_OCR_106-268.txt"
OUTPUT_CSV = "./output/开平方言_OCR_106-268.csv"


@dataclass
class Entry:
    image_page: Optional[int]
    book_page: Optional[int]
    section: str  # "lexicon" or "proverb"
    kp_text: str
    ipa: str
    mandarin: str


def is_cjk(ch: str) -> bool:
    """Rough detection of CJK characters."""
    code = ord(ch)
    # CJK Unified Ideographs & extensions + fullwidth punctuation etc.
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0xF900 <= code <= 0xFAFF
        or 0x3000 <= code <= 0x303F  # CJK punctuation
    )


def is_separator_line(s: str) -> bool:
    """Check if the line is a technical separator/header line."""
    if not s:
        return True
    if s.startswith("--- ") and "页面_" in s:
        return True
    if s.startswith("<Token Count:"):
        return True
    if set(s) <= {"=", "-"}:
        return True
    return False


def should_skip_line(s: str) -> bool:
    """
    判断是否应该跳过该行（非词条内容）。
    包括：标题、说明、章节标题等。
    """
    if not s:
        return True
    
    # 标题行
    if s in ["词汇篇", "开平话.普通话对照词语 3000 例"]:
        return True
    
    # 说明行（通常包含"说明"、"冒号"等关键词）
    if "说明" in s or ("冒号" in s and "后为举例" in s):
        return True
    
    # 章节标题：格式如 "01.阿[a]部"、"02. 矮[ai]部"、"07. 鸭 [ap] 部"
    # 匹配：数字 + 点 + 可选空格 + 汉字 + 可选空格 + [音标] + 可选空格 + 部
    if re.match(r"^\d+\.\s*.*?\[[^\]]+\].*?部\s*$", s):
        return True
    
    return False


def is_proverb_section_title(s: str) -> bool:
    """
    判断是否是谚语/歇后语部分的标题。
    这些标题出现时，应该切换到proverb模式。
    """
    if not s:
        return False
    if s in ["开平话常用谚语和俗语", "开平话常用歇后语"]:
        return True
    return False


def extract_image_page(header_line: str) -> Optional[int]:
    """
    从形如：
    --- 开平方言.邓钧.2000_页面_106.png ---
    中提取 106 作为 image_page。
    """
    m = re.search(r"页面_(\d+)\.png", header_line)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def split_head_and_rest_lexicon(line: str) -> Tuple[str, str]:
    """
    对 106–247 页的"词汇"行进行初步拆分：
    - 先按第一个空白拆成：head_token + rest
    - 如果词头后面直接跟着IPA（没有空格，如"哗va32"），需要分离
    - 如果 head_token 尾部粘有 IPA（如"麻石ma11"），尝试把末尾的 ASCII+数字部分剥离出来并并入 rest。
    - 如果 rest 开头是数字（如"1 tsui33"），这是用来区分不同词语的，应该合并到 head_token 中（如"锥1"）。
    """
    # 先尝试按空格分割
    m = re.match(r"^(\S+)\s+(.*)$", line)
    if not m:
        # 如果没有空格，可能是词头后面直接跟着IPA（如"哗va32哟;嚯"）
        # 需要找到词头（CJK字符）和IPA的分界点
        line_stripped = line.strip()
        if not line_stripped:
            return "", ""
        
        # 找到第一个连续的CJK字符序列的结束位置（词头）
        # 对于"哗va32哟;嚯"，词头应该是"哗"，rest应该是"va32哟;嚯"
        # 对于"那.na33连接"，词头应该是"那."（包括标点），rest应该是"na33连接"
        first_cjk_end_idx = None
        for i in range(len(line_stripped)):
            if is_cjk(line_stripped[i]):
                # 找到第一个CJK字符，继续找连续的CJK字符序列
                first_cjk_end_idx = i
            elif first_cjk_end_idx is not None:
                # 已经找到了CJK字符序列，现在遇到非CJK字符
                # 如果是标点符号（如"."、"〉"等），应该包含在词头中
                if line_stripped[i] in ".,。，〉>":
                    first_cjk_end_idx = i
                else:
                    # 遇到其他字符（可能是IPA的开始），停止
                    break
        
        if first_cjk_end_idx is not None and first_cjk_end_idx < len(line_stripped) - 1:
            # 有CJK字符序列，且后面还有内容
            # 词头是到第一个CJK字符序列的结束位置（包括可能的标点）
            head_token = line_stripped[:first_cjk_end_idx + 1]
            # rest是后面的部分（包含IPA和可能的mandarin）
            rest = line_stripped[first_cjk_end_idx + 1:]
        else:
            # 没有找到CJK字符，整个作为词头
            return line_stripped, ""
    else:
        head_token = m.group(1)
        rest = m.group(2)

    # 检查 rest 开头是否是标记符号（如"}"、"]"、")"等），这些应该合并到词头中
    # 格式：词头 + 空格 + 标记符号 + 空格 + IPA + ...
    # 或者：词头 + 空格 + 标记符号 + 空格 + CJK字符 + 空格 + IPA + ...
    rest_stripped = rest.strip()
    if rest_stripped:
        # 检查是否以标记符号开头（如"}"、"]"、")"等）
        marker_match = re.match(r"^([}\]\)])\s+(.*)$", rest_stripped)
        if marker_match:
            # 标记符号应该合并到词头中，如"雍 }" -> "雍}"
            marker = marker_match.group(1)
            rest_after_marker = marker_match.group(2)
            head_token = head_token + marker
            
            # 检查标记符号后面是否还有CJK字符（如"雍 } 芋" -> "雍} 芋"）
            rest_after_marker_stripped = rest_after_marker.strip()
            if rest_after_marker_stripped:
                # 检查是否以CJK字符开头
                cjk_match = re.match(r"^([^\s]+)\s+(.*)$", rest_after_marker_stripped)
                if cjk_match:
                    potential_cjk = cjk_match.group(1)
                    # 检查是否主要是CJK字符
                    if any(is_cjk(ch) for ch in potential_cjk):
                        # CJK字符应该合并到词头中，如"雍} 芋" -> "雍}芋"
                        head_token = head_token + potential_cjk
                        rest = cjk_match.group(2)
                    else:
                        rest = rest_after_marker
                else:
                    rest = rest_after_marker
            else:
                rest = rest_after_marker
        
        # 检查是否以CJK字符开头（如"系该°LE 哪"中的"哪"应该合并到词头）
        # 格式：词头 + 空格 + CJK字符 + 空格 + IPA + ...
        # 注意：如果开头是IPA字符（字母、数字），不应该合并
        if rest_stripped:  # 重新检查rest（可能已经被上面的逻辑修改）
            # 先检查是否以IPA字符开头（字母、数字、IPA符号），如果是则跳过
            first_char = rest_stripped[0]
            if not (first_char.isalnum() or first_char in "'‘'\u0250-\u02AF\u0300-\u036F"):
                cjk_match = re.match(r"^([^\s]+)\s+(.*)$", rest.strip())
                if cjk_match:
                    potential_cjk = cjk_match.group(1)
                    # 检查是否主要是CJK字符（而不是包含IPA字符）
                    # 如果包含字母或数字，说明可能是IPA，不应该合并
                    if any(is_cjk(ch) for ch in potential_cjk) and not any(ch.isalnum() for ch in potential_cjk):
                        # 检查后面是否跟着IPA（而不是解释）
                        rest_after_cjk = cjk_match.group(2).strip()
                        # 如果后面是IPA（以字母或数字开头），则合并CJK字符到词头
                        if rest_after_cjk and (rest_after_cjk[0].isalnum() or rest_after_cjk[0] in "'‘'"):
                            # CJK字符应该合并到词头中，如"系该°LE 哪" -> "系该°LE 哪"
                            head_token = head_token + " " + potential_cjk
                            rest = rest_after_cjk
        
        # 检查是否以数字开头（用于区分不同词语，如"锥 1 tsui33"）
        # 格式：词头 + 空格 + 数字 + 空格 + IPA + ...
        if rest_stripped:  # 重新检查rest（可能已经被上面的逻辑修改）
            rest_stripped = rest.strip()
            if rest_stripped:
                num_match = re.match(r"^(\d+)\s+(.*)$", rest_stripped)
                if num_match:
                    # 数字应该合并到词头中，如"锥 1" -> "锥1"
                    num = num_match.group(1)
                    rest = num_match.group(2)
                    head_token = head_token + num

    # 从后往前找最后一个 CJK 字符，把其后的 ASCII 视为可能的 IPA 前缀
    split_idx = None
    for i in range(len(head_token) - 1, -1, -1):
        if is_cjk(head_token[i]):
            split_idx = i
            break

    if split_idx is not None and split_idx < len(head_token) - 1:
        # 一些标记符号（如 ], ), }, ｝, ·, -, 〉 等）属于词头的后缀，
        # 不应被当作 IPA 前缀拆出去，例如「湛}1」「带枚}」等。
        postfix_markers = set("]}｝）)〉》·*-")
        j = split_idx + 1
        while j < len(head_token) and head_token[j] in postfix_markers:
            split_idx = j
            j += 1
        
        head_part = head_token[: split_idx + 1]
        suffix = head_token[split_idx + 1 :]
        # 只有在后缀含有数字（可能是声调）时才认为是 IPA
        # 但如果后缀只是数字（如"锥1"中的"1"），不应该剥离
        if any(ch.isdigit() for ch in suffix) and not suffix.isdigit():
            rest = (suffix + " " + rest).strip()
            head_token = head_part

    return head_token.strip(), rest.strip()


def split_ipa_and_mandarin(rest: str) -> Tuple[str, str]:
    """
    从“词汇”行的剩余部分中拆分 IPA 与普通话解释。
    策略：
    1. 先检查是否有括号内容（`<>`或`()`），这些应该归入mandarin部分
    2. 从左到右扫描，遇到第一个明显的 CJK 字符或中文标点时，
       之前视为 IPA，之后视为普通话解释
    3. 括号内容（包括括号本身）应该归入mandarin部分
    """
    if not rest:
        return "", ""

    # 先找到所有括号内容的位置（包括`<>`和`()`）
    bracket_ranges: List[Tuple[int, int]] = []
    
    # 找`<>`括号
    i = 0
    while i < len(rest):
        if rest[i] == '<':
            start = i
            i += 1
            while i < len(rest) and rest[i] != '>':
                i += 1
            if i < len(rest) and rest[i] == '>':
                bracket_ranges.append((start, i + 1))
        i += 1
    
    # 找`()`括号
    i = 0
    while i < len(rest):
        if rest[i] == '(':
            start = i
            i += 1
            while i < len(rest) and rest[i] != ')':
                i += 1
            if i < len(rest) and rest[i] == ')':
                bracket_ranges.append((start, i + 1))
        i += 1
    
    # 合并重叠的括号范围
    if bracket_ranges:
        bracket_ranges.sort()
        merged = [bracket_ranges[0]]
        for start, end in bracket_ranges[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(end, last_end))
            else:
                merged.append((start, end))
        bracket_ranges = merged
    
    # 判断每个字符是否在括号内
    def is_in_bracket(pos: int) -> bool:
        for start, end in bracket_ranges:
            if start <= pos < end:
                return True
        return False
    
    ipa_chars: List[str] = []
    mandarin_chars: List[str] = []
    seen_cjk = False
    in_ipa_region = True  # 是否还在IPA区域

    for i, ch in enumerate(rest):
        # 如果字符在括号内，直接归入mandarin
        if is_in_bracket(i):
            mandarin_chars.append(ch)
            seen_cjk = True
            in_ipa_region = False
            continue
        
        # 如果已经看到CJK字符，后续都归入mandarin
        if seen_cjk:
            mandarin_chars.append(ch)
            continue
        
        # 检查是否是CJK字符
        if is_cjk(ch):
            seen_cjk = True
            in_ipa_region = False
            mandarin_chars.append(ch)
        elif in_ipa_region:
            # 还在IPA区域，检查是否是IPA字符（字母、数字、IPA符号、空格、声门塞音标记等）
            # 分号（；或;）也可以作为IPA分隔符，应该保留在IPA中
            if ch.isalnum() or ch in " \t\u0250-\u02AF\u0300-\u036F'‘'；;":
                ipa_chars.append(ch)
            else:
                # 遇到非IPA字符，切换到mandarin区域
                in_ipa_region = False
                mandarin_chars.append(ch)
        else:
            mandarin_chars.append(ch)

    ipa = "".join(ipa_chars).strip()
    mandarin = "".join(mandarin_chars).strip()

    # 规范空白：去掉首尾空格，并将中间连续空格压缩为单个空格
    if ipa:
        ipa = " ".join(ipa.split())
    if mandarin:
        mandarin = " ".join(mandarin.split())

    return ipa, mandarin


def extract_parenthetical_chinese(s: str) -> str:
    """
    提取汉字行中括号里的中文解释，用作 mandarin 字段。
    同时支持全角/半角括号。
    """
    parts: List[str] = []
    # 半角括号
    for m in re.finditer(r"\(([^)]*?)\)", s):
        parts.append(m.group(1).strip())
    # 全角括号
    for m in re.finditer(r"（([^）]*?)）", s):
        parts.append(m.group(1).strip())

    # 去掉空的片段
    parts = [p for p in parts if p]
    return "；".join(parts)


def strip_parentheses(s: str) -> str:
    """去除字符串中的中英文括号内容，仅保留主体句子。"""
    s = re.sub(r"\([^)]*?\)", "", s)
    s = re.sub(r"（[^）]*?）", "", s)
    return s.strip()


def remove_trailing_period(s: str) -> str:
    """移除字符串结尾的句号（中文或英文）。"""
    s = s.rstrip()
    if s.endswith("。"):
        return s[:-1]
    if s.endswith("."):
        return s[:-1]
    return s


def normalize_commas(s: str) -> str:
    """将字符串中的半角逗号替换为全角逗号。"""
    return s.replace(",", "，")


def parse_txt_to_entries(path: str) -> List[Entry]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    entries: List[Entry] = []
    current_image_page: Optional[int] = None
    current_book_page: Optional[int] = None
    section = "lexicon"  # or "proverb"

    pending_ipa: Optional[str] = None  # 只用于 section == "proverb"
    
    # 用于回溯更新 book_page：记录当前 image_page 下已添加的条目索引
    entries_for_current_image: List[int] = []

    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        s = raw.strip()

        # 分隔与 header 处理
        if not s:
            i += 1
            continue

        if s.startswith("--- ") and "页面_" in s:
            current_image_page = extract_image_page(s)
            current_book_page = None  # 重置，等待从内容末尾读取
            entries_for_current_image = []  # 重置当前页的条目索引
            # 如果image_page >= 248，自动切换到proverb模式（248页开始是谚语/歇后语）
            if current_image_page is not None and current_image_page >= 248:
                section = "proverb"
            i += 1
            continue

        if s.startswith("<Token Count:"):
            i += 1
            continue

        if set(s) <= {"=", "-"}:
            i += 1
            continue

        # 检查是否是谚语/歇后语部分的标题，如果是则切换到proverb模式
        if is_proverb_section_title(s):
            section = "proverb"
            i += 1
            continue

        # 跳过非词条内容
        if should_skip_line(s):
            i += 1
            continue

        # 纯数字行：视为书页码（页码在页面内容的最后）
        if s.isdigit():
            try:
                page_num = int(s)
                current_book_page = page_num
                # 只有当image_page < 248时才根据book_page设置section
                # 如果image_page >= 248，强制使用proverb（已在header处理时设置）
                if current_image_page is not None and current_image_page < 248:
                    if page_num >= 248:
                        section = "proverb"
                    else:
                        section = "lexicon"
                # 如果image_page >= 248，保持proverb不变
                
                # 回溯更新当前 image_page 下已添加条目的 book_page 和 section
                for idx in entries_for_current_image:
                    if entries[idx].book_page is None:
                        entries[idx].book_page = current_book_page
                        # 如果image_page >= 248，强制设置为proverb
                        if current_image_page is not None and current_image_page >= 248:
                            entries[idx].section = "proverb"
                        else:
                            entries[idx].section = section
                
                entries_for_current_image = []  # 清空，后续条目会直接使用当前 book_page
            except ValueError:
                pass
            i += 1
            continue

        # 根据 section 不同采用不同解析策略
        if section == "lexicon":
            # 简单的单行词汇：开平话 + IPA + 普通话解释
            head, rest = split_head_and_rest_lexicon(s)
            ipa, mandarin = split_ipa_and_mandarin(rest)
            
            # 跳过空词条或无效词条
            if not head.strip():
                i += 1
                continue

            new_entry = Entry(
                image_page=current_image_page,
                book_page=current_book_page,
                section=section,
                kp_text=head,
                ipa=ipa,
                mandarin=mandarin,
            )
            entries.append(new_entry)
            entries_for_current_image.append(len(entries) - 1)
            i += 1
            continue

        # section == "proverb"
        # 248页后的格式：通常是"IPA行 + 汉字行"成对出现，中间可能有空行
        has_cjk = any(is_cjk(ch) for ch in s)

        if not has_cjk:
            # 应为 IPA 行（只包含IPA字符、空格、标点等，没有CJK）
            # 检查是否真的是IPA行（包含IPA常见字符，如字母、数字、特殊符号）
            if re.search(r"[a-zA-Z0-9\u0250-\u02AF\u0300-\u036F]", s):
                # 确实是IPA行
                if pending_ipa is None:
                    pending_ipa = s
                else:
                    # 连续两个 IPA 行，合并在一起
                    pending_ipa = pending_ipa + " " + s
            # 如果不是IPA行（可能是空行或其他），跳过
            i += 1
            continue

        # 有 CJK：应为汉字行（谚语/歇后语等）
        chinese_line = s

        # 提取括号内说明作为普通话解释
        mandarin = extract_parenthetical_chinese(chinese_line)
        kp_text = strip_parentheses(chinese_line)
        # 移除proverb结尾的句号
        kp_text = remove_trailing_period(kp_text)
        # 将proverb中的半角逗号规范为全角逗号
        kp_text = normalize_commas(kp_text)

        ipa_for_entry = ""

        if pending_ipa:
            # 形如「IPA 行 → 汉字行」的次序（248页开始的标准格式）
            ipa_for_entry = pending_ipa.strip()
            pending_ipa = None
        else:
            # 如果没有pending_ipa，可能是「汉字行 → IPA行」的次序（249页开始的格式）
            # 向前看（下一行）找IPA
            j = i + 1
            next_ipa: Optional[str] = None
            while j < n:
                s2 = lines[j].strip()
                if not s2:
                    j += 1
                    continue
                if s2.isdigit() or is_separator_line(s2) or is_proverb_section_title(s2):
                    # 遇到新页、分隔符或新标题，视为该条无 IPA
                    break
                if not any(is_cjk(ch) for ch in s2) and re.search(r"[a-zA-Z0-9\u0250-\u02AF\u0300-\u036F]", s2):
                    # 找到 IPA（下一行是IPA）
                    next_ipa = s2
                    break
                else:
                    # 下一行又是中文，说明这里本身就是单独一行句子（无IPA配对）
                    break
            if next_ipa is not None:
                ipa_for_entry = next_ipa.strip()
                # 跳过已消费的 IPA 行（下一行）
                i = j + 1  # 注意：这里要+1，因为后面还有i += 1
                # 直接创建条目，跳过下面的i += 1
                new_entry = Entry(
                    image_page=current_image_page,
                    book_page=current_book_page,
                    section=section,
                    kp_text=kp_text,
                    ipa=ipa_for_entry,
                    mandarin=mandarin,
                )
                entries.append(new_entry)
                entries_for_current_image.append(len(entries) - 1)
                continue  # 跳过下面的i += 1

        # 跳过空词条
        if not kp_text.strip():
            i += 1
            continue
        
        # 创建条目（如果没有在else分支中提前创建）
        new_entry = Entry(
            image_page=current_image_page,
            book_page=current_book_page,
            section=section,
            kp_text=kp_text,
            ipa=ipa_for_entry,
            mandarin=mandarin,
        )
        entries.append(new_entry)
        entries_for_current_image.append(len(entries) - 1)
        i += 1

    return entries


def write_entries_to_csv(entries: List[Entry], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "image_page", "book_page", "section", "kp_text", "ipa", "mandarin"])
        for idx, e in enumerate(entries, start=1):
            writer.writerow(
                [
                    idx,
                    e.image_page if e.image_page is not None else "",
                    e.book_page if e.book_page is not None else "",
                    e.section,
                    e.kp_text,
                    e.ipa,
                    e.mandarin,
                ]
            )


def main() -> None:
    print("=" * 80)
    print("《开平方言》 OCR TXT → CSV 转换")
    print(f"输入 TXT : {INPUT_TXT}")
    print(f"输出 CSV : {OUTPUT_CSV}")
    print("=" * 80)
    print()

    if not os.path.exists(INPUT_TXT):
        print(f"❌ 找不到输入文件: {INPUT_TXT}")
        return

    entries = parse_txt_to_entries(INPUT_TXT)
    print(f"共解析得到 {len(entries)} 条记录，正在写入 CSV ...")
    write_entries_to_csv(entries, OUTPUT_CSV)
    print("✅ 写入完成！")


if __name__ == "__main__":
    main()

