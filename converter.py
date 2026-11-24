import re
import os
from datetime import datetime
import csv
from typing import List, Dict, Optional, Any 
import argparse

# --- 常量定义 ---
# 正则表达式预编译，提高效率
RE_WEEKDAY = re.compile(r'星期[一二三四五六日]')
RE_AUTHOR = re.compile(r'\(([^)]+)\)[^(]*$') # 匹配书名后括号内的作者
RE_PAGE = re.compile(r'第 (\S+) 页')
RE_LOCATION = re.compile(r'位置 #(\d+(?:-\d+)?)')
RE_TIMESTAMP = re.compile(r'添加于 (.*?)$')
RE_WHITESPACE = re.compile(r'\s+')

# CSV文件头部
CSV_HEADERS = ["Title", "Author", "Date", "Location", "Highlight", "Note", "Tag"]
# Kindle My Clippings.txt 文件名
DEFAULT_CLIPPINGS_FILE = "My Clippings-2025_05_06.txt"
# 输出CSV文件名
DEFAULT_OUTPUT_CSV = "MyClippings.csv"

def parse_datetime_string(time_str: str) -> Optional[datetime]:
    """将Kindle中文时间戳字符串转换为datetime对象"""
    time_str = RE_WEEKDAY.sub('', time_str).strip()
    time_str = time_str.replace('年', '-').replace('月', '-').replace('日', '')
    time_str = time_str.replace('上午', 'AM').replace('下午', 'PM')
    time_str = RE_WHITESPACE.sub(' ', time_str).strip()

    for fmt in ('%Y-%m-%d %p%I:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    print(f"日期解析失败: '{time_str}'")
    return None

def parse_single_clipping(chunk_lines: List[str]) -> Optional[Dict[str, Any]]:
    """解析单个剪贴条目(高亮或笔记)"""
    if not chunk_lines or len(chunk_lines) < 3:
        return None

    entry: Dict[str, Any] = {}
    # 移除BOM字符 (通常在文件开头，但行首也可能出现)
    book_author_line = chunk_lines[0].strip().replace("\ufeff", "")
    metadata_line = chunk_lines[1].strip()
    content_line = chunk_lines[3].strip().replace("\ufeff", "") if len(chunk_lines) > 3 else ""

    # 解析书名和作者
    author_match = RE_AUTHOR.search(book_author_line)
    if author_match:
        entry['Author'] = author_match.group(1).strip()
        entry['Title'] = book_author_line[:author_match.start()].strip()
    else:
        entry['Title'] = book_author_line
        entry['Author'] = ""

    # 判断条目类型 (高亮或笔记)
    if "标注" in metadata_line: # 简化判断条件
        entry['Type'] = 'Highlight'
    elif "笔记" in metadata_line:
        entry['Type'] = 'Note'
    else:
        return None # 未知类型

    # 解析页码
    page_match = RE_PAGE.search(metadata_line)
    entry['Page'] = page_match.group(1) if page_match else None

    # 解析位置信息
    location_match = RE_LOCATION.search(metadata_line)
    entry['Location_raw'] = location_match.group(1) if location_match else None
    entry['Location_start'] = entry['Location_end'] = None
    if entry['Location_raw']:
        parts = entry['Location_raw'].split('-')
        try:
            entry['Location_start'] = int(parts[0])
            entry['Location_end'] = int(parts[-1])
        except ValueError:
            return None # 位置格式无效

    # 解析时间戳
    time_match = RE_TIMESTAMP.search(metadata_line)
    if time_match:
        entry['Timestamp_str'] = time_match.group(1)
        entry['Timestamp'] = parse_datetime_string(entry['Timestamp_str'])
        if entry['Timestamp'] is None: return None # 时间戳解析失败
    else:
        return None # 未找到时间戳

    entry['Content'] = content_line
    # 为笔记去重创建标志键
    loc_key_part = str(entry['Location_raw']) if entry['Location_raw'] else "None"
    entry['Deduplication_Key'] = f"{entry['Title']}_{entry['Author']}_{loc_key_part}"

    return entry

def process_clippings_text(all_clippings_text: str) -> List[Dict[str, Any]]:
    """处理My Clippings.txt的全部文本内容，返回结构化的剪贴列表"""
    raw_entries: List[Dict[str, Any]] = []
    current_chunk_lines: List[str] = []

    for line in all_clippings_text.splitlines():
        if line.strip() == "==========":
            if current_chunk_lines:
                parsed = parse_single_clipping(current_chunk_lines)
                if parsed:
                    raw_entries.append(parsed)
            current_chunk_lines = []
        else:
            current_chunk_lines.append(line)
    if current_chunk_lines: # 处理最后一个条目
        parsed = parse_single_clipping(current_chunk_lines)
        if parsed:
            raw_entries.append(parsed)
    return raw_entries

def deduplicate_notes(notes_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """对笔记列表进行去重，保留最新的笔记"""
    notes_map: Dict[str, Dict[str, Any]] = {}
    for entry in notes_list:
        key = entry['Deduplication_Key']
        if key not in notes_map or entry['Timestamp'] > notes_map[key]['Timestamp']:
            notes_map[key] = entry
    return list(notes_map.values())

def deduplicate_highlights(highlights_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """对高亮列表进行去重，规则：页码及位置原始字符串/起始/结束任一相同，则视为同一条，保留最新"""
    # 按时间戳升序排序，便于后续处理时，新的替换旧的
    sorted_highlights = sorted(highlights_list, key=lambda x: x['Timestamp'])
    final_highlights: List[Dict[str, Any]] = []

    for current_hl in sorted_highlights:
        is_merged_or_older = False
        for i in range(len(final_highlights) - 1, -1, -1): # 反向迭代以便安全替换
            existing_hl = final_highlights[i]

            # 基础匹配条件：书名、作者相同
            if not (current_hl['Title'] == existing_hl['Title'] and \
                    current_hl['Author'] == existing_hl['Author']):
                continue

            # 位置匹配条件
            loc_match = False
            # 条件a: 位置原始字符串相同
            if current_hl.get('Location_raw') and current_hl['Location_raw'] == existing_hl.get('Location_raw'):
                loc_match = True
            # 条件b: 起始位置相同
            elif current_hl.get('Location_start') is not None and current_hl['Location_start'] == existing_hl.get('Location_start'):
                loc_match = True
            # 条件c: 结束位置相同
            elif current_hl.get('Location_end') is not None and current_hl['Location_end'] == existing_hl.get('Location_end'):
                loc_match = True

            if loc_match:
                # 若当前高亮时间更新，则替换已有的；否则视为旧版/重复
                if current_hl['Timestamp'] > existing_hl['Timestamp']:
                    final_highlights[i] = current_hl
                is_merged_or_older = True
                break # 已找到对应高亮并处理完毕

        if not is_merged_or_older:
            final_highlights.append(current_hl)
    return final_highlights

def match_notes_to_highlights(
    highlights: List[Dict[str, Any]],
    notes: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """将去重后的笔记匹配到高亮条目上"""
    output_data: List[Dict[str, Any]] = []
    # 为了提高查找效率，将笔记按书名、作者（不要使用页码，因为跨页笔记会匹配不到标注）分组 (可选优化，当前列表大小可能不需要)
    # notes_grouped = defaultdict(list)
    # for note in notes:
    #     notes_grouped[(note['Title'], note['Author']
    # ].append(note)

    for hl in highlights:
        matched_note_content = None
        # 从最新的笔记开始匹配
        for note in sorted(notes, key=lambda x: x['Timestamp'], reverse=True):
            if hl['Title'] == note['Title'] and \
               hl['Author'] == note['Author']and \
               hl.get('Location_start') is not None and note.get('Location_start') is not None:

                hl_loc_start, hl_loc_end = hl['Location_start'], hl['Location_end']
                note_loc_start = note['Location_start']

                # 笔记位置在高亮范围内或与点状高亮位置相同
                if (hl_loc_start == hl_loc_end and note_loc_start == hl_loc_start) or \
                   (hl_loc_start <= note_loc_start <= hl_loc_end):
                    matched_note_content = note['Content']
                    break # 已找到匹配的最新笔记

        output_data.append({
            "Title": hl['Title'],
            "Author": hl['Author'],
            "Date": hl['Timestamp'].strftime('%Y-%m-%d %H:%M:%S'), # 统一日期格式
            "Location": str(hl['Page']) if hl['Page'] else str(hl.get('Location_start', '')),
            "Highlight": hl['Content'],
            "Note": matched_note_content,
            "Location_responsive": hl.get('Location_raw', '')
        })
    return output_data

def parse_and_collate_clippings(all_clippings_text: str) -> List[Dict[str, Any]]:
    """完整解析My Clippings文本：原始解析、分类、去重、笔记高亮匹配"""
    raw_entries = process_clippings_text(all_clippings_text)

    notes_raw = [e for e in raw_entries if e['Type'] == 'Note']
    highlights_raw = [e for e in raw_entries if e['Type'] == 'Highlight']

    deduplicated_notes = deduplicate_notes(notes_raw)
    deduplicated_highlights = deduplicate_highlights(highlights_raw)

    collated_data = match_notes_to_highlights(deduplicated_highlights, deduplicated_notes)

    # 按书名、作者、日期排序最终结果
    collated_data.sort(key=lambda x: (
        x['Title'],
        x['Author'],
        # x['Date']已经是字符串，可以直接比较；或转回datetime对象比较
        datetime.strptime(x['Date'], '%Y-%m-%d %H:%M:%S')
    ))
    return collated_data

def read_clippings_file(filepath: str) -> Optional[str]:
    """读取剪贴文件内容"""
    try:
        # 优先尝试带./路径，失败则尝试不带 (针对不同运行环境)
        try:
            with open(f"./{filepath}", "r", encoding="UTF8") as f:
                return f.read()
        except FileNotFoundError:
            with open(filepath, "r", encoding="UTF8") as f:
                return f.read()
    except FileNotFoundError:
        print(f"错误: 文件 '{filepath}' 未找到。")
        return None
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return None

def write_to_csv(data: List[Dict[str, Any]], output_filename: str = DEFAULT_OUTPUT_CSV, sort_by_key: Optional[str] = "Title") -> None:
    """将处理后的数据写入CSV文件"""
    if not data:
        print("无数据可写入。")
        return

    # `parse_and_collate_clippings` 已排序，此处的 `sort_clips` 或可移除或调整
    # if sort_by_key:
    #     data = sorted(data, key=lambda d: d.get(sort_by_key, ""))

    # 输出目录默认为当前目录
    os.makedirs(os.path.dirname(output_filename) or ".", exist_ok=True)

    with open(output_filename, mode="w", encoding="UTF-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for row_dict in data:
            # 确保所有字段都存在，对于Note字段，如果为None则写入空字符串
            # 在match_notes_to_highlights中Note已处理为None或字符串
            # CSV行数据准备
            csv_row = {
                "Title": row_dict.get("Title", ""),
                "Author": row_dict.get("Author", ""),
                "Date": row_dict.get("Date", ""),
                "Location": row_dict.get("Location", ""),
                "Highlight": str(row_dict.get("Highlight", "")).replace("\n", "\\n"),
                "Note": str(row_dict.get("Note", "") if row_dict.get("Note") is not None else "").replace("\n", "\\n"),
                "Tag": "Kindle", # Location_responsive 字段未在表头中，若需要可添加
            }
            writer.writerow(csv_row)
    print(f"剪贴已成功写入到 {output_filename}")

def run_parser(clippings_filepath: str, output_csv_filepath: str): # 参数化
    """执行剪报解析和写入操作的主函数"""
    print(f"开始处理输入文件: {clippings_filepath}")
    clippings_text = read_clippings_file(clippings_filepath)
    if clippings_text:
        processed_data = parse_and_collate_clippings(clippings_text)
        write_to_csv(processed_data, output_csv_filepath)
        print(f"处理完成。输出文件: {output_csv_filepath}")
    else:
        print(f"未能读取或处理文件: {clippings_filepath}")

if __name__ == "__main__":
    # --- 命令行参数解析 ---
    parser = argparse.ArgumentParser(description="将 Kindle 'My Clippings.txt' 文件转换为 Readwise 兼容的 CSV 文件。")
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=DEFAULT_CLIPPINGS_FILE, # 提供默认输入文件名
        help="Kindle 'My Clippings.txt' 文件的路径和名称。"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=DEFAULT_OUTPUT_CSV, # 如果未指定，则使用默认输出文件名
        help=f"输出 CSV 文件的路径和名称。 (默认: {DEFAULT_OUTPUT_CSV})"
    )

    args = parser.parse_args()

    # 使用从命令行获取的参数调用主处理函数
    run_parser(clippings_filepath=args.input, output_csv_filepath=args.output)