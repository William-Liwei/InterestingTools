#!/usr/bin/env python3
"""
GitHub活动模拟器 - 更安全的版本，不会污染现有仓库
"""

import os
import random
import datetime
import subprocess
import time
import argparse
import tempfile
import shutil
from pathlib import Path

# 可能的提交消息列表
COMMIT_MESSAGES = [
    "更新文档",
    "修复bug",
    "添加新功能",
    "重构代码",
    "优化性能",
    "改进UI/UX",
    "更新依赖",
    "添加测试",
    "修复安全问题",
    "代码清理",
    "实现新API",
    "修复拼写错误",
    "更新README",
    "添加注释",
    "重组项目结构",
    "修复边界情况",
    "添加日志",
    "优化查询",
    "更新配置",
    "重构模块",
]

# 可能的文件类型列表
FILE_TYPES = [
    (".py", ["# 更新Python代码", "def function():", "class MyClass:", "import random", "# TODO: 实现这个功能"]),
    (".js", ["// JavaScript更新", "function update() {", "const newFeature = () => {", "// 修复这个问题"]),
    (".html", ["<!-- HTML更新 -->", "<div>", "<section>", "<p>内容更新</p>"]),
    (".css", ["/* CSS更新 */", ".new-class {", "margin: 0 auto;", "display: flex;"]),
    (".md", ["# 文档更新", "## 新部分", "* 列表项", "更新说明"]),
    (".json", ['"key": "value"', '"updated": true', '"version": "1.0.1"']),
    (".txt", ["更新文本", "添加描述", "修复文档"]),
]

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="GitHub活动模拟器 - 安全版")
    parser.add_argument("--days", type=int, default=180, help="要模拟的天数")
    parser.add_argument("--max-commits", type=int, default=5, help="每天的最大提交数")
    parser.add_argument("--method", type=str, choices=["temp-repo", "new-repo", "orphan-branch", "dry-run"], 
                        default="temp-repo", help="使用哪种方法进行模拟")
    parser.add_argument("--new-repo-name", type=str, default="FakeCommits", 
                        help="如果使用new-repo方法，指定新仓库的名称")
    parser.add_argument("--orphan-branch-name", type=str, default="FakeCommits", 
                        help="如果使用orphan-branch方法，指定孤立分支的名称")
    parser.add_argument("--push", action="store_true", help="自动推送到远程仓库")
    parser.add_argument("--backdate", action="store_true", help="创建过去日期的提交", default=True)
    parser.add_argument("--weekend-bias", action="store_true", help="在周末创建更多提交", default=True)
    parser.add_argument("--file-prefix", type=str, default="auto_", help="自动创建文件的前缀")
    parser.add_argument("--keep-temp", action="store_true", help="保留临时目录（仅适用于temp-repo方法）")
    parser.add_argument("--remote", type=str, default="origin", help="远程仓库名称")
    return parser.parse_args()

def create_or_update_file(repo_path, file_prefix):
    """创建或更新仓库中的文件"""
    # 随机选择文件类型和内容
    file_ext, content_options = random.choice(FILE_TYPES)
    
    # 生成文件名 (使用时间戳以确保唯一性)
    timestamp = int(time.time())
    file_name = f"{file_prefix}{timestamp}{file_ext}"
    file_path = os.path.join(repo_path, file_name)
    
    # 确保目录存在
    Path(repo_path).mkdir(parents=True, exist_ok=True)
    
    # 写入随机内容到文件
    with open(file_path, "w") as f:
        num_lines = random.randint(3, 10)
        for _ in range(num_lines):
            f.write(random.choice(content_options) + "\n")
    
    return file_name

