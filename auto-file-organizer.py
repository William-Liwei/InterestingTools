#!/usr/bin/env python3
"""
智能文件整理器 - 自动整理杂乱的文件夹
"""

import os
import shutil
import datetime
import time
import argparse
import re
import hashlib
from pathlib import Path
from collections import defaultdict

# 文件类型映射
FILE_TYPES = {
    # 图像文件
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".heic", ".raw", ".cr2"],
    
    # 文档文件
    "文档": [".doc", ".docx", ".pdf", ".txt", ".rtf", ".odt", ".pages", ".md", ".ppt", ".pptx", ".key", ".odp", ".xls", ".xlsx", ".csv", ".numbers", ".ods"],
    
    # 音频文件
    "音频": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".aiff"],
    
    # 视频文件
    "视频": [".mp4", ".avi", ".mov", ".wmv", ".mkv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".3gp"],
    
    # 压缩文件
    "压缩文件": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"],
    
    # 代码文件
    "代码": [".py", ".java", ".c", ".cpp", ".h", ".js", ".html", ".css", ".php", ".rb", ".go", ".swift", ".kt", ".ts", ".json", ".xml", ".yml", ".yaml", ".sql"],
    
    # 可执行文件
    "可执行文件": [".exe", ".msi", ".app", ".bat", ".sh", ".cmd", ".com", ".gadget", ".vb", ".vbs", ".ws", ".wsf"],
}

# 反向映射（扩展名到类型）
EXT_TO_TYPE = {}
for folder, extensions in FILE_TYPES.items():
    for ext in extensions:
        EXT_TO_TYPE[ext] = folder

def parse_arguments():
    parser = argparse.ArgumentParser(description="智能文件整理器 - 自动整理杂乱的文件夹")
    
    parser.add_argument("source_dir", type=str, nargs="?", default=".", 
                        help="要整理的源目录 (默认: 当前目录)")
    
    parser.add_argument("--mode", type=str, choices=["type", "date", "name", "size", "duplicate", "custom", "analyze"], 
                        default="type", help="整理模式 (默认: 按文件类型)")
    
    parser.add_argument("--recursive", action="store_true", 
                        help="递归处理子目录中的文件")
    
    parser.add_argument("--dry-run", action="store_true", 
                        help="仅显示会进行的操作，不实际移动文件")
    
    parser.add_argument("--date-format", type=str, default="%Y-%m", 
                        help="日期模式下的文件夹命名格式 (默认: 年-月)")
    
    parser.add_argument("--size-bins", type=str, default="1MB,10MB,100MB,1GB", 
                        help="大小模式下的分类区间，用逗号分隔 (默认: 1MB,10MB,100MB,1GB)")
    
    parser.add_argument("--min-size", type=str, default="10KB", 
                        help="要处理的最小文件大小 (默认: 10KB)")
    
    parser.add_argument("--exclude", type=str, default="", 
                        help="要排除的文件或目录模式，用逗号分隔 (例如: .git*,node_modules)")
    
    parser.add_argument("--custom-rules", type=str, default="", 
                        help="自定义整理规则文件的路径")
    
    parser.add_argument("--include-hidden", action="store_true", 
                        help="包括隐藏文件 (默认: 排除)")
    
    parser.add_argument("--no-misc", action="store_true", 
                        help="不创建'杂项'文件夹 (默认: 创建以存储未分类文件)")
    
    parser.add_argument("--keep-structure", action="store_true", 
                        help="在递归模式下保持原始目录结构")
    
    parser.add_argument("--organize-by", type=str, choices=["move", "copy", "link"], 
                        default="move", help="整理文件的方式 (默认: 移动)")
    
    return parser.parse_args()

# 文件大小转换函数
def parse_size(size_str):
    """将人类可读的大小字符串转换为字节数"""
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    
    size_str = size_str.upper().replace(" ", "")
    
    if not re.match(r'^\d+(\.\d+)?[A-Z]+$', size_str):
        raise ValueError(f"无效的大小格式: {size_str}")
    
    number = float(re.sub(r'[A-Z]+$', '', size_str))
    unit = re.sub(r'^\d+(\.\d+)?', '', size_str)
    
    if unit not in units:
        raise ValueError(f"未知的大小单位: {unit}")
    
    return int(number * units[unit])

