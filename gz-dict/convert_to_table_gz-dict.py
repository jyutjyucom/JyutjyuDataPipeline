#!/usr/bin/env python3
"""
将《广州话词典（第2版）》OCR输出转换为表格形式（CSV）

OCR输出格式特点（参照 OCR_openrouter_gz-dict.py 的格式要求）：
- 每个词条通常为两行：
  1) 第一行：【词头】读音（可含注释/异体/又音等）
  2) 第二行：释义内容（可含例句；例句中“～”代替词头）
- 分页可能打断释义：上一页最后一个词条的释义可能出现在下一页开头
- 词条之间通常有空行，但不依赖空行识别

输出CSV列：
- 序号 (index)
- 类型 (entry_type): 统一为 "词条"
- 词条 (headword)
- 拼音/读音 (pronunciation)
- 释义 (definition)
- 页码 (page)
- 来源文件 (source_file)
"""

import csv
import re
from pathlib import Path

from convert_to_jyutping import convert_gwongping_to_jyutping


_GWONGPING_SYLLABLE_RE = re.compile(r"[a-zɑêéüA-ZɑÊÉÜ]+[0-9](?:-[0-9])?")


def _sanitize_gwongping(text: str) -> str:
    """
    OCR里的注音会使用 ɑ 等字符；先做最小替换以兼容 convert_to_jyutping.py 的规则。
    """
    return (
        text.replace("ɑ", "a")
        .replace("Ａ", "A")
        .replace("ａ", "a")
        .strip()
    )


def fix_ocr_number_format(text: str) -> str:
    """
    修复OCR识别错误：将 $^数字$ 格式恢复为正常数字格式。
    
    例如：
    - "sen$^5$" -> "sen5"
    - "sên$^1$" -> "sên1"
    - "sen$^5$ yen$^4$" -> "sen5 yen4"
    """
    # 将 $^数字$ 或 $数字$ 格式恢复为正常数字
    result = re.sub(r'\$?\^?(\d+)\$?', r'\1', text)
    return result


def normalize_tone_change_spaces(text: str) -> str:
    """
    规范化变调符号前后的空格：将 " - " (带空格) 转换为 "-" (不带空格)。
    
    例如：
    - "wo4 cung4 - 2" -> "wo4 cung4-2"
    - "ɑ3 dɑi6 - 2" -> "ɑ3 dɑi6-2"
    - "ɑ3 féi4 - 2" -> "ɑ3 féi4-2"
    """
    # 将 " - " (带空格) 转换为 "-" (不带空格)
    result = re.sub(r'\s+-\s+', '-', text)
    return result


def _extract_youyin_alt_prons(pronunciation: str) -> list[str]:
    """
    从括号注释里提取“又音…”部分的注音。

    规则：
    - 仅提取包含“又音”的部分
    - 反切/直音法（如“某某切”“读音ping1”）不参与转换
    """
    alts: list[str] = []
    # 统一为全角括号后再抓取括号内容
    s = normalize_text(pronunciation)
    for content in re.findall(r"（([^）]+)）", s):
        if "又音" not in content:
            continue
        # 取“又音”后的内容
        tail = content.split("又音", 1)[1]
        syls = _GWONGPING_SYLLABLE_RE.findall(tail)
        if syls:
            alts.append(" ".join(syls))
    return alts


def pronunciation_to_jyutping(pronunciation: str) -> str:
    """
    将广州话词典原书注音转换为粤拼（jyutping）。

    处理逻辑：
    - 主读音：取第一个括号（若有）之前的部分进行转换
    - 括号内：
      - 反切法/直音法（常见“切”“读音…”）直接忽略
      - 若含“又音…”，把“又音”后的注音转换后用英文括号追加到 jyutping 末尾
    """
    s = normalize_text(pronunciation).strip()
    main = s.split("（", 1)[0].strip()
    main_j = convert_gwongping_to_jyutping(_sanitize_gwongping(main))

    alts = _extract_youyin_alt_prons(s)
    alt_j_list: list[str] = []
    for alt in alts:
        alt_j = convert_gwongping_to_jyutping(_sanitize_gwongping(alt))
        if alt_j and alt_j != main_j:
            alt_j_list.append(alt_j)

    if alt_j_list:
        return f"{main_j} ({'; '.join(alt_j_list)})".strip()
    return main_j.strip()


def extract_page_info(line: str) -> tuple[str, int] | None:
    """
    从页面标题行提取文件名和页码

    格式示例：
    --- 广州话词典（第2版）(Clear).饶秉才.欧阳觉亚.周无忌.2020_页面_121.png (第121页) ---
    """
    line = line.strip()
    # 注意：normalize_text 会把半角括号 () 转为全角 （）
    # 所以这里同时兼容两种括号
    m = re.match(
        r'---\s*(.+?页面_(\d+)\.png)(?:\s*[\(（]第(\d+)页[\)）])?\s*---',
        line,
    )
    if not m:
        return None
    filename = m.group(1)
    page_num = int(m.group(3) or m.group(2))
    return filename, page_num


