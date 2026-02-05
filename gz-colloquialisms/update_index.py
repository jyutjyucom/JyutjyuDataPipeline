import csv

# 读取原CSV文件
input_file = '广州话俗语词典.csv'
output_file = '广州话俗语词典_updated.csv'

# 第一遍：读取所有数据，统计每个phrase的义项数量
with open(input_file, 'r', encoding='utf-8-sig') as f_in:
    reader = csv.DictReader(f_in)
    all_rows = list(reader)
    fieldnames = reader.fieldnames

# 统计每个phrase的出现次数
phrase_counts = {}
for row in all_rows:
    phrase = row['phrases']
    phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

# 第二遍：写入更新后的数据
with open(output_file, 'w', encoding='utf-8-sig', newline='') as f_out:
    writer = csv.DictWriter(f_out, fieldnames=fieldnames)
    writer.writeheader()
    
    current_entry_number = 0  # 当前词条编号
    previous_phrase = None  # 上一个词条的字头
    current_sense_in_entry = 0  # 当前词条内的义项编号
    
    for row in all_rows:
        current_phrase = row['phrases']
        
        # 判断是否是新词条：字头与上一条不同
        if current_phrase != previous_phrase:
            # 新词条开始
            current_entry_number += 1
            current_sense_in_entry = 0  # 重置义项编号
            previous_phrase = current_phrase
        
        # 增加当前词条的义项编号
        current_sense_in_entry += 1
        
        # 获取这个phrase总共有多少个义项
        total_senses = phrase_counts[current_phrase]
        
        # 更新sense_number和index
        if total_senses == 1:
            # 只有一个义项，sense_number为0，index不带后缀
            row['sense_number'] = '0'
            new_index = str(current_entry_number)
        else:
            # 有多个义项，sense_number从1开始，index都要带义项编号
            row['sense_number'] = str(current_sense_in_entry)
            new_index = f"{current_entry_number}-{current_sense_in_entry}"
        
        # 更新index
        row['index'] = new_index
        writer.writerow(row)

print(f"处理完成！结果已保存到 {output_file}")
print(f"已根据连续相同的字头（phrases）重新编号")
print(f"共处理了 {current_entry_number} 个词条")