def format_size(size_bytes):
    """将字节大小转换为人类可读的格式"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.1f}KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/(1024**2):.1f}MB"
    elif size_bytes < 1024**4:
        return f"{size_bytes/(1024**3):.1f}GB"
    else:
        return f"{size_bytes/(1024**4):.1f}TB"

def should_process_file(file_path, args):
    """检查是否应该处理此文件"""
    # 检查文件大小
    if os.path.getsize(file_path) < parse_size(args.min_size):
        return False
    
    # 检查是否为隐藏文件
    if not args.include_hidden and os.path.basename(file_path).startswith('.'):
        return False
    
    # 检查排除模式
    if args.exclude:
        exclude_patterns = [p.strip() for p in args.exclude.split(',')]
        for pattern in exclude_patterns:
            if re.search(pattern, file_path):
                return False
    
    return True

def get_file_hash(file_path, block_size=65536):
    """计算文件的SHA-256哈希值"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            sha256.update(block)
    return sha256.hexdigest()

def organize_by_type(file_path, source_dir, args):
    """按文件类型整理"""
    _, ext = os.path.splitext(file_path.lower())
    
    if ext in EXT_TO_TYPE:
        target_dir = os.path.join(source_dir, EXT_TO_TYPE[ext])
    else:
        if args.no_misc:
            return None
        target_dir = os.path.join(source_dir, "杂项")
    
    return target_dir

def organize_by_date(file_path, source_dir, args):
    """按文件修改日期整理"""
    mod_time = os.path.getmtime(file_path)
    date_str = datetime.datetime.fromtimestamp(mod_time).strftime(args.date_format)
    target_dir = os.path.join(source_dir, date_str)
    return target_dir

def organize_by_name(file_path, source_dir, args):
    """按文件名首字母整理"""
    filename = os.path.basename(file_path)
    
    # 获取首字母或首个汉字
    first_char = filename[0].upper()
    
    # 英文字母归类到相应字母文件夹
    if 'A' <= first_char <= 'Z':
        target_dir = os.path.join(source_dir, first_char)
    # 数字归类到"数字"文件夹
    elif '0' <= first_char <= '9':
        target_dir = os.path.join(source_dir, "数字")
    # 汉字和其他字符归类到"其他"文件夹
    else:
        target_dir = os.path.join(source_dir, "其他")
    
    return target_dir

def organize_by_size(file_path, source_dir, args):
    """按文件大小整理"""
    size = os.path.getsize(file_path)
    
    # 解析大小区间
    size_bins = [parse_size(bin_str.strip()) for bin_str in args.size_bins.split(',')]
    size_bins.sort()
    
    # 确定文件所属区间
    for i, bin_size in enumerate(size_bins):
        if size < bin_size:
            if i == 0:
                return os.path.join(source_dir, f"小于{format_size(bin_size)}")
            else:
                return os.path.join(source_dir, f"{format_size(size_bins[i-1])}-{format_size(bin_size)}")
    
    # 大于最大区间
    return os.path.join(source_dir, f"大于{format_size(size_bins[-1])}")

def find_duplicates(file_paths):
    """查找重复文件"""
    # 首先按大小分组
    size_groups = defaultdict(list)
    for file_path in file_paths:
        size = os.path.getsize(file_path)
        size_groups[size].append(file_path)
    
    # 然后只对相同大小的文件计算哈希值
    duplicates = []
    hash_groups = defaultdict(list)
    
    # 只处理有多个文件的大小组
    for size, files in size_groups.items():
        if len(files) < 2:
            continue
        
        for file_path in files:
            file_hash = get_file_hash(file_path)
            hash_groups[file_hash].append(file_path)
    
    # 收集重复文件（有相同哈希值的文件）
    for hash_val, files in hash_groups.items():
        if len(files) > 1:
            duplicates.append(files)
    
    return duplicates