def normalize_text(text: str) -> str:
    """
    轻量标准化：仅统一一些常见半角符号到全角，避免OCR混用。
    不做"纠错式"改写，尽量保留原文。
    """
    text = text.replace("(", "（").replace(")", "）")
    text = text.replace("[", "［").replace("]", "］")
    text = text.replace("<", "〈").replace(">", "〉")
    return text


def clean_pronunciation_comment_spaces(pronunciation: str) -> str:
    """
    清理读音字段中括号注释前后的多余空格，以及注释内部的多余空格。
    
    例如：
    - "xxx （ 注释 ）" -> "xxx（注释）"
    - "xxx （  注释  ）" -> "xxx（注释）"
    - "xxx （ 注释1， 注释2 ）" -> "xxx（注释1，注释2）"
    """
    # 清理括号前后的空格
    result = re.sub(r'\s+（', '（', pronunciation)  # 清理左括号前的空格
    result = re.sub(r'）\s+', '）', result)  # 清理右括号后的空格
    
    # 清理括号内的首尾空格
    result = re.sub(r'（\s+', '（', result)  # 左括号后紧接的空格
    result = re.sub(r'\s+）', '）', result)  # 右括号前紧接的空格
    
    # 清理括号内多个连续空格，压缩为一个空格
    # 同时清理标点符号前后的多余空格
    def clean_inside_brackets(match):
        content = match.group(1)
        # 压缩多个连续空格为一个空格
        content = re.sub(r'\s+', ' ', content)
        # 清理标点符号前后的空格（逗号、分号等）
        content = re.sub(r'\s*，\s*', '，', content)  # 逗号前后
        content = re.sub(r'\s*；\s*', '；', content)  # 分号前后
        content = re.sub(r'\s*。\s*', '。', content)  # 句号前后
        # 清理首尾空格
        content = content.strip()
        return f'（{content}）'
    
    # 匹配括号及其内容，清理内部空格
    result = re.sub(r'（([^）]+)）', clean_inside_brackets, result)
    
    return result


def clean_headword_spaces(headword: str) -> str:
    """
    清理词条字段中括号前后的多余空格，以及括号内部的多余空格。
    
    例如：
    - "謵（ 拗） 到掂" -> "謵（拗）到掂"
    - "呃呃 （ 眲眲 ） 骗骗" -> "呃呃（眲眲）骗骗"
    - "罨（ 罯、浥）" -> "罨（罯、浥）"
    """
    # 清理括号前后的空格
    result = re.sub(r'\s+（', '（', headword)  # 清理左括号前的空格
    result = re.sub(r'）\s+', '）', result)  # 清理右括号后的空格
    
    # 清理括号内的首尾空格
    result = re.sub(r'（\s+', '（', result)  # 左括号后紧接的空格
    result = re.sub(r'\s+）', '）', result)  # 右括号前紧接的空格
    
    # 清理括号内多个连续空格，压缩为一个空格
    # 同时清理标点符号前后的多余空格
    def clean_inside_brackets(match):
        content = match.group(1)
        # 压缩多个连续空格为一个空格
        content = re.sub(r'\s+', ' ', content)
        # 清理标点符号前后的空格（逗号、分号、顿号等）
        content = re.sub(r'\s*，\s*', '，', content)  # 逗号前后
        content = re.sub(r'\s*、\s*', '、', content)  # 顿号前后
        content = re.sub(r'\s*；\s*', '；', content)  # 分号前后
        # 清理首尾空格
        content = content.strip()
        return f'（{content}）'
    
    # 匹配括号及其内容，清理内部空格
    result = re.sub(r'（([^）]+)）', clean_inside_brackets, result)
    
    return result


def is_separator_line(line: str) -> bool:
    line = line.strip()
    return bool(re.match(r'^[=]{8,}$', line))


def is_token_count_line(line: str) -> bool:
    line = line.strip()
    return line.startswith("<Token Count:") or line.startswith("〈Token Count:")


def is_skip_line(line: str) -> bool:
    line = line.strip()
    if not line:
        return True
    if is_separator_line(line):
        return True
    if is_token_count_line(line):
        return True
    # 页面标题行会在 preprocess_lines 里处理并移除；这里兜底
    if line.startswith("---") and line.endswith("---"):
        return True
    return False


def is_entry_start(line: str) -> bool:
    """词条头行：以【...】开头。"""
    return bool(re.match(r"^【[^】]+】", line.strip()))


def parse_entry_header(line: str) -> tuple[str, str] | None:
    """
    解析词条头行：
    【词头】读音（注释）
    返回 (headword, pronunciation)
    """
    m = re.match(r"^【\s*(.+?)\s*】\s*(.*)$", line.strip())
    if not m:
        return None
    headword = re.sub(r"\s+", " ", m.group(1)).strip()
    pronunciation = re.sub(r"\s+", " ", m.group(2)).strip()
    return headword, pronunciation


