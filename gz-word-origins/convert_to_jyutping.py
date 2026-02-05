#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将广州话拼音转换为粤拼的脚本
"""

import csv
import re

# 声母映射表（从广州话拼音到粤拼）
INITIAL_MAP = {
    'b': 'b',
    'c': 'c',
    'd': 'd',
    'f': 'f',
    'g': 'g',
    'gu': 'gw',
    'h': 'h',
    'y': 'j',
    'k': 'k',
    'ku': 'kw',
    'l': 'l',
    'm': 'm',
    'n': 'n',
    'ng': 'ng',
    'p': 'p',
    's': 's',
    'j': 'z',
    'q': 'c',
    'x': 's',
    't': 't',
    'w': 'w',
    'z': 'z',
}

# 韵母映射表（从广州话拼音到粤拼）
FINAL_MAP = {
    'a': 'aa',
    'ai': 'aai',
    'ao': 'aau',
    'am': 'aam',
    'an': 'aan',
    'ang': 'aang',
    'ab': 'aap',
    'ad': 'aat',
    'ag': 'aak',
    'ei': 'ai',
    'eo': 'au',
    'em': 'am',
    'en': 'an',
    'eng': 'ang',
    'eb': 'ap',
    'ed': 'at',
    'eg': 'ak',
    'é': 'e',
    'éi': 'ei',
    'éng': 'eng',
    'ég': 'ek',
    'i': 'i',
    'iu': 'iu',
    'im': 'im',
    'in': 'in',
    'ing': 'ing',
    'ib': 'ip',
    'id': 'it',
    'ig': 'ik',
    'o': 'o',
    'oi': 'oi',
    'ou': 'ou',
    'on': 'on',
    'ong': 'ong',
    'od': 'ot',
    'og': 'ok',
    'ê': 'oe',
    'êng': 'oeng',
    'êg': 'oek',
    'êu': 'eoi',
    'ên': 'eon',
    'êd': 'eot',
    'u': 'u',
    'ui': 'ui',
    'un': 'un',
    'ung': 'ung',
    'ud': 'ut',
    'ug': 'uk',
    'ü': 'yu',
    'ün': 'yun',
    'üd': 'yut',
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
    
    # 特殊规则：当声母是 j/q/x（对应粤拼 z/c/s）且韵母以 u 开头时，
    # 需要将韵母转换为对应的 yu 韵母
    if initial in ['j', 'q', 'x'] and final.startswith('u'):
        # 将 u- 韵母转换为 ü- 韵母（对应粤拼的 yu-）
        final_with_yu = 'ü' + final[1:]
        if final_with_yu in FINAL_MAP:
            jyutping_final = FINAL_MAP[final_with_yu]
    
    # 组合结果
    result = jyutping_initial + jyutping_final + tone
    
    return result

def convert_gwongping_to_jyutping(gwongping_text):
    """
    转换整个广州话拼音文本到粤拼
    """
    if not gwongping_text or gwongping_text.strip() == '':
        return gwongping_text
    
    # 分隔音节
    syllables = split_syllables(gwongping_text)
    
    # 转换每个音节
    jyutping_syllables = [convert_syllable(syl) for syl in syllables]
    
    # 用空格连接
    return ' '.join(jyutping_syllables)

def convert_csv(input_file, output_file):
    """
    转换CSV文件中的gwongping列
    """
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        # 添加新的列名用于粤拼
        if 'jyutping' not in fieldnames:
            fieldnames = list(fieldnames)
            # 在gwongping后面插入jyutping列
            gwongping_index = fieldnames.index('gwongping')
            fieldnames.insert(gwongping_index + 1, 'jyutping')
        
        rows = []
        for row in reader:
            gwongping_original = row.get('gwongping', '')
            
            # 分隔音节并用空格连接（用于gwongping列）
            syllables = split_syllables(gwongping_original)
            gwongping_spaced = ' '.join(syllables)
            
            # 转换为粤拼（用于jyutping列）
            jyutping_syllables = [convert_syllable(syl) for syl in syllables]
            jyutping = ' '.join(jyutping_syllables)
            
            # 更新两个列
            row['gwongping'] = gwongping_spaced  # 覆盖原来的gwongping列
            row['jyutping'] = jyutping
            rows.append(row)
            
            # 打印前几个示例
            if len(rows) <= 5:
                print(f"原文: {gwongping_original}")
                print(f"分隔: {gwongping_spaced}")
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
    input_file = '《粵語辭源》在線協作.csv'
    output_file = '《粵語辭源》在線協作_粤拼.csv'
    
    convert_csv(input_file, output_file)