def organize_by_custom(file_path, source_dir, args, rules=None):
    """使用自定义规则整理文件"""
    if not rules:
        return None
    
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()
    
    for rule_name, patterns in rules.items():
        for pattern in patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                return os.path.join(source_dir, rule_name)
    
    if args.no_misc:
        return None
    return os.path.join(source_dir, "杂项")

def process_file(file_path, source_dir, args, rules=None):
    """处理单个文件"""
    if not should_process_file(file_path, args):
        return None
    
    # 根据所选模式确定目标目录
    if args.mode == "type":
        target_dir = organize_by_type(file_path, source_dir, args)
    elif args.mode == "date":
        target_dir = organize_by_date(file_path, source_dir, args)
    elif args.mode == "name":
        target_dir = organize_by_name(file_path, source_dir, args)
    elif args.mode == "size":
        target_dir = organize_by_size(file_path, source_dir, args)
    elif args.mode == "custom":
        target_dir = organize_by_custom(file_path, source_dir, args, rules)
    else:
        return None
    
    if not target_dir:
        return None
    
    # 创建目标目录（如果是dry run则仅打印）
    if not args.dry_run and not os.path.exists(target_dir):
        os.makedirs(target_dir)
    
    # 确定目标文件路径
    filename = os.path.basename(file_path)
    target_path = os.path.join(target_dir, filename)
    
    # 处理文件名冲突
    counter = 1
    while os.path.exists(target_path) and not args.dry_run:
        name, ext = os.path.splitext(filename)
        target_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
        counter += 1
    
    return target_path

