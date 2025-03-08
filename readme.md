# InterestingTools

一个实用Python工具集合，帮助您自动化日常任务、提高工作效率，并解决各种实际问题。

## 📋 工具概览

这个仓库包含多个独立的Python工具，每个都设计用来解决特定问题：

1. **文件整理器** - 自动整理杂乱的文件夹，按类型、日期、大小等进行分类
2. **GitHub贡献模拟器** - 安全地模拟GitHub提交活动，让您的贡献图更加活跃
3. **PDF分析与提取工具** - 智能分析PDF文档，提取文本、表格、关键词和摘要
4. **网站变化监控器** - 自动监控网站内容变化并发送通知

## 🔧 安装

所有工具都需要Python 3.6或更高版本。克隆此仓库后，为每个工具安装相应的依赖：

```bash
# 克隆仓库
git clone https://github.com/William-Liwei/InterestingTools.git
cd InterestingTools
```

如果您只想使用特定工具，可以查看各工具的单独安装说明。

## 🛠️ 工具详情

### 1. 文件整理器 (auto-file-organizer.py)

自动整理杂乱的文件夹，将文件按类型、日期、名称或大小分类，并可以检测重复文件。

#### 特点：
- 多种整理模式：按文件类型、修改日期、文件名首字母、文件大小分类
- 查找并处理重复文件
- 支持递归处理子目录
- 预览模式可在执行前查看将进行的操作
- 自定义规则支持，通过正则表达式匹配文件
- 详细的文件夹分析报告

#### 使用方法：
```bash
# 基本使用（按文件类型整理当前目录）
python auto-file-organizer.py

# 按修改日期整理指定目录中的文件
python auto-file-organizer.py /path/to/directory --mode date

# 查找并整理重复文件
python auto-file-organizer.py --mode duplicate

# 预览将进行的操作（不实际移动文件）
python auto-file-organizer.py --dry-run

# 分析目录内容并生成报告
python auto-file-organizer.py --mode analyze
```

### 2. GitHub贡献模拟器 (github_activity.py)

安全地模拟GitHub提交活动，不污染您的实际项目代码仓库。让您的贡献图更加活跃。

#### 特点：
- 多种安全模式：临时仓库、新建仓库、孤立分支或仅预览
- 支持创建回溯日期的提交
- 周末提交偏好设置
- 随机且真实的提交信息和文件更改
- 自动推送到远程GitHub仓库选项

#### 使用方法：
```bash
# 在临时目录中创建模拟提交（会自动删除本地文件）
python github_activity.py --method temp-repo --days 90 --push

# 创建新的仓库用于模拟提交
python github_activity.py --method new-repo --new-repo-name FakeCommits --days 180

# 在现有仓库中创建一个孤立分支用于模拟提交
python github_activity.py --method orphan-branch --orphan-branch-name activity-sim

# 仅模拟运行，不创建实际提交
python github_activity.py --method dry-run --days 30 --max-commits 8
```

### 3. PDF分析与提取工具 (pdf-analyzer.py)

自动分析PDF文档，提取文本、表格和图片，生成关键词、摘要和可视化内容。

#### 特点：
- 提取文本、表格和图片（如果可用）
- 自动生成文档摘要和关键词
- 创建词云和页面内容分布图表
- 支持多种语言分析
- 表格以多种格式导出（CSV、Excel、JSON）
- 生成完整的分析报告

#### 使用方法：
```bash
# 分析PDF文档（默认提取所有内容）
python pdf-analyzer.py document.pdf

# 仅提取文本
python pdf-analyzer.py document.pdf --extract-mode text

# 分析特定页面范围
python pdf-analyzer.py document.pdf --pages 1-10,15,20-25

# 生成可视化图表和分析
python pdf-analyzer.py document.pdf --visualize

# 指定输出目录
python pdf-analyzer.py document.pdf --output /path/to/output
```

### 4. 网站变化监控器 (website-monitor.py)

自动监控网站内容变化并发送通知。支持电子邮件和桌面通知。

#### 特点：
- 监控多个网站的内容变化
- 使用CSS选择器筛选监控内容
- 忽略特定内容的正则表达式支持
- 通过电子邮件和桌面通知提醒
- 生成详细的差异报告（文本和HTML格式）
- 作为守护进程持续运行

#### 使用方法：
```bash
# 创建默认配置文件
python website-monitor.py --create-config

# 添加要监控的网站
python website-monitor.py --add-site

# 查看监控的所有网站
python website-monitor.py --list-sites

# 立即检查所有网站变化
python website-monitor.py --check-now

# 作为守护进程运行（持续监控）
python website-monitor.py --daemon

# 显示特定网站的内容变化
python website-monitor.py --diff "网站名称或URL"
```

## 📜 许可证

本项目采用MIT许可证。

## 🤝 贡献

欢迎贡献代码、报告问题或提出改进建议！请随时创建Issue或提交Pull Request。

## 🔮 未来计划

- 为所有工具添加图形用户界面
- 创建统一的安装和配置系统
- 添加更多实用工具
- 改进多语言支持

## ⚠️ 免责声明

这些工具仅供学习和个人使用。请负责任地使用GitHub贡献模拟器，避免违反任何服务条款。
