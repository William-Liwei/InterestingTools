#!/usr/bin/env python3
"""
网站变化监控器 - 自动监控网站内容变化并发送通知
"""

import os
import re
import time
import json
import hashlib
import argparse
import datetime
import difflib
import smtplib
import requests
import logging
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('website_monitor')

# 默认配置
DEFAULT_CONFIG = {
    "check_interval": 3600,  # 检查间隔（秒）
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
    "timeout": 30,
    "retry_count": 3,
    "retry_delay": 5,
    "data_dir": "monitor_data",
    "notification": {
        "email": {
            "enabled": False,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "",
            "password": "",
            "from_addr": "",
            "to_addr": []
        },
        "desktop": {
            "enabled": True
        }
    },
    "sites": [
        {
            "name": "示例网站",
            "url": "https://example.com",
            "selector": "body",  # CSS选择器，用于筛选要监控的内容
            "ignore_patterns": [],  # 忽略内容的正则表达式
            "check_interval": None,  # 特定于此站点的检查间隔（覆盖全局设置）
            "active": True
        }
    ]
}

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="网站变化监控器")
    
    parser.add_argument("--config", type=str, default="config.json",
                      help="配置文件路径 (默认: config.json)")
    
    parser.add_argument("--create-config", action="store_true",
                      help="创建默认配置文件")
    
    parser.add_argument("--add-site", action="store_true",
                      help="添加新网站到监控列表")
    
    parser.add_argument("--list-sites", action="store_true",
                      help="列出所有监控的网站")
    
    parser.add_argument("--check-now", action="store_true",
                      help="立即检查所有网站")
    
    parser.add_argument("--reset", type=str, default="",
                      help="重置特定网站的基准内容（使用站点名称或URL）")
    
    parser.add_argument("--diff", type=str, default="",
                      help="显示特定网站的内容变化（使用站点名称或URL）")
    
    parser.add_argument("--test-notification", action="store_true",
                      help="测试通知配置")
    
    parser.add_argument("--daemon", action="store_true",
                      help="作为守护进程运行（持续监控）")
    
    parser.add_argument("--verbose", action="store_true",
                      help="显示详细日志")
    
    return parser.parse_args()

def create_default_config(config_path):
    """创建默认配置文件"""
    if os.path.exists(config_path):
        confirm = input(f"配置文件 '{config_path}' 已存在。覆盖它? (y/n): ")
        if confirm.lower() != 'y':
            return False
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=4)
    
    logger.info(f"已创建默认配置文件: {config_path}")
    return True

def load_config(config_path):
    """加载配置文件"""
    if not os.path.exists(config_path):
        logger.error(f"配置文件 '{config_path}' 不存在。使用 --create-config 创建一个。")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 确保配置文件包含所有必需的部分
        for key, value in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
        
        return config
    
    except Exception as e:
        logger.error(f"加载配置文件时出错: {e}")
        return None

def add_site_to_config(config_path, config):
    """添加新网站到配置文件"""
    print("\n添加新网站到监控列表")
    print("-" * 50)
    
    name = input("网站名称: ")
    url = input("网站URL: ")
    
    # 验证URL
    try:
        parsed_url = urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            logger.error("无效的URL。请包含协议（如 http:// 或 https://）")
            return False
    except:
        logger.error("无效的URL格式。")
        return False
    
    selector = input("CSS选择器 (用于筛选内容，例如 '#content'，或者留空以使用整个页面): ")
    if not selector:
        selector = "body"
    
    ignore_patterns_input = input("忽略模式 (正则表达式，使用逗号分隔，或留空): ")
    ignore_patterns = [p.strip() for p in ignore_patterns_input.split(',')] if ignore_patterns_input else []
    
    interval_input = input(f"检查间隔（秒，留空使用全局设置 {config['check_interval']}）: ")
    check_interval = int(interval_input) if interval_input else None
    
    # 创建新网站配置
    new_site = {
        "name": name,
        "url": url,
        "selector": selector,
        "ignore_patterns": ignore_patterns,
        "check_interval": check_interval,
        "active": True
    }
    
    # 添加到配置
    config['sites'].append(new_site)
    
    # 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    
    logger.info(f"已添加网站 '{name}' 到监控列表")
    return True

