#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将《现代粤语词典》拼音方案转换为粤拼（Jyutping）的脚本
参考：《现代粤语词典（广州音 第一版）》范俊军.范兰德.2021
"""

import csv
import re

# 声调映射表（从现代粤语词典到粤拼）
# 现代粤语词典的声调顺序：阴平、阳平、阴上、阳上、阴去、阳去、上阴入、下阴入、阳入
# 粤拼的声调顺序：阴平、阴上、阴去、阳平、阳上、阳去、上阴入、下阴入、阳入
TONE_MAP = {
    '1': '1',  # 阴平 (55) → 阴平 (55)
    '2': '4',  # 阳平 (21) → 阳平 (21)
    '3': '2',  # 阴上 (35) → 阴上 (35)
    '4': '5',  # 阳上 (13) → 阳上 (13)
    '5': '3',  # 阴去 (33) → 阴去 (33)
    '6': '6',  # 阳去 (22) → 阳去 (22)
    '7': '1',  # 上阴入 (55) → 上阴入 (55)
    '8': '3',  # 下阴入 (33) → 下阴入 (33)
    '9': '6',  # 阳入 (22) → 阳入 (22)
}

# 声母映射表（从现代粤语词典拼音方案到粤拼）
# 参考：《现代粤语词典（广州音 第一版）》范俊军.范兰德.2021
INITIAL_MAP = {
    'b': 'b',
    'p': 'p',
    'm': 'm',
    'f': 'f',
    'd': 'd',
    't': 't',
    'n': 'n',
    'l': 'l',
    'g': 'g',
    'k': 'k',
    'ng': 'ng',
    'h': 'h',
    'z': 'z',
    'c': 'c',
    's': 's',
    'gw': 'gw',
    'kw': 'kw',
    'w': 'w',
    'y': 'j',  # 现代粤语词典用 y，粤拼用 j
}

# 韵母映射表（从现代粤语词典拼音方案到粤拼）
# 参考：《现代粤语词典（广州音 第一版）》范俊军.范兰德.2021
# 主要变化：韵尾 b→p, d→t, g→k（入声韵尾）
FINAL_MAP = {
    # aa 系韵母
    'aa': 'aa',
    'aai': 'aai',
    'aau': 'aau',
    'aam': 'aam',
    'aan': 'aan',
    'aang': 'aang',
    'aab': 'aap',
    'aad': 'aat',
    'aag': 'aak',
    
    # a 系韵母（短 a）
    'ai': 'ai',
    'au': 'au',
    'am': 'am',
    'an': 'an',
    'ang': 'ang',
    'ab': 'ap',
    'ad': 'at',
    'ag': 'ak',
    
    # o 系韵母
    'o': 'o',
    'oi': 'oi',
    'ou': 'ou',
    'on': 'on',
    'ong': 'ong',
    'od': 'ot',
    'og': 'ok',
    
    # e 系韵母
    'e': 'e',
    'ei': 'ei',
    'eu': 'eu',
    'em': 'em',
    'eng': 'eng',
    'eb': 'ep',
    'eg': 'ek',
    
    # oe 系韵母
    'oe': 'oe',
    'oey': 'eoi',   # oey → eoi
    'ioey': 'eoi',  # ioey → eoi
    'oen': 'eon',
    'oeng': 'oeng',
    'oed': 'eot',
    'oeg': 'oek',
    
    # i 系韵母
    'i': 'i',
    'iu': 'iu',
    'im': 'im',
    'in': 'in',
    'ing': 'ing',
    'ib': 'ip',
    'id': 'it',
    'ig': 'ik',
    
    # u 系韵母
    'u': 'u',
    'ui': 'ui',
    'un': 'un',
    'ung': 'ung',
    'ud': 'ut',
    'ug': 'uk',
    
    # yu 系韵母
    'yu': 'yu',
    'yun': 'yun',
    'yud': 'yut',
    
    # 独立鼻音韵母
    'm': 'm',
    'ng': 'ng',
}

def split_syllables(gwongping_text):
    """
    按声调数字分隔音节
    """
    # 移除零宽字符
    gwongping_text = gwongping_text.replace('\u200d', '').replace('\u200c', '')
    
    # 使用正则表达式按数字声调分隔
    # 匹配：字母（包括带音调符号的字母）+ 数字声调（可能带变调，如4-2）
    syllables = re.findall(r'[a-zêéüA-ZÊÉÜ]+[0-9](?:-[0-9])?', gwongping_text)
    
    return syllables

def convert_syllable(syllable):
    """
    转换单个音节从广州话拼音到粤拼
    """
    # 提取声调（包括变调，如4-2）
    match = re.match(r'([a-zêéüA-ZÊÉÜ]+)([0-9](?:-[0-9])?)', syllable)
    if not match:
        return syllable
    
    phonetic = match.group(1).lower()
    tone = match.group(2)
    
    # 尝试所有可能的声母+韵母拆分，并选择最合理的一个
    # 策略：当有多个有效拆分时，优先选择韵母更长的拆分
    valid_splits = []
    
    # 按长度排序声母（长的优先匹配）
    sorted_initials = sorted(INITIAL_MAP.keys(), key=len, reverse=True)
    
    for init in sorted_initials:
        if phonetic.startswith(init):
            potential_final = phonetic[len(init):]
            # 验证剩余部分是否是有效的韵母
            if potential_final in FINAL_MAP:
                # 记录这个有效拆分：(声母, 韵母, 韵母长度)
                valid_splits.append((init, potential_final, len(potential_final)))
    
    # 如果没有找到有效的声母+韵母组合，尝试只匹配韵母（无声母的情况）
    if not valid_splits and phonetic in FINAL_MAP:
        valid_splits.append(('', phonetic, len(phonetic)))
    
    # 如果找到多个有效拆分，选择韵母最长的那个
    if valid_splits:
        # 按韵母长度降序排序，选择韵母最长的
        valid_splits.sort(key=lambda x: x[2], reverse=True)
        initial = valid_splits[0][0]
        final = valid_splits[0][1]
    else:
        # 如果没有找到任何有效拆分，保持原样
        initial = ''
        final = phonetic
    
    # 转换声母
    jyutping_initial = INITIAL_MAP.get(initial, initial)
    
    # 转换韵母
    jyutping_final = FINAL_MAP.get(final, final)
    
    # 特殊规则：处理没有声母的情况
    if not initial:
        # 说明(2)：i、iu、im、in、ing、ib、id、ig 前面没有声母时，应添加 y（→ j）
        if final in ['i', 'iu', 'im', 'in', 'ing', 'ib', 'id', 'ig']:
            jyutping_initial = 'j'
        # 说明(3)：u、ui、un、ud 前面没有声母时，应添加 w
        elif final in ['u', 'ui', 'un', 'ud']:
            jyutping_initial = 'w'
        # 说明(4)：yu、yun、yud 与声母 y 相拼时声母省略，转换时需添加 j
        elif final in ['yu', 'yun', 'yud']:
            jyutping_initial = 'j'
    
    # 转换声调
    # 处理变调情况（如 4-2）
    if '-' in tone:
        # 变调格式：分别转换每个声调
        tone_parts = tone.split('-')
        jyutping_tones = [TONE_MAP.get(t, t) for t in tone_parts]
        jyutping_tone = '-'.join(jyutping_tones)
    else:
        # 单一声调
        jyutping_tone = TONE_MAP.get(tone, tone)
    
    # 组合结果
    result = jyutping_initial + jyutping_final + jyutping_tone
    
    return result

def convert_gwongping_to_jyutping(gwongping_text):
    """
    转换现代粤语词典拼音文本到粤拼（Jyutping）
    支持多音节，用 / 分隔的读音等格式
    """
    if not gwongping_text or gwongping_text.strip() == '':
        return gwongping_text
    
    # 处理 / 分隔的多个读音（如：aa1 / aa5）
    if '/' in gwongping_text:
        # 分别转换每个读音，保持 / 分隔符
        parts = gwongping_text.split('/')
        converted_parts = []
        for part in parts:
            part = part.strip()
            if part:
                syllables = split_syllables(part)
                jyutping_syllables = [convert_syllable(syl) for syl in syllables]
                converted_parts.append(' '.join(jyutping_syllables))
        return ' / '.join(converted_parts)
    
    # 处理普通的音节序列
    syllables = split_syllables(gwongping_text)
    
    # 转换每个音节
    jyutping_syllables = [convert_syllable(syl) for syl in syllables]
    
    # 用空格连接
    return ' '.join(jyutping_syllables)

def convert_csv(input_file, output_file):
    """
    转换CSV文件中的pronunciation列（现代粤语词典拼音方案）到jyutping（粤拼）
    """
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        # 添加新的列名用于粤拼
        if 'jyutping' not in fieldnames:
            fieldnames = list(fieldnames)
            # 在pronunciation后面插入jyutping列
            pronunciation_index = fieldnames.index('pronunciation')
            fieldnames.insert(pronunciation_index + 1, 'jyutping')
        
        rows = []
        for row in reader:
            pronunciation_original = row.get('pronunciation', '')
            
            # 转换为粤拼
            jyutping = convert_gwongping_to_jyutping(pronunciation_original)
            
            # 添加jyutping列（保持原pronunciation列不变）
            row['jyutping'] = jyutping
            rows.append(row)
            
            # 打印前几个示例
            if len(rows) <= 5:
                print(f"词头: {row.get('headword', '')}")
                print(f"原拼音: {pronunciation_original}")
                print(f"粤拼: {jyutping}")
                print()
    
    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"转换完成！共处理 {len(rows)} 条记录。")
    print(f"结果已保存到: {output_file}")

if __name__ == '__main__':
    input_file = '现代粤语词典_table.csv'
    output_file = '现代粤语词典_table_粤拼.csv'
    
    convert_csv(input_file, output_file)