def make_commit(repo_path, file_name, date=None):
    """创建Git提交"""
    # 添加文件到Git
    subprocess.run(["git", "add", file_name], cwd=repo_path, check=True)
    
    # 选择随机提交消息
    commit_message = random.choice(COMMIT_MESSAGES)
    
    # 构建提交命令
    commit_cmd = ["git", "commit", "-m", commit_message]
    
    # 如果提供了日期，则设置GIT_AUTHOR_DATE和GIT_COMMITTER_DATE环境变量
    env = os.environ.copy()
    if date:
        date_str = date.strftime("%Y-%m-%d %H:%M:%S")
        env["GIT_AUTHOR_DATE"] = date_str
        env["GIT_COMMITTER_DATE"] = date_str
    
    # 执行提交
    subprocess.run(commit_cmd, cwd=repo_path, env=env, check=True)
    
    return commit_message

def push_to_remote(repo_path, remote="origin", branch="master"):
    """推送更改到远程仓库"""
    try:
        subprocess.run(["git", "push", remote, branch], cwd=repo_path, check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"无法推送到远程仓库 {remote}/{branch}。请确保已设置远程仓库并有适当的权限。")
        return False

def init_repo(path):
    """初始化一个新的Git仓库"""
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True)
    
    # 创建初始提交
    readme_path = os.path.join(path, "README.md")
    with open(readme_path, "w") as f:
        f.write("# GitHub活动模拟器\n\n这是一个用于增加GitHub贡献图活跃度的仓库。这些提交是通过脚本自动生成的。\n")
    
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "初始提交"], cwd=path, check=True)

def setup_remote(repo_path, repo_name, remote="origin"):
    """设置远程仓库"""
    print(f"请在GitHub上创建一个名为 '{repo_name}' 的新仓库（推荐设为私有）")
    github_username = input("请输入你的GitHub用户名: ")
    
    remote_url = f"git@github.com:{github_username}/{repo_name}.git"
    
    try:
        # 添加远程仓库
        subprocess.run(["git", "remote", "add", remote, remote_url], cwd=repo_path, check=True)
        print(f"成功添加远程仓库: {remote_url}")
        return True
    except subprocess.CalledProcessError:
        print(f"无法添加远程仓库。请确保你有权限访问 {remote_url}")
        return False

def create_orphan_branch(repo_path, branch_name):
    """创建一个孤立的Git分支，没有任何历史记录"""
    try:
        # 创建并切换到孤立分支
        subprocess.run(["git", "checkout", "--orphan", branch_name], cwd=repo_path, check=True)
        
        # 清除工作区
        subprocess.run(["git", "rm", "-rf", "."], cwd=repo_path, check=True)
        
        # 创建初始提交
        readme_path = os.path.join(repo_path, "README.md")
        with open(readme_path, "w") as f:
            f.write(f"# 活动模拟分支\n\n这是一个用于增加GitHub贡献图活跃度的孤立分支。这个分支上的所有提交都是通过脚本自动生成的。\n")
        
        subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "初始提交 (孤立分支)"], cwd=repo_path, check=True)
        
        print(f"成功创建孤立分支: {branch_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"创建孤立分支时出错: {e}")
        return False

def simulate_activity(args):
    """根据选择的方法模拟GitHub活动"""
    method = args.method
    temp_dir = None
    
    try:
        if method == "temp-repo":
            # 创建临时目录
            temp_dir = tempfile.mkdtemp()
            print(f"创建临时仓库于: {temp_dir}")
            
            # 初始化Git仓库
            init_repo(temp_dir)
            
            if args.push:
                # 设置远程仓库
                if not setup_remote(temp_dir, args.new_repo_name):
                    print("未能设置远程仓库，将继续但不会推送。")
                    args.push = False
            
            working_dir = temp_dir
            branch = "master"
            
        elif method == "new-repo":
            # 在当前目录创建新的仓库目录
            repo_dir = os.path.join(os.getcwd(), args.new_repo_name)
            
            if os.path.exists(repo_dir):
                raise ValueError(f"目录已存在: {repo_dir}。请选择一个不同的仓库名称。")
            
            print(f"创建新仓库于: {repo_dir}")
            
            # 初始化Git仓库
            init_repo(repo_dir)
            
            if args.push:
                # 设置远程仓库
                if not setup_remote(repo_dir, args.new_repo_name):
                    print("未能设置远程仓库，将继续但不会推送。")
                    args.push = False
            
            working_dir = repo_dir
            branch = "master"
            
        elif method == "orphan-branch":
            # 在当前目录中检查是否为Git仓库
            if not os.path.isdir(os.path.join(os.getcwd(), ".git")):
                raise ValueError("当前目录不是Git仓库。请先初始化Git仓库或选择其他方法。")
            
            # 记住当前分支
            current_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                cwd=os.getcwd()
            ).decode().strip()
            
            # 创建孤立分支
            if not create_orphan_branch(os.getcwd(), args.orphan_branch_name):
                raise ValueError(f"无法创建孤立分支: {args.orphan_branch_name}")
            
            working_dir = os.getcwd()
            branch = args.orphan_branch_name
            
        elif method == "dry-run":
            # 不实际创建任何仓库或提交，只是模拟
            print("执行模拟运行 (dry run) - 不会创建任何实际的提交")
            working_dir = None
            branch = None
        
        # 执行模拟
        do_simulate_activity(args, working_dir, branch)
        
        # 如果使用orphan-branch方法，切回原来的分支
        if method == "orphan-branch":
            print(f"切换回原来的分支: {current_branch}")
            subprocess.run(["git", "checkout", current_branch], cwd=working_dir, check=True)
            
    finally:
        # 如果是临时目录且不需要保留，则删除
        if temp_dir and not args.keep_temp and method == "temp-repo":
            print(f"清理临时目录: {temp_dir}")
            shutil.rmtree(temp_dir)