def load_custom_rules(rules_file):
    """从文件加载自定义规则"""
    if not os.path.exists(rules_file):
        print(f"错误: 自定义规则文件 '{rules_file}' 不存在。")
        return None
    
    rules = {}
    current_category = None
    
    with open(rules_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith('#'):
                continue
            
            # 类别行
            if line.startswith('[') and line.endswith(']'):
                current_category = line[1:-1].strip()
                rules[current_category] = []
            # 规则行
            elif current_category is not None:
                rules[current_category].append(line)
    
    return rules

def analyze_directory(directory, args):
    """分析目录并生成报告"""
    print(f"\n📊 目录分析: {directory}")
    print("=" * 60)
    
    all_files = []
    total_size = 0
    extension_count = defaultdict(int)
    extension_size = defaultdict(int)
    type_count = defaultdict(int)
    type_size = defaultdict(int)
    
    # 遍历目录
    for root, dirs, files in os.walk(directory):
        # 排除不需要处理的目录
        if not args.include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        if args.exclude:
            exclude_patterns = [p.strip() for p in args.exclude.split(',')]
            for pattern in exclude_patterns:
                dirs[:] = [d for d in dirs if not re.search(pattern, os.path.join(root, d))]
        
        for file in files:
            file_path = os.path.join(root, file)
            
            # 检查是否应该处理此文件
            if not should_process_file(file_path, args):
                continue
            
            all_files.append(file_path)
            
            # 统计文件大小
            size = os.path.getsize(file_path)
            total_size += size
            
            # 统计扩展名
            _, ext = os.path.splitext(file.lower())
            extension_count[ext] += 1
            extension_size[ext] += size
            
            # 统计文件类型
            file_type = "杂项"
            if ext in EXT_TO_TYPE:
                file_type = EXT_TO_TYPE[ext]
            type_count[file_type] += 1
            type_size[file_type] += size
    
    # 打印总体统计
    print(f"总文件数: {len(all_files)}")
    print(f"总大小: {format_size(total_size)}")
    print(f"平均文件大小: {format_size(total_size / max(1, len(all_files)))}")
    
    # 按文件类型打印统计
    print("\n🗂️ 按文件类型统计:")
    print(f"{'类型':<15} {'数量':<10} {'大小':<10} {'占比':<10}")
    print("-" * 45)
    
    for file_type in sorted(type_count.keys()):
        count = type_count[file_type]
        size = type_size[file_type]
        percent = (size / total_size) * 100 if total_size > 0 else 0
        print(f"{file_type:<15} {count:<10} {format_size(size):<10} {percent:.1f}%")
    
    # 打印前10个最常见的扩展名
    print("\n📑 最常见的文件类型:")
    print(f"{'扩展名':<10} {'数量':<10} {'大小':<10} {'占比':<10}")
    print("-" * 45)
    
    for ext, count in sorted(extension_count.items(), key=lambda x: x[1], reverse=True)[:10]:
        size = extension_size[ext]
        percent = (size / total_size) * 100 if total_size > 0 else 0
        print(f"{ext or '(无)':<10} {count:<10} {format_size(size):<10} {percent:.1f}%")
    
    # 查找重复文件
    print("\n🔍 查找重复文件...")
    duplicates = find_duplicates(all_files)
    
    if duplicates:
        dup_count = sum(len(group) for group in duplicates)
        dup_size = sum(os.path.getsize(group[0]) * (len(group) - 1) for group in duplicates)
        print(f"找到 {len(duplicates)} 组重复文件，共 {dup_count} 个文件")
        print(f"可节省空间: {format_size(dup_size)}")
        
        # 打印前5组重复文件
        print("\n示例重复文件组:")
        for i, group in enumerate(duplicates[:5]):
            print(f"\n组 {i+1} ({len(group)} 个文件，每个 {format_size(os.path.getsize(group[0]))})")
            for j, file_path in enumerate(group[:3]):
                print(f"  {j+1}. {os.path.relpath(file_path, directory)}")
            if len(group) > 3:
                print(f"  ...以及其他 {len(group) - 3} 个文件")
    else:
        print("没有找到重复文件。")
    
    print("\n💡 建议:")
    
    # 根据分析结果给出建议
    if duplicates:
        potential_savings = sum(os.path.getsize(group[0]) * (len(group) - 1) for group in duplicates)
        if potential_savings > total_size * 0.1:  # 如果可以节省超过10%的空间
            print(f"- 处理重复文件可以节省 {format_size(potential_savings)} ({(potential_savings/total_size*100):.1f}%) 的空间")
    
    # 建议整理大型文件类型
    large_types = [(t, s) for t, s in type_size.items() if s > total_size * 0.2]
    if large_types:
        print(f"- 考虑优先整理以下占用空间较大的文件类型:")
        for file_type, size in sorted(large_types, key=lambda x: x[1], reverse=True):
            print(f"  * {file_type} ({format_size(size)}, {(size/total_size*100):.1f}%)")
    
    # 如果没有明显的大型文件类型，建议按日期或类型整理
    else:
        print("- 建议使用 '--mode type' 按文件类型整理或 '--mode date' 按日期整理")
    
    print("=" * 60)

def organize_files(args):
    """整理文件的主函数"""
    source_dir = os.path.abspath(args.source_dir)
    
    if not os.path.exists(source_dir):
        print(f"错误: 源目录 '{source_dir}' 不存在。")
        return
    
    print(f"\n🚀 智能文件整理器")
    print(f"源目录: {source_dir}")
    print(f"模式: {args.mode}")
    print(f"{'(仅显示操作，不实际移动文件)' if args.dry_run else ''}")
    print("=" * 60)
    
    # 如果是分析模式，只进行分析不整理
    if args.mode == "analyze":
        analyze_directory(source_dir, args)
        return
    
    # 加载自定义规则
    custom_rules = None
    if args.mode == "custom":
        if not args.custom_rules:
            print("错误: 自定义模式需要指定规则文件 (--custom-rules)")
            return
        custom_rules = load_custom_rules(args.custom_rules)
        if not custom_rules:
            return
    
    # 收集要处理的文件
    all_files = []
    
    if args.recursive:
        for root, dirs, files in os.walk(source_dir):
            # 排除不需要处理的目录
            if not args.include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            if args.exclude:
                exclude_patterns = [p.strip() for p in args.exclude.split(',')]
                for pattern in exclude_patterns:
                    dirs[:] = [d for d in dirs if not re.search(pattern, os.path.join(root, d))]
            
            for file in files:
                file_path = os.path.join(root, file)
                all_files.append(file_path)
    else:
        for file in os.listdir(source_dir):
            file_path = os.path.join(source_dir, file)
            if os.path.isfile(file_path):
                all_files.append(file_path)
    
    # 重复文件处理
    if args.mode == "duplicate":
        print("查找重复文件...")
        duplicates = find_duplicates(all_files)
        
        if not duplicates:
            print("没有发现重复文件。")
            return
        
        # 创建重复文件目录
        duplicate_dir = os.path.join(source_dir, "重复文件")
        if not args.dry_run and not os.path.exists(duplicate_dir):
            os.makedirs(duplicate_dir)
        
        print(f"\n找到 {len(duplicates)} 组重复文件:")
        
        total_saved = 0
        for i, group in enumerate(duplicates):
            # 保留第一个文件，移动其余文件
            original = group[0]
            duplicates_to_move = group[1:]
            
            group_dir = os.path.join(duplicate_dir, f"组_{i+1}")
            if not args.dry_run and not os.path.exists(group_dir):
                os.makedirs(group_dir)
            
            print(f"\n组 {i+1} ({len(group)} 个文件, 每个 {format_size(os.path.getsize(original))})")
            print(f"  保留: {os.path.relpath(original, source_dir)}")
            
            for dup in duplicates_to_move:
                saved_space = os.path.getsize(dup)
                total_saved += saved_space
                
                target_path = os.path.join(group_dir, os.path.basename(dup))
                print(f"  移动: {os.path.relpath(dup, source_dir)} -> {os.path.relpath(target_path, source_dir)}")
                
                if not args.dry_run:
                    counter = 1
                    while os.path.exists(target_path):
                        name, ext = os.path.splitext(os.path.basename(dup))
                        target_path = os.path.join(group_dir, f"{name}_{counter}{ext}")
                        counter += 1
                    
                    if args.organize_by == "move":
                        shutil.move(dup, target_path)
                    elif args.organize_by == "copy":
                        shutil.copy2(dup, target_path)
                    elif args.organize_by == "link":
                        os.symlink(os.path.abspath(dup), target_path)
        
        print(f"\n总计: 处理了 {sum(len(g)-1 for g in duplicates)} 个重复文件")
        print(f"可节省空间: {format_size(total_saved)}")
        return
    
    # 处理所有文件
    file_count = 0
    moved_count = 0
    skipped_count = 0
    
    for file_path in all_files:
        rel_path = os.path.relpath(file_path, source_dir)
        
        # 如果是递归模式且保持结构，需要调整目标目录
        if args.recursive and args.keep_structure:
            file_dir = os.path.dirname(rel_path)
            sub_source_dir = os.path.join(source_dir, file_dir) if file_dir else source_dir
        else:
            sub_source_dir = source_dir
        
        # 处理文件
        target_path = process_file(file_path, sub_source_dir, args, custom_rules)
        
        if not target_path:
            skipped_count += 1
            continue
        
        file_count += 1
        
        if file_path == target_path:
            continue
        
        print(f"{'[预览]' if args.dry_run else ''} {rel_path} -> {os.path.relpath(target_path, source_dir)}")
        
        # 执行操作（除非是预览模式）
        if not args.dry_run:
            try:
                if args.organize_by == "move":
                    shutil.move(file_path, target_path)
                elif args.organize_by == "copy":
                    shutil.copy2(file_path, target_path)
                elif args.organize_by == "link":
                    os.symlink(os.path.abspath(file_path), target_path)
                
                moved_count += 1
            except Exception as e:
                print(f"错误: 无法处理文件 '{rel_path}': {e}")
                skipped_count += 1
    
    print("\n" + "=" * 60)
    if args.dry_run:
        print(f"预览完成: 将处理 {file_count} 个文件 (跳过 {skipped_count} 个)")
    else:
        print(f"整理完成: 已处理 {moved_count} 个文件 (跳过 {skipped_count} 个)")

if __name__ == "__main__":
    args = parse_arguments()
    organize_files(args)
