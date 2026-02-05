#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将开平方言IPA方案转换为粤拼（Jyutping）的脚本
"""

import csv
import re

# 声调映射表（从开平方言IPA五度标记法到粤拼）
# 五度标记法 → 粤拼调号
TONE_MAP = {
    '33': '1',  # 33 → 1
    '55': '2',  # 55 → 2
    '11': '4',  # 11 → 4
    '21': '5',  # 21 → 5
    '32': '6',  # 32 → 6
    '35': '1*', # 35 → 1* 阴平阴去变调
    '15': '4*', # 15 → 4* 阳平变调
    '215': '5*', # 215 → 5* 阳上变调
    '325': '6*', # 325 → 6* 阳去变调
}

# 声母映射表（从开平方言IPA到粤拼）
# IPA符号需要根据实际使用的符号调整
INITIAL_MAP = {
    # 双唇音
    'p': 'b',      # [p]
    'p‘': 'p',     # [pʰ] 送气
    'm': 'm',      # [m]
    
    # 唇齿音
    'f': 'f',      # [f]
    'v': 'v',      # [v]
    
    # 齿龈音
    't': 'd',      # [t]
    't‘': 't',     # [tʰ] 送气
    'n': 'n',      # [n]
    'l': 'l',      # [l]
    'ɬ': 'sl',     # [ɬ]
    
    # 齿龈擦音
    'ts': 'z',     # [ts]
    'ts‘': 'c',    # [tsʰ] 送气
    's': 's',      # [s]
    
    # 软腭音
    'k': 'g',      # [k]
    'k‘': 'k',     # [kʰ] 送气
    'g': 'g',      # [g]
    'ŋ': 'ng',     # [ŋ]
    'η': 'ng',     # [η] (eta, alternative to ŋ)
    'h': 'h',      # [h]
    
    # 近音
    'j': 'j',      # [j]
    
    # 零声母（空字符串）
    '': '',
}

# 韵母映射表（从开平方言IPA到粤拼）
# IPA韵母符号需要根据实际使用的符号调整
FINAL_MAP = {
    # aa 系韵母
    'a': 'aa',           # [a]
    'ai': 'aai',         # [ai]
    'au': 'aau',         # [au]
    'am': 'aam',         # [am]
    'an': 'aan',         # [an]
    'aŋ': 'aang',        # [aŋ]
    'aη': 'aang',        # [aη] (eta variant)
    'ap': 'aap',         # [ap]
    'at': 'aat',         # [at]
    'ak': 'aak',         # [ak]
    
    # e 系韵母
    'e': 'e',            # [e]
    'ei': 'ei',          # [ei]
    'eu': 'eu',          # [eu]
    'em': 'em',          # [em]
    'en': 'en',          # [en]
    'ep': 'ep',          # [ep]
    'et': 'et',          # [et]

    # o 系韵母
    'ɔ': 'o',            # [ɔ]
    'ɔi': 'oi',          # [ɔi]
    'ɔn': 'on',          # [ɔn]
    'ɔŋ': 'ong',         # [ɔŋ]
    'ɔη': 'ong',         # [ɔη] (eta variant)
    'ɔt': 'ot',          # [ɔt]
    'ɔk': 'ok',          # [ɔk]
    
    # i 系韵母
    'i': 'i',            # [i]
    'iu': 'iu',          # [iu]
    'im': 'im',          # [im]
    'in': 'in',          # [in]
    'ip': 'ip',          # [ip]
    'it': 'it',          # [it]
    'iŋ': 'ing',         # [iŋ]
    'iη': 'ing',         # [iη] (eta variant)
    'ik': 'ik',          # [ik]

    # iɛ 系韵母
    'iɛ': 'ia',          # [ie]
    'iɛŋ': 'iang',       # [iɛŋ]
    'iɛη': 'iang',       # [iɛη] (eta variant)
    'iɛk': 'iak',        # [iɛk]
    
    # u 系韵母
    'u': 'u',            # [u]
    'ui': 'ui',          # [ui]
    'uɔ': 'uɔ',          # [uɔ]
    'un': 'un',          # [un]
    'uŋ': 'ung',         # [uŋ]
    'uη': 'ung',         # [uη] (eta variant)
    'ut': 'ut',          # [ut]
    'uk': 'uk',          # [uk]
    
    # 独立鼻音韵母
    'm': 'm',            # [m]
    'ŋ': 'ng',           # [ŋ]
    'η': 'ng',           # [η] (eta, alternative to ŋ)
}

def split_syllables(ipa_text):
    """
    按声调数字分隔音节
    支持IPA格式，可能包含声调数字或声调符号
    处理五度标记法声调（33, 55, 11, 22, 32）
    处理声母和送气符号之间的空格（如 "ts 'iɛ33" → "ts'iɛ33"）
    """
    # 移除零宽字符
    ipa_text = ipa_text.replace('\u200d', '').replace('\u200c', '')
    
    # 统一单引号：将所有类型的单引号统一为左单引号
    ipa_text = ipa_text.replace("'", "'").replace("'", "'")
    
    # 处理声母和送气符号之间的空格
    # 匹配模式：声母（如 ts, p, t, k）+ 空格 + 送气符号（'）+ 韵母
    # 将 "ts 'iɛ33" 转换为 "ts'iɛ33"
    ipa_text = re.sub(r'([a-z]+)\s+([\'ˈ])', r'\1\2', ipa_text)
    
    # 使用正则表达式按五度标记法声调分隔音节
    # 匹配：IPA字符（包括各种音标符号）+ 五度标记法声调（两位或三位数字，如 33, 55, 11, 21, 32, 325 等）
    # IPA字符包括：字母、音标符号（如 ː ʰ ʲ ʷ 等）
    # 先匹配三位数字声调，再匹配两位数字声调
    syllables = re.findall(r'[a-zæɑɐəɛɜɨɪɯɵœɔɞɶɷɸβθðʃʒʂʐçʝxɣχʁħʕʜʢɦɬɮʋɹɻɰʎʟɓɗɠʛɥɧɺɰᵊᵿŋη\u2018\u2019\'ˈ]+[0-9]{2,3}', ipa_text, re.IGNORECASE)
    
    # 如果没有找到五度标记法声调，尝试按空格分隔
    if not syllables:
        syllables = ipa_text.split()
    
    return syllables

def convert_syllable(syllable):
    """
    转换单个音节从开平方言IPA到粤拼
    支持五度标记法声调（33, 55, 11, 21, 32）
    """
    # 统一单引号：将所有类型的单引号（普通单引号 U+0027、左单引号 U+2018、右单引号 U+2019等）统一为左单引号
    syllable = syllable.replace("'", "'").replace("'", "'")
    
    # 先处理声母和送气符号之间的空格（如果还有的话）
    syllable = re.sub(r'([a-z]+)\s+([\'ˈ])', r'\1\2', syllable)
    
    # 提取声调（五度标记法：两位或三位数字，如 33, 55, 11, 21, 32, 325 等）
    # 先尝试匹配五度标记法声调（两位或三位数字）
    # 注意：包含 ŋ 等常见 IPA 字符
    match = re.match(r'([a-zæɑɐəɛɜɨɪɯɵœɔɞɶɷɸβθðʃʒʂʐçʝxɣχʁħʕʜʢɦɬɮʋɹɻɰʎʟɓɗɠʛɥɧɺɰᵊᵿŋη\u2018\u2019\'ˈ]+)([0-9]{2,3})', syllable, re.IGNORECASE)
    if not match:
        # 如果没有五度标记法声调，尝试匹配整个音节
        phonetic = syllable.lower()
        tone = ''
    else:
        phonetic = match.group(1).lower()
        tone = match.group(2)
    
    # 尝试所有可能的声母+韵母拆分，并选择最合理的一个
    valid_splits = []
    
    # 按长度排序声母（长的优先匹配）
    sorted_initials = sorted(INITIAL_MAP.keys(), key=len, reverse=True)
    
    # 先尝试匹配声母+韵母的组合
    for init in sorted_initials:
        if phonetic.startswith(init):
            potential_final = phonetic[len(init):]
            # 验证剩余部分是否是有效的韵母
            if potential_final in FINAL_MAP:
                valid_splits.append((init, potential_final, len(potential_final), True))
            elif potential_final:  # 如果韵母不在映射表中，但仍然记录（可能是缺失的映射）
                valid_splits.append((init, potential_final, len(potential_final), False))
    
    # 如果没有找到有效的声母+韵母组合，尝试只匹配韵母（无声母的情况）
    if not valid_splits and phonetic in FINAL_MAP:
        valid_splits.append(('', phonetic, len(phonetic), True))
    
    # 如果找到多个有效拆分，优先选择韵母在映射表中的，然后选择韵母最长的
    if valid_splits:
        # 先按是否在映射表中排序（在映射表中的优先），再按韵母长度排序
        valid_splits.sort(key=lambda x: (not x[3], -x[2]))
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
        # i、iu、im、in、ip、it 前面没有声母时，应添加 j
        if final in ['i', 'iu', 'im', 'in', 'ip', 'it', 'iɛ', 'iɛŋ', 'iɛk']:
            jyutping_initial = 'j'
        # u、ui、un、ut、uk、uɔ 前面没有声母时，应添加 w
        # 注意：uŋ 不需要添加 w，直接转换为 ung
        elif final in ['u', 'ui', 'un', 'ut', 'uk', 'uɔ']:
            jyutping_initial = 'w'
    
    # 转换声调
    if tone:
        if '-' in tone:
            # 变调格式：分别转换每个声调
            tone_parts = tone.split('-')
            jyutping_tones = [TONE_MAP.get(t, t) for t in tone_parts]
            jyutping_tone = '-'.join(jyutping_tones)
        elif len(tone) == 3:
            # 三位数字声调（如 325）
            # 先检查整个三位数字是否在映射表中（如 325 → 6*）
            if tone in TONE_MAP:
                jyutping_tone = TONE_MAP[tone]
            else:
                # 如果不在映射表中，取前两位进行转换（如 32 → 6）
                tone_2digit = tone[:2]
                jyutping_tone = TONE_MAP.get(tone_2digit, tone)
        else:
            # 单一声调（两位数字）
            jyutping_tone = TONE_MAP.get(tone, tone)
    else:
        jyutping_tone = ''
    
    # 组合结果
    result = jyutping_initial + jyutping_final + jyutping_tone
    
    return result

def convert_ipa_to_jyutping(ipa_text):
    """
    转换开平方言IPA文本到粤拼（Jyutping）
    支持多音节，用 / 分隔的读音等格式
    """
    if not ipa_text or ipa_text.strip() == '':
        return ipa_text
    
    # 处理 / 分隔的多个读音（如：pa1 / pa5）
    if '/' in ipa_text:
        parts = ipa_text.split('/')
        converted_parts = []
        for part in parts:
            part = part.strip()
            if part:
                syllables = split_syllables(part)
                jyutping_syllables = [convert_syllable(syl) for syl in syllables]
                converted_parts.append(' '.join(jyutping_syllables))
        return ' / '.join(converted_parts)
    
    # 处理普通的音节序列
    syllables = split_syllables(ipa_text)
    
    # 转换每个音节
    jyutping_syllables = [convert_syllable(syl) for syl in syllables]
    
    # 用空格连接
    return ' '.join(jyutping_syllables)

def normalize_ipa(ipa_text):
    """
    规范化IPA格式：
    1. 统一单引号格式（将所有类型的单引号统一为左单引号 U+2018）
       - 普通单引号 U+0027 (')
       - 左单引号 U+2018 (')
       - 右单引号 U+2019 (')
       - 修饰字母左单引号 U+02BB (ʻ)
    2. 移除声母和送气符号之间的空格（如 "ts 'ut" → "ts'ut"）
    3. 保持其他格式不变（包括 / 分隔的多个读音）
    """
    if not ipa_text or ipa_text.strip() == '':
        return ipa_text
    
    # 处理 / 分隔的多个读音
    if '/' in ipa_text:
        parts = ipa_text.split('/')
        normalized_parts = []
        for part in parts:
            part = part.strip()
            if part:
                # 统一单引号：将所有类型的单引号统一为左单引号 U+2018
                normalized_part = (part.replace("'", "\u2018")  # 普通单引号
                                   .replace("'", "\u2018")        # 右单引号
                                   .replace("\u02BB", "\u2018"))  # 修饰字母左单引号
                # 移除声母和送气符号之间的空格
                normalized_part = re.sub(r'([a-z]+)\s+(\u2018)', r'\1\2', normalized_part)
                normalized_parts.append(normalized_part)
        return ' / '.join(normalized_parts)
    
    # 统一单引号：将所有类型的单引号统一为左单引号 U+2018
    normalized = (ipa_text.replace("'", "\u2018")      # 普通单引号 U+0027
                 .replace("'", "\u2018")               # 右单引号 U+2019
                 .replace("\u02BB", "\u2018"))          # 修饰字母左单引号 U+02BB
    
    # 移除声母和送气符号之间的空格
    # 匹配模式：声母（字母）+ 空格 + 左单引号 + 韵母
    normalized = re.sub(r'([a-z]+)\s+(\u2018)', r'\1\2', normalized)
    
    return normalized

def convert_csv(input_file, output_file, ipa_column='pronunciation'):
    """
    转换CSV文件中的IPA列（开平方言IPA方案）到jyutping（粤拼）
    
    参数:
        input_file: 输入CSV文件路径
        output_file: 输出CSV文件路径
        ipa_column: IPA列的名称，默认为 'pronunciation'
    """
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        if not fieldnames:
            print("错误：CSV文件没有列名")
            return
        
        # 添加新的列名用于粤拼
        if 'jyutping' not in fieldnames:
            fieldnames = list(fieldnames)
            # 在IPA列后面插入jyutping列
            if ipa_column in fieldnames:
                ipa_index = fieldnames.index(ipa_column)
                fieldnames.insert(ipa_index + 1, 'jyutping')
            else:
                fieldnames.append('jyutping')
        
        rows = []
        for row in reader:
            ipa_original = row.get(ipa_column, '')
            
            # 规范化IPA格式（统一单引号、移除空格）
            ipa_normalized = normalize_ipa(ipa_original)
            
            # 转换为粤拼（使用规范化后的IPA）
            jyutping = convert_ipa_to_jyutping(ipa_normalized)
            
            # 更新IPA列为规范化后的格式
            row[ipa_column] = ipa_normalized
            
            # 添加jyutping列
            row['jyutping'] = jyutping
            rows.append(row)
            
            # 打印前几个示例
            if len(rows) <= 5:
                print(f"词头: {row.get('headword', row.get('word', ''))}")
                print(f"原IPA: {ipa_original}")
                print(f"规范化IPA: {ipa_normalized}")
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
    input_file = 'output/开平方言_OCR_106-268.csv'
    output_file = 'output/开平方言_OCR_106-268_粤拼.csv'
    
    convert_csv(input_file, output_file, 'ipa')