def do_simulate_activity(args, repo_path, branch):
    """实际执行模拟活动的逻辑"""
    # 如果是dry run模式，不需要实际执行
    if args.method == "dry-run":
        simulate_dry_run(args)
        return
    
    # 获取当前日期
    today = datetime.datetime.now().date()
    
    # 计算起始日期
    if args.backdate:
        start_date = today - datetime.timedelta(days=args.days - 1)
    else:
        start_date = today
    
    total_commits = 0
    
    # 循环每一天
    for day_offset in range(args.days):
        current_date = start_date + datetime.timedelta(days=day_offset)
        
        # 确定这一天的提交次数
        if args.weekend_bias and current_date.weekday() >= 5:  # 周末 (5=周六, 6=周日)
            max_commits = args.max_commits
            min_commits = max(1, args.max_commits // 2)
        else:
            max_commits = args.max_commits
            min_commits = 0  # 工作日可能没有提交
        
        # 随机生成这一天的提交次数
        num_commits = random.randint(min_commits, max_commits)
        
        for i in range(num_commits):
            # 创建基准时间 (当天的随机时间)
            commit_hour = random.randint(9, 22)  # 早9点到晚10点
            commit_minute = random.randint(0, 59)
            commit_second = random.randint(0, 59)
            
            commit_date = datetime.datetime(
                current_date.year, 
                current_date.month, 
                current_date.day,
                commit_hour,
                commit_minute,
                commit_second
            )
            
            # 只有在模拟过去日期或当前日期早于现在时创建提交
            if args.backdate or commit_date <= datetime.datetime.now():
                # 创建或更新文件
                file_name = create_or_update_file(repo_path, args.file_prefix)
                
                # 创建提交
                commit_message = make_commit(
                    repo_path, 
                    file_name, 
                    date=commit_date if args.backdate else None
                )
                
                total_commits += 1
                
                date_str = commit_date.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{date_str}] 提交: {commit_message} - {file_name}")
                
                # 添加随机延迟，使过程看起来更自然
                time.sleep(random.uniform(0.1, 0.5))
    
    print(f"\n成功创建了 {total_commits} 个提交!")
    
    # 如果需要，推送到远程仓库
    if args.push:
        print(f"正在推送到远程仓库 {args.remote}/{branch}...")
        if push_to_remote(repo_path, args.remote, branch):
            print("成功推送到远程仓库")