def list_monitored_sites(config):
    """列出所有监控的网站"""
    sites = config.get('sites', [])
    
    if not sites:
        print("监控列表为空。使用 --add-site 添加网站。")
        return
    
    print("\n监控的网站:")
    print("-" * 70)
    print(f"{'名称':<20} {'URL':<30} {'状态':<10} {'检查间隔':<15}")
    print("-" * 70)
    
    for i, site in enumerate(sites):
        status = "活跃" if site.get('active', True) else "已禁用"
        interval = site.get('check_interval', config['check_interval'])
        interval_str = str(datetime.timedelta(seconds=interval))
        
        print(f"{site['name']:<20} {site['url'][:30]:<30} {status:<10} {interval_str:<15}")
    
    print("-" * 70)

def get_site_data_path(config, site):
    """获取网站数据存储路径"""
    data_dir = Path(config['data_dir'])
    data_dir.mkdir(exist_ok=True)
    
    # 使用网站URL的哈希作为目录名，避免特殊字符问题
    site_hash = hashlib.md5(site['url'].encode()).hexdigest()
    site_dir = data_dir / site_hash
    site_dir.mkdir(exist_ok=True)
    
    return site_dir

def fetch_website_content(url, config):
    """获取网站内容"""
    headers = {
        'User-Agent': config['user_agent'],
    }
    
    for attempt in range(config['retry_count']):
        try:
            response = requests.get(
                url, 
                headers=headers, 
                timeout=config['timeout']
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            if attempt < config['retry_count'] - 1:
                logger.warning(f"获取 {url} 失败: {e}。重试中...")
                time.sleep(config['retry_delay'])
            else:
                logger.error(f"获取 {url} 失败: {e}")
                return None

def extract_content(html, selector, ignore_patterns):
    """提取并清理网站内容"""
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # 使用选择器提取内容
        if selector:
            elements = soup.select(selector)
            if not elements:
                logger.warning(f"选择器 '{selector}' 未匹配任何内容")
                content = str(soup)
            else:
                content = ''.join(str(element) for element in elements)
        else:
            content = str(soup)
        
        # 应用忽略模式
        for pattern in ignore_patterns:
            try:
                content = re.sub(pattern, '', content)
            except re.error as e:
                logger.error(f"无效的正则表达式 '{pattern}': {e}")
        
        # 净化HTML
        text_soup = BeautifulSoup(content, 'html.parser')
        
        # 移除脚本和样式元素
        for script in text_soup(['script', 'style']):
            script.decompose()
        
        # 移除注释
        for comment in text_soup.findAll(text=lambda text: isinstance(text, str) and '<!--' in text):
            comment.extract()
        
        # 获取文本内容
        clean_content = text_soup.get_text()
        
        # 规范化空白
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        
        return clean_content
    
    except Exception as e:
        logger.error(f"解析内容时出错: {e}")
        return html

def save_content(content, file_path):
    """保存内容到文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"保存内容到 {file_path} 时出错: {e}")
        return False

def load_content(file_path):
    """从文件加载内容"""
    try:
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"从 {file_path} 加载内容时出错: {e}")
        return None

def compute_diff(old_content, new_content):
    """计算两个内容之间的差异"""
    if not old_content or not new_content:
        return None
    
    differ = difflib.Differ()
    diff = list(differ.compare(old_content.splitlines(), new_content.splitlines()))
    
    # 过滤只包含相同内容的行
    changes = [line for line in diff if line.startswith('+ ') or line.startswith('- ')]
    
    return '\n'.join(changes) if changes else None

def format_diff_html(old_content, new_content, site_name, url):
    """创建HTML格式的差异报告"""
    if not old_content or not new_content:
        return f"<p>无法为 {site_name} 创建差异报告</p>"
    
    # 创建HTML差异
    d = difflib.HtmlDiff()
    html_diff = d.make_file(
        old_content.splitlines(), 
        new_content.splitlines(),
        fromdesc=f"先前版本",
        todesc=f"当前版本"
    )
    
    # 改进HTML输出，使其更现代化、响应式
    html_diff = html_diff.replace(
        '</head>',
        '''
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; }
            .header { background: #f4f4f4; padding: 15px; margin-bottom: 20px; border-bottom: 1px solid #ddd; }
            .diff-table { width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
            .diff-table td { word-wrap: break-word; padding: 5px; border: 1px solid #ddd; }
            .diff-table .diff_header { width: 40px; text-align: center; background: #f8f8f8; }
            .diff-table .diff_next { display: none; }
            .diff-table .diff_add { background-color: #e6ffed; }
            .diff-table .diff_chg { background-color: #fff5b1; }
            .diff-table .diff_sub { background-color: #ffdce0; }
            @media (max-width: 768px) {
                .diff-table { font-size: 12px; }
                .diff-table td { padding: 3px; }
            }
        </style>
        </head>
        '''
    )
    
    # 添加站点信息到HTML头部
    html_diff = html_diff.replace(
        '<body>',
        f'''<body>
        <div class="header">
            <h2>{site_name}</h2>
            <p><a href="{url}" target="_blank">{url}</a></p>
            <p>变化检测时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        '''
    )
    
    return html_diff

def send_email_notification(site, diff, config):
    """发送邮件通知"""
    email_config = config['notification']['email']
    
    if not email_config.get('enabled', False):
        logger.info("邮件通知已禁用")
        return False
    
    # 验证必要的邮件配置
    required_fields = ['smtp_server', 'smtp_port', 'username', 'password', 'from_addr']
    for field in required_fields:
        if not email_config.get(field):
            logger.error(f"邮件配置缺少必要字段: {field}")
            return False
    
    if not email_config.get('to_addr'):
        logger.error("邮件配置缺少收件人地址")
        return False
    
    try:
        # 创建复合邮件
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"网站变化通知: {site['name']}"
        msg['From'] = email_config['from_addr']
        msg['To'] = ', '.join(email_config['to_addr'])
        
        # 添加文本部分
        text_content = f"""
检测到网站 {site['name']} ({site['url']}) 的内容发生变化。

变化摘要:
{diff[:500]}...

此邮件由网站变化监控器自动发送。
        """
        text_part = MIMEText(text_content, 'plain')
        msg.attach(text_part)
        
        # 连接SMTP服务器并发送邮件
        server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
        server.starttls()
        server.login(email_config['username'], email_config['password'])
        server.send_message(msg)
        server.quit()
        
        logger.info(f"已发送邮件通知到 {', '.join(email_config['to_addr'])}")
        return True
    
    except Exception as e:
        logger.error(f"发送邮件通知时出错: {e}")
        return False

def send_desktop_notification(site, diff):
    """发送桌面通知"""
    try:
        # 尝试导入平台相关的通知模块
        title = f"网站变化: {site['name']}"
        message = f"检测到网站 {site['url']} 的内容发生变化。"
        
        # 根据操作系统选择通知方法
        if os.name == 'posix':  # Linux/Unix
            try:
                import notify2
                notify2.init("网站变化监控器")
                notification = notify2.Notification(title, message)
                notification.show()
                return True
            except ImportError:
                os.system(f"notify-send '{title}' '{message}'")
                return True
        
        elif os.name == 'nt':  # Windows
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(title, message, duration=10)
                return True
            except ImportError:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, message, title, 0)
                return True
        
        elif sys.platform == 'darwin':  # macOS
            os.system(f"""osascript -e 'display notification "{message}" with title "{title}"'""")
            return True
        
        return False
    
    except Exception as e:
        logger.error(f"发送桌面通知时出错: {e}")
        return False

def send_notification(site, diff, config):
    """发送通知（电子邮件和/或桌面通知）"""
    notification_sent = False
    
    # 电子邮件通知
    if config['notification']['email'].get('enabled', False):
        if send_email_notification(site, diff, config):
            notification_sent = True
    
    # 桌面通知
    if config['notification']['desktop'].get('enabled', False):
        if send_desktop_notification(site, diff):
            notification_sent = True
    
    return notification_sent

def test_notification(config):
    """测试通知配置"""
    print("\n测试通知配置")
    print("-" * 50)
    
    test_site = {
        "name": "测试网站",
        "url": "https://example.com"
    }
    
    test_diff = "这是一个测试通知，用于验证通知配置是否正常工作。"
    
    # 测试电子邮件通知
    if config['notification']['email'].get('enabled', False):
        print("测试电子邮件通知...")
        if send_email_notification(test_site, test_diff, config):
            print("✅ 电子邮件通知已成功发送")
        else:
            print("❌ 电子邮件通知发送失败")
    else:
        print("ℹ️ 电子邮件通知已禁用")
    
    # 测试桌面通知
    if config['notification']['desktop'].get('enabled', False):
        print("测试桌面通知...")
        if send_desktop_notification(test_site, test_diff):
            print("✅ 桌面通知已成功发送")
        else:
            print("❌ 桌面通知发送失败")
    else:
        print("ℹ️ 桌面通知已禁用")

def check_website_changes(site, config, force_update=False):
    """检查网站变化"""
    logger.info(f"检查网站: {site['name']} ({site['url']})")
    
    # 获取网站数据路径
    site_dir = get_site_data_path(config, site)
    
    # 内容文件路径
    content_file = site_dir / "content.txt"
    html_file = site_dir / "raw.html"
    diff_file = site_dir / "diff.txt"
    html_diff_file = site_dir / "diff.html"
    last_check_file = site_dir / "last_check.json"
    
    # 获取当前网站内容
    html_content = fetch_website_content(site['url'], config)
    
    if not html_content:
        logger.error(f"无法获取 {site['name']} 的内容")
        return False
    
    # 保存原始HTML
    save_content(html_content, html_file)
    
    # 提取和清理内容
    extracted_content = extract_content(
        html_content, 
        site.get('selector', 'body'),
        site.get('ignore_patterns', [])
    )
    
    # 加载以前的内容
    previous_content = load_content(content_file)
    
    # 如果是第一次检查或强制更新，保存当前内容作为基准
    if not previous_content or force_update:
        logger.info(f"为 {site['name']} 创建新的基准内容")
        save_content(extracted_content, content_file)
        
        # 更新最后检查时间
        check_info = {
            "timestamp": time.time(),
            "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(last_check_file, 'w', encoding='utf-8') as f:
            json.dump(check_info, f, ensure_ascii=False, indent=4)
        
        return False
    
    # 计算差异
    diff = compute_diff(previous_content, extracted_content)
    
    # 更新最后检查时间
    check_info = {
        "timestamp": time.time(),
        "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(last_check_file, 'w', encoding='utf-8') as f:
        json.dump(check_info, f, ensure_ascii=False, indent=4)
    
    # 如果有变化
    if diff:
        logger.info(f"检测到 {site['name']} 的内容变化")
        
        # 保存差异
        save_content(diff, diff_file)
        
        # 创建HTML差异报告
        html_diff = format_diff_html(previous_content, extracted_content, site['name'], site['url'])
        save_content(html_diff, html_diff_file)
        
        # 更新当前内容
        save_content(extracted_content, content_file)
        
        # 发送通知
        send_notification(site, diff, config)
        
        return True
    else:
        logger.info(f"未检测到 {site['name']} 的内容变化")
        return False

def find_site_by_name_or_url(sites, name_or_url):
    """通过名称或URL查找网站"""
    for site in sites:
        if site['name'].lower() == name_or_url.lower() or site['url'].lower() == name_or_url.lower():
            return site
    return None

def display_diff(site, config):
    """显示网站的内容变化"""
    site_dir = get_site_data_path(config, site)
    diff_file = site_dir / "diff.txt"
    html_diff_file = site_dir / "diff.html"
    
    if not os.path.exists(diff_file):
        print(f"未找到 {site['name']} 的差异记录")
        return
    
    print(f"\n{site['name']} 的内容变化:")
    print("-" * 50)
    
    with open(diff_file, 'r', encoding='utf-8') as f:
        diff_content = f.read()
    
    print(diff_content)
    print("-" * 50)
    
    if os.path.exists(html_diff_file):
        print(f"HTML差异报告已保存到: {html_diff_file}")
        
        # 尝试在浏览器中打开HTML差异报告
        try:
            import webbrowser
            webbrowser.open(f"file://{os.path.abspath(html_diff_file)}")
        except:
            pass

def check_sites(config, reset_site=None):
    """检查所有网站的变化"""
    sites = config.get('sites', [])
    
    if not sites:
        logger.warning("监控列表为空。使用 --add-site 添加网站。")
        return
    
    # 如果指定了重置特定网站，仅处理该网站
    if reset_site:
        site = find_site_by_name_or_url(sites, reset_site)
        if site:
            logger.info(f"重置 {site['name']} 的基准内容")
            check_website_changes(site, config, force_update=True)
        else:
            logger.error(f"未找到网站: {reset_site}")
        return
    
    changes_detected = False
    
    for site in sites:
        if not site.get('active', True):
            logger.info(f"跳过已禁用的网站: {site['name']}")
            continue
        
        if check_website_changes(site, config):
            changes_detected = True
    
    return changes_detected

def run_daemon(config, args):
    """作为守护进程运行"""
    logger.info("启动网站变化监控守护进程")
    
    sites = config.get('sites', [])
    if not sites:
        logger.error("监控列表为空。使用 --add-site 添加网站。")
        return
    
    try:
        while True:
            # 记录当前时间
            now = time.time()
            
            for site in sites:
                if not site.get('active', True):
                    continue
                
                # 获取站点的最后检查时间
                site_dir = get_site_data_path(config, site)
                last_check_file = site_dir / "last_check.json"
                
                last_check_time = 0
                if os.path.exists(last_check_file):
                    try:
                        with open(last_check_file, 'r', encoding='utf-8') as f:
                            last_check_info = json.load(f)
                            last_check_time = last_check_info.get('timestamp', 0)
                    except:
                        last_check_time = 0
                
                # 确定检查间隔（优先使用站点特定的间隔）
                check_interval = site.get('check_interval') or config['check_interval']
                
                # 如果超过了检查间隔，检查此网站
                if now - last_check_time >= check_interval:
                    check_website_changes(site, config)
            
            # 休眠一段时间
            time.sleep(60)  # 每分钟检查一次是否有网站需要监控
    
    except KeyboardInterrupt:
        logger.info("监控器已停止")

def main():
    """主函数"""
    args = parse_arguments()
    
    # 设置日志级别
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # 创建默认配置
    if args.create_config:
        if create_default_config(args.config):
            print(f"请编辑 {args.config} 以配置您的监控设置")
        return
    
    # 加载配置
    config = load_config(args.config)
    if not config:
        return
    
    # 添加网站
    if args.add_site:
        add_site_to_config(args.config, config)
        return
    
    # 列出网站
    if args.list_sites:
        list_monitored_sites(config)
        return
    
    # 测试通知
    if args.test_notification:
        test_notification(config)
        return
    
    # 显示特定网站的差异
    if args.diff:
        site = find_site_by_name_or_url(config['sites'], args.diff)
        if site:
            display_diff(site, config)
        else:
            logger.error(f"未找到网站: {args.diff}")
        return
    
    # 检查网站变化
    if args.check_now:
        check_sites(config)
        return
    
    # 重置特定网站的基准内容
    if args.reset:
        check_sites(config, reset_site=args.reset)
        return
    
    # 作为守护进程运行
    if args.daemon:
        run_daemon(config, args)
        return
    
    # 如果没有指定任何操作，显示帮助
    list_monitored_sites(config)
    print("\n使用 --help 查看所有可用选项")

if __name__ == "__main__":
    main()
