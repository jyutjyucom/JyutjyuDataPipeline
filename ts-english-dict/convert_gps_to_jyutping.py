#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 HED phrases CSV 中的 GPS（粤语拼音方案）转换为粤拼（Jyutping）。
在 GPS 列后新增一列 Jyutping。
"""

import csv
import re
import os

# 声调：GPS 调符 → Jyutping 调号
# ä 1, ã 4, ā 2, â 5, à 6
TONE_DIACRITIC_MAP = {
    'ä': '1', 'ã': '4', 'ā': '2', 'â': '5', 'à': '6',
    'ë': '1', 'ẽ': '4', 'ē': '2', 'ê': '5', 'è': '6',
    'ï': '1', 'ĩ': '4', 'ī': '2', 'î': '5', 'ì': '6',
    'ö': '1', 'õ': '4', 'ō': '2', 'ô': '5', 'ò': '6',
    'ü': '1', 'ũ': '4', 'ū': '2', 'û': '5', 'ù': '6',
}

# 变调：音节后带 "/" 时，原调 → Jyutping 变调标注（参考官方文档 335→1*, 225→4*, 325→6*, 215→5*）
# Tone 2 (33) middle rising 335 → 1*；Tone 3 (22) low rising 225 → 4*；
# Tone 4 (32) middle dip rising 325 → 6*；Tone 5 (21) low dip rising 215 → 5*
TONAL_CHANGE_MAP = {
    '2': '1*',   # 335
    '4': '4*',   # 225
    '5': '5*',   # 215
    '6': '6*',   # 325
}
# 调号 1 无变调，保持 1

# 声母：GPS → Jyutping（长声母优先匹配）
INITIAL_GPS_TO_JYP = {
    'ch': 'c',
    'x': 'sl',
    'y': 'j',
    'j': 'z',
}
INITIAL_KEYS_SORTED = sorted(INITIAL_GPS_TO_JYP.keys(), key=len, reverse=True)

# 韵母：GPS → Jyutping（从用户提供的表格整理）
FINAL_GPS_TO_JYP = {
    # aa 系
    'a': 'aa', 'ai': 'aai', 'ao': 'aau', 'am': 'aam', 'an': 'aan',
    'ang': 'aang', 'ak': 'aak', 'ap': 'aap', 'at': 'aat',
    # ie/eh 系
    'eh': 'ie', 'el': 'eu', 'eim': 'em', 'ein': 'en', 'eik': 'ek', 'eip': 'ep',
    # ea/e 系
    'e': 'ea', 'eo': 'ieu', 'em': 'iem', 'en': 'ien', 'eng': 'ieng',
    'ek': 'iek', 'ep': 'iep', 'et': 'iet',
    # i 系（相同）
    'i': 'i', 'iu': 'iu', 'im': 'im', 'in': 'in', 'ip': 'ip', 'it': 'it',
    # uo/o 系
    'o': 'uo', 'oi': 'uoi', 'on': 'uon', 'ong': 'ong', 'ok': 'ok', 'ot': 'uot',
    # u 系
    'u': 'u', 'ui': 'ui', 'un': 'un', 'ung': 'eang', 'uk': 'eak', 'ut': 'ut',
}
# 匹配顺序：长韵母优先
FINAL_KEYS_SORTED = sorted(FINAL_GPS_TO_JYP.keys(), key=len, reverse=True)


def get_tone_from_syllable(syllable: str) -> tuple[str, str]:
    """
    从音节中提取带调符的元音，返回 (去掉调符的字母, Jyutping 调号)。
    若没有调符，返回 ('', '')。
    """
    for char, tone in TONE_DIACRITIC_MAP.items():
        if char in syllable:
            base = {
                'ä': 'a', 'ã': 'a', 'ā': 'a', 'â': 'a', 'à': 'a',
                'ë': 'e', 'ẽ': 'e', 'ē': 'e', 'ê': 'e', 'è': 'e',
                'ï': 'i', 'ĩ': 'i', 'ī': 'i', 'î': 'i', 'ì': 'i',
                'ö': 'o', 'õ': 'o', 'ō': 'o', 'ô': 'o', 'ò': 'o',
                'ü': 'u', 'ũ': 'u', 'ū': 'u', 'û': 'u', 'ù': 'u',
            }.get(char, char)
            return base, tone
    return '', ''


def strip_tone_diacritics(s: str) -> str:
    """将带调符的字母替换为不带调符的字母。"""
    result = []
    for c in s:
        base = {
            'ä': 'a', 'ã': 'a', 'ā': 'a', 'â': 'a', 'à': 'a',
            'ë': 'e', 'ẽ': 'e', 'ē': 'e', 'ê': 'e', 'è': 'e',
            'ï': 'i', 'ĩ': 'i', 'ī': 'i', 'î': 'i', 'ì': 'i',
            'ö': 'o', 'õ': 'o', 'ō': 'o', 'ô': 'o', 'ò': 'o',
            'ü': 'u', 'ũ': 'u', 'ū': 'u', 'û': 'u', 'ù': 'u',
        }.get(c, c)
        result.append(base)
    return ''.join(result)


def split_into_initial_final(syllable: str) -> tuple[str, str, str]:
    """
    将音节拆成：声母、韵母(GPS)、调号。
    韵母为 GPS 拼写（已去调符的韵母部分），调号为 Jyutping 数字。
    """
    s = syllable.strip().lower()
    if not s:
        return '', '', ''

    tone_num = ''
    base = strip_tone_diacritics(s)
    for char, tone in TONE_DIACRITIC_MAP.items():
        if char in s:
            tone_num = tone
            break

    # 在 base 上找韵母：从前往后尝试最长的 GPS 韵母
    for gps_final in FINAL_KEYS_SORTED:
        if base.endswith(gps_final):
            # 声母 = base 去掉韵母
            init = base[: -len(gps_final)] if len(gps_final) < len(base) else ''
            return init, gps_final, tone_num

    # 没有匹配到韵母时，整段当作韵母（或保留原样）
    return '', base, tone_num


def convert_final_gps_to_jyutping(gps_final: str) -> str:
    """韵母 GPS → Jyutping。"""
    return FINAL_GPS_TO_JYP.get(gps_final, gps_final)


def convert_initial_gps_to_jyutping(initial: str) -> str:
    """声母 GPS → Jyutping（x→sl, y→j, j→z, ch→c）。"""
    for gps_init in INITIAL_KEYS_SORTED:
        if initial.startswith(gps_init):
            return INITIAL_GPS_TO_JYP[gps_init] + initial[len(gps_init):]
    return initial


def convert_syllable(syllable: str) -> str:
    """
    将单个 GPS 音节转为 Jyutping。
    例如：ā → aa2, ngũn → ngun4, lũng → leang4
    支持括号内读音如 sì(hài) → si2(hai2)
    支持变调：音节后 "/" 时按 TONAL_CHANGE_MAP 标为 1*/4*/5*/6*（如 ài-lëo/ → aai6 lie2 → aai6 lie1*）
    """
    s = syllable.strip()
    if not s:
        return ''

    # 变调标记：音节末尾的 "/"
    has_tonal_change = s.endswith('/')
    if has_tonal_change:
        s = s[:-1].strip()

    # 括号内读音：如 sì(hài) 分别转换（变调 "/" 已在上方剥掉，不进入括号内）
    m = re.match(r'^([^(]*)\(([^)]*)\)(.*)$', s)
    if m:
        before, inside, after = m.group(1), m.group(2), m.group(3)
        return (
            convert_syllable(before) +
            '(' + convert_syllable(inside) + ')' +
            (convert_syllable(after) if after else '')
        )

    initial, final, tone = split_into_initial_final(s)
    if has_tonal_change and tone:
        tone = TONAL_CHANGE_MAP.get(tone, tone)
    jyp_initial = convert_initial_gps_to_jyutping(initial)
    jyp_final = convert_final_gps_to_jyutping(final)
    jyp = jyp_initial + jyp_final + tone
    return jyp


def convert_gps_text(gps_text: str) -> str:
    """
    将整段 GPS 文本转为 Jyutping。
    支持：空格、连字符分隔音节；括号内保留不拆；保留 " or " 等结构。
    """
    if not gps_text or not gps_text.strip():
        return gps_text

    # 处理 " or " 分隔的多种读法
    if ' or ' in gps_text:
        parts = gps_text.split(' or ')
        return ' or '.join(convert_gps_text(p.strip()) for p in parts if p.strip())

    # 按连字符或空格分音节，但保留括号块不拆
    # 先保护括号内容：将 (xxx) 替换为占位，再按 - 和空格分，最后还原
    parens = []
    def save_paren(m):
        parens.append(m.group(0))
        return f'\x00PAREN{len(parens)-1}\x00'
    text = re.sub(r'\([^)]*\)', save_paren, gps_text)

    syllables = re.split(r'[\s\-]+', text)
    result_parts = []
    for syl in syllables:
        syl = syl.strip()
        if not syl:
            continue
        # 还原占位
        for i, p in enumerate(parens):
            syl = syl.replace(f'\x00PAREN{i}\x00', p)
        result_parts.append(convert_syllable(syl))
    return ' '.join(result_parts)


def convert_csv(
    input_path: str,
    output_path: str | None = None,
    gps_column: str = 'GPS',
):
    """
    读取 HED phrases CSV，在 GPS 列后增加一列 Jyutping，写入新文件。
    """
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f'{base}_jyutping{ext}'

    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        raw_names = list(reader.fieldnames or [])
        # 去掉 BOM，过滤 None；保留 原始名→清洁名 的对应以便从 row 取值
        fieldnames = []
        raw_to_clean = {}
        for n in raw_names:
            if n is None:
                continue
            clean_name = n.strip('\ufeff')
            fieldnames.append(clean_name)
            raw_to_clean[clean_name] = n

        if gps_column not in fieldnames:
            raise ValueError(f'CSV 中未找到列: {gps_column}')

        # 在 GPS 后插入 Jyutping（若尚未存在）
        if 'Jyutping' not in fieldnames:
            idx = fieldnames.index(gps_column)
            fieldnames.insert(idx + 1, 'Jyutping')

        rows = []
        for row in reader:
            # 用原始列名从 row 取值，写入清洁列名，避免 BOM/None 导致错位
            clean = {}
            for cname in fieldnames:
                rname = raw_to_clean.get(cname, cname)
                clean[cname] = row.get(rname, row.get(cname, ''))
            gps = clean.get(gps_column, '')
            jyutping = convert_gps_text(gps) if gps else ''
            clean['Jyutping'] = jyutping
            rows.append(clean)

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f'已处理 {len(rows)} 行，输出: {output_path}')
    return output_path


if __name__ == '__main__':
    import sys
    input_file = 'HED Alphabetically (A-Y) October 2024_phrases.csv'
    if not os.path.isfile(input_file):
        input_file = os.path.join(os.path.dirname(__file__), input_file)
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    convert_csv(input_file, output_file, gps_column='GPS')