def simulate_dry_run(args):
    """执行模拟运行，只打印将会创建的提交，不实际创建"""
    # 获取当前日期
    today = datetime.datetime.now().date()
    
    # 计算起始日期
    if args.backdate:
        start_date = today - datetime.timedelta(days=args.days - 1)
    else:
        start_date = today
    
    total_commits = 0
    
    print("\n模拟运行 - 以下是将会创建的提交:")
    print("=" * 60)
    
    # 循环每一天
    for day_offset in range(args.days):
        current_date = start_date + datetime.timedelta(days=day_offset)
        
        # 确定这一天的提交次数
        if args.weekend_bias and current_date.weekday() >= 5:  # 周末 (5=周六, 6=周日)
            max_commits = args.max_commits
            min_commits = max(1, args.max_commits // 2)
        else:
            max_commits = args.max_commits
            min_commits = 0  # 工作日可能没有提交
        
        # 随机生成这一天的提交次数
        num_commits = random.randint(min_commits, max_commits)
        
        if num_commits > 0:
            print(f"\n日期: {current_date.strftime('%Y-%m-%d')} ({['周一','周二','周三','周四','周五','周六','周日'][current_date.weekday()]})")
        
        for i in range(num_commits):
            # 创建基准时间 (当天的随机时间)
            commit_hour = random.randint(9, 22)
            commit_minute = random.randint(0, 59)
            
            commit_time = f"{commit_hour:02d}:{commit_minute:02d}"
            commit_message = random.choice(COMMIT_MESSAGES)
            file_ext, _ = random.choice(FILE_TYPES)
            
            print(f"  {commit_time} - {commit_message} (文件类型: {file_ext})")
            
            total_commits += 1
    
    print("\n" + "=" * 60)
    print(f"总计: 将创建 {total_commits} 个提交，横跨 {args.days} 天")
    print(f"平均每天提交数: {total_commits / args.days:.1f}")
    
    if args.push:
        print("注意: 如果实际执行，这些提交将被推送到远程仓库")

def print_help_and_examples():
    """打印帮助信息和使用示例"""
    print("\n📖 GitHub活动模拟器 - 使用指南")
    print("=" * 60)
    print("这个脚本提供了四种不同的方法来模拟GitHub活动，而不污染你的现有仓库:")
    print()
    print("1. 临时仓库 (temp-repo) - 默认")
    print("   在临时目录中创建一个新仓库，完成后自动删除")
    print("   示例: python github_activity.py --method temp-repo --days 30 --push")
    print()
    print("2. 新仓库 (new-repo)")
    print("   在指定目录中创建一个全新的仓库")
    print("   示例: python github_activity.py --method new-repo --new-repo-name activity-boost --days 60 --push")
    print()
    print("3. 孤立分支 (orphan-branch)")
    print("   在现有仓库中创建一个没有历史记录的新分支")
    print("   示例: python github_activity.py --method orphan-branch --orphan-branch-name activity-sim --days 90")
    print()
    print("4. 模拟运行 (dry-run)")
    print("   只显示将会创建什么，不实际创建任何提交")
    print("   示例: python github_activity.py --method dry-run --days 30 --max-commits 8")
    print()
    print("其他常用选项:")
    print("  --days N             - 模拟N天的活动 (默认: 180)")
    print("  --max-commits N      - 每天最多N次提交 (默认: 5)")
    print("  --backdate           - 创建过去日期的提交")
    print("  --weekend-bias       - 在周末创建更多提交")
    print("  --push               - 推送到远程仓库 (需要GitHub账户)")
    print("  --keep-temp          - 保留临时目录 (仅适用于temp-repo方法)")
    print("=" * 60)

if __name__ == "__main__":
    args = parse_arguments()
    
    # 打印标题
    print("\n🚀 GitHub活动模拟器 - 安全版")
    print(f"方法: {args.method}, 天数: {args.days}, 每天最多提交: {args.max_commits}")
    
    # 打印帮助和示例
    print_help_and_examples()
    
    # 确认是否继续
    confirmation = input("\n是否继续? (y/n): ").strip().lower()
    if confirmation != 'y':
        print("已取消。")
        exit(0)
    
    # 执行模拟
    simulate_activity(args)