def preprocess_lines(lines: list[str]) -> list[tuple[str, int, str]]:
    """
    预处理：给每行打上 (page_num, source_file)，并移除页面标题行本身。

    返回: [(line_content, page_num, source_file), ...]
    """
    result: list[tuple[str, int, str]] = []
    current_page = 0
    current_source = ""

    for raw in lines:
        line = raw.rstrip("\n")
        page_info = extract_page_info(line)
        if page_info:
            current_source, current_page = page_info
            continue
        result.append((line, current_page, current_source))

    return result


def parse_ocr_file(input_path: str) -> list[dict]:
    with open(input_path, "r", encoding="utf-8") as f:
        lines = [normalize_text(x) for x in f.readlines()]

    processed = preprocess_lines(lines)
    entries: list[dict] = []

    i = 0
    while i < len(processed):
        line, page, source = processed[i]
        if is_skip_line(line):
            i += 1
            continue

        # 不是【...】开头：多半是上一条释义被分页/识别打散；这里跳过
        if not is_entry_start(line):
            i += 1
            continue

        header = parse_entry_header(line)
        if not header:
            i += 1
            continue

        headword, pronunciation = header
        
        # 清理词条字段中括号前后的多余空格
        headword = clean_headword_spaces(headword)
        
        entry_page = page
        entry_source = source

        def_lines: list[str] = []

        # 修复少数OCR换行：头行的括号注释被拆到下一行（如 "( 合" 换行到 "尺，何奢） ..."）
        j = i + 1
        if "（" in pronunciation and "）" not in pronunciation:
            k = j
            while k < len(processed):
                next_line, _, _ = processed[k]
                if is_skip_line(next_line):
                    k += 1
                    continue
                if is_entry_start(next_line):
                    break
                if "）" in next_line:
                    before, after = next_line.split("）", 1)
                    pronunciation = f"{pronunciation} {before}）"
                    after = after.strip()
                    if after:
                        def_lines.append(after)
                    k += 1
                    j = k
                    break
                # 如果这一行仍然没有闭合括号，整行都并入注释并继续找下一行
                pronunciation = f"{pronunciation} {next_line.strip()}"
                k += 1
                j = k

        # 修复OCR识别错误：将 $^数字$ 格式恢复为正常数字格式
        pronunciation = fix_ocr_number_format(pronunciation)
        
        # 规范化变调符号前后的空格：将 " - " 转换为 "-"
        pronunciation = normalize_tone_change_spaces(pronunciation)
        
        # 清理读音字段中括号注释前后的多余空格
        pronunciation = clean_pronunciation_comment_spaces(pronunciation)
        
        jyutping = pronunciation_to_jyutping(pronunciation)
        while j < len(processed):
            next_line, _, _ = processed[j]
            if is_skip_line(next_line):
                j += 1
                continue
            if is_entry_start(next_line):
                break
            def_lines.append(next_line.strip())
            j += 1

        definition = re.sub(r"\s+", " ", " ".join(def_lines)).strip()

        entries.append(
            {
                "entry_type": "词条",
                "headword": headword,
                "pronunciation": pronunciation,
                "jyutping": jyutping,
                "definition": definition,
                "page": entry_page,
                "source_file": entry_source,
            }
        )
        i = j

    return entries


def save_to_csv(entries: list[dict], output_path: str):
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "index",
                "entry_type",
                "headword",
                "pronunciation",
                "jyutping",
                "definition",
                "page",
                "source_file",
            ],
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        for idx, e in enumerate(entries, 1):
            row = dict(e)
            row["index"] = idx
            writer.writerow(row)


def main():
    root = Path(__file__).parent
    input_path = root / "output" / "广州话词典_重新OCR_输出.txt"
    output_path = root / "output" / "广州话词典_重新OCR_输出_table.csv"

    print(f"读取OCR输出文件: {input_path}")
    entries = parse_ocr_file(str(input_path))
    print(f"解析得到 {len(entries)} 个词条")

    print("\n前20个词条示例：")
    print("-" * 80)
    for e in entries[:20]:
        print(f"【{e['headword']}】 {e['pronunciation']}")
        preview = e["definition"][:100] + ("..." if len(e["definition"]) > 100 else "")
        print(f"  释义: {preview}")
        print(f"  页码: {e['page']}")
        print()

    save_to_csv(entries, str(output_path))
    print(f"\n已保存到: {output_path}")

    pages = sorted({e["page"] for e in entries if e["page"]})
    if pages:
        print(f"涵盖页数: {len(pages)} ({pages[0]} - {pages[-1]})")
    with_pron = sum(1 for e in entries if e["pronunciation"])
    print(f"有读音的词条: {with_pron} ({with_pron/len(entries)*100:.1f}%)" if entries else "有读音的词条: 0")


if __name__ == "__main__":
    main()

