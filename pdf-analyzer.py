#!/usr/bin/env python3
"""
智能PDF分析与提取工具 - 自动分析、提取和整理PDF文档内容
"""

import os
import re
import json
import argparse
import tempfile
import shutil
from pathlib import Path
from collections import Counter, defaultdict
import datetime
import logging

try:
    import pdfplumber
    from tabulate import tabulate
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
    from nltk.probability import FreqDist
    from nltk.stem import PorterStemmer, WordNetLemmatizer
    import matplotlib.pyplot as plt
    from wordcloud import WordCloud
    import pandas as pd
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:
    print("缺少必要的依赖项，正在安装...")
    import subprocess
    subprocess.check_call([
        "pip", "install", 
        "pdfplumber", "tabulate", "nltk", "matplotlib", 
        "wordcloud", "pandas", "numpy", "scikit-learn"
    ])
    import pdfplumber
    from tabulate import tabulate
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
    from nltk.probability import FreqDist
    from nltk.stem import PorterStemmer, WordNetLemmatizer
    import matplotlib.pyplot as plt
    from wordcloud import WordCloud
    import pandas as pd
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('pdf_analyzer')

# 下载必要的NLTK数据
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet', quiet=True)

# 支持的语言和对应的停用词
SUPPORTED_LANGUAGES = {
    'english': 'en',
    'spanish': 'es',
    'french': 'fr',
    'german': 'de',
    'italian': 'it',
    'portuguese': 'pt',
    'chinese': 'zh',
    'japanese': 'ja',
    'russian': 'ru',
}

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="智能PDF分析与提取工具")
    
    parser.add_argument("pdf_file", type=str, help="要分析的PDF文件路径")
    
    parser.add_argument("--output", "-o", type=str, default="",
                        help="输出目录（默认：在PDF旁创建同名目录）")
    
    parser.add_argument("--extract-mode", "-e", type=str, 
                        choices=["text", "tables", "images", "all"], 
                        default="all", help="提取模式（默认：all）")
    
    parser.add_argument("--pages", "-p", type=str, default="all",
                        help="要处理的页面范围（例如：1-5,8,11-13 或 all）")
    
    parser.add_argument("--language", "-l", type=str, default="english",
                        choices=list(SUPPORTED_LANGUAGES.keys()),
                        help="文档的主要语言（用于文本分析）")
    
    parser.add_argument("--summary-length", "-s", type=int, default=5,
                        help="摘要中包含的句子数")
    
    parser.add_argument("--keywords", "-k", type=int, default=20,
                        help="要提取的关键词数量")
    
    parser.add_argument("--table-format", "-t", type=str, 
                        choices=["csv", "excel", "json", "all"], 
                        default="csv", help="表格输出格式")
    
    parser.add_argument("--ocr", action="store_true",
                        help="对扫描的PDF使用OCR（需要安装Tesseract）")
    
    parser.add_argument("--metadata", "-m", action="store_true",
                        help="提取PDF元数据")
    
    parser.add_argument("--visualize", "-v", action="store_true",
                        help="生成可视化（词云、页面分布等）")
    
    parser.add_argument("--clean", "-c", action="store_true",
                        help="清理提取的文本（移除多余空格、特殊字符等）")
    
    parser.add_argument("--detect-language", "-d", action="store_true",
                        help="尝试自动检测文档语言")
    
    parser.add_argument("--verbose", action="store_true",
                        help="显示详细日志")
    
    parser.add_argument("--no-progress", action="store_true",
                        help="不显示进度条")
    
    return parser.parse_args()

def validate_file(file_path):
    """验证文件是否存在且是PDF"""
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return False
    
    if not file_path.lower().endswith('.pdf'):
        logger.error(f"文件不是PDF: {file_path}")
        return False
    
    return True

def parse_page_range(page_range, max_pages):
    """解析页面范围字符串"""
    if page_range.lower() == 'all':
        return list(range(max_pages))
    
    pages = []
    ranges = page_range.split(',')
    
    for r in ranges:
        if '-' in r:
            start, end = map(int, r.split('-'))
            # 转换为0-索引
            start = max(0, start - 1)
            end = min(max_pages, end)
            pages.extend(range(start, end))
        else:
            page = int(r) - 1  # 转换为0-索引
            if 0 <= page < max_pages:
                pages.append(page)
    
    return sorted(list(set(pages)))

def create_output_directory(pdf_path, output_dir):
    """创建输出目录"""
    if not output_dir:
        # 使用PDF文件名作为目录名
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_dir = os.path.join(os.path.dirname(pdf_path), f"{pdf_name}_分析")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 创建子目录
    text_dir = os.path.join(output_dir, "文本")
    tables_dir = os.path.join(output_dir, "表格")
    images_dir = os.path.join(output_dir, "图片")
    analysis_dir = os.path.join(output_dir, "分析")
    
    os.makedirs(text_dir, exist_ok=True)
    os.makedirs(tables_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(analysis_dir, exist_ok=True)
    
    return {
        "root": output_dir,
        "text": text_dir,
        "tables": tables_dir,
        "images": images_dir,
        "analysis": analysis_dir
    }

def extract_text_from_pdf(pdf, pages, clean=False):
    """从PDF提取文本"""
    all_text = []
    page_texts = {}
    
    for i, page_num in enumerate(pages):
        logger.info(f"提取文本：第 {page_num+1} 页")
        
        try:
            page = pdf.pages[page_num]
            text = page.extract_text() or ""
            
            if clean:
                # 清理文本
                text = clean_text(text)
            
            all_text.append(text)
            page_texts[page_num] = text
            
        except Exception as e:
            logger.error(f"提取第 {page_num+1} 页文本时出错: {e}")
            page_texts[page_num] = ""
    
    return "\n\n".join(all_text), page_texts

def extract_tables_from_pdf(pdf, pages, output_dirs, table_format):
    """从PDF提取表格"""
    all_tables = []
    page_tables = defaultdict(list)
    
    for i, page_num in enumerate(pages):
        logger.info(f"提取表格：第 {page_num+1} 页")
        
        try:
            page = pdf.pages[page_num]
            tables = page.extract_tables()
            
            if tables:
                for t_idx, table in enumerate(tables):
                    # 过滤空行和空列
                    filtered_table = []
                    for row in table:
                        filtered_row = [cell for cell in row if cell is not None]
                        if filtered_row:
                            filtered_table.append(filtered_row)
                    
                    if filtered_table:
                        all_tables.append(filtered_table)
                        page_tables[page_num].append(filtered_table)
                        
                        # 保存表格
                        if "csv" in table_format or "all" in table_format:
                            save_table_as_csv(
                                filtered_table, 
                                os.path.join(output_dirs["tables"], f"表格_页面{page_num+1}_{t_idx+1}.csv")
                            )
                        
                        if "excel" in table_format or "all" in table_format:
                            save_table_as_excel(
                                filtered_table, 
                                os.path.join(output_dirs["tables"], f"表格_页面{page_num+1}_{t_idx+1}.xlsx")
                            )
                        
                        if "json" in table_format or "all" in table_format:
                            save_table_as_json(
                                filtered_table, 
                                os.path.join(output_dirs["tables"], f"表格_页面{page_num+1}_{t_idx+1}.json")
                            )
        
        except Exception as e:
            logger.error(f"提取第 {page_num+1} 页表格时出错: {e}")
    
    return all_tables, page_tables

def extract_images_from_pdf(pdf, pages, output_dirs):
    """从PDF提取图片"""
    page_images = defaultdict(list)
    total_images = 0
    
    for i, page_num in enumerate(pages):
        logger.info(f"提取图片：第 {page_num+1} 页")
        
        try:
            page = pdf.pages[page_num]
            
            # PDFPlumber不直接支持图像提取，我们使用替代方法
            # 这里使用PyMuPDF (fitz) 如果它可用
            if 'fitz' in globals() or 'fitz' in locals():
                import fitz
                pdf_fitz = fitz.open(pdf._stream.name)
                fitz_page = pdf_fitz[page_num]
                
                image_list = fitz_page.get_images(full=True)
                
                for img_idx, img_info in enumerate(image_list):
                    xref = img_info[0]
                    base_image = pdf_fitz.extract_image(xref)
                    image_data = base_image["image"]
                    
                    # 保存图片
                    image_path = os.path.join(output_dirs["images"], f"图片_页面{page_num+1}_{img_idx+1}.png")
                    with open(image_path, "wb") as img_file:
                        img_file.write(image_data)
                    
                    page_images[page_num].append(image_path)
                    total_images += 1
            
        except Exception as e:
            logger.error(f"提取第 {page_num+1} 页图片时出错: {e}")
    
    return page_images, total_images

def extract_pdf_metadata(pdf):
    """提取PDF元数据"""
    try:
        metadata = pdf.metadata
        return metadata
    except Exception as e:
        logger.error(f"提取元数据时出错: {e}")
        return {}

def clean_text(text):
    """清理文本，移除多余空格和特殊字符"""
    # 替换多个换行符为单个
    text = re.sub(r'\n+', '\n', text)
    
    # 替换多个空格为单个
    text = re.sub(r'\s+', ' ', text)
    
    # 移除非打印字符
    text = re.sub(r'[^\x20-\x7E\n\u4e00-\u9fff]', '', text)
    
    # 修复断行造成的单词分割
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    
    # 修复句子在换行处的中断
    text = re.sub(r'([.!?])\s*\n([A-Z])', r'\1 \2', text)
    
    return text.strip()

def detect_language(text):
    """检测文本语言"""
    try:
        from langdetect import detect
        return detect(text)
    except ImportError:
        logger.warning("未安装langdetect，无法自动检测语言")
        return None
    except Exception as e:
        logger.error(f"检测语言时出错: {e}")
        return None

def tokenize_text(text, language):
    """将文本分词"""
    if language in ['chinese', 'japanese']:
        # 对于中文和日文，我们逐字符分词
        return list(text)
    else:
        return word_tokenize(text)

def get_stopwords(language):
    """获取指定语言的停用词"""
    if language in stopwords.fileids():
        return set(stopwords.words(language))
    else:
        return set()

def process_tokens(tokens, language, remove_stopwords=True, stemming=False, lemmatization=True):
    """处理分词（移除停用词，词干提取等）"""
    # 移除标点和数字
    tokens = [token.lower() for token in tokens 
              if token.isalpha() or (language in ['chinese', 'japanese'] and token.strip())]
    
    # 移除停用词
    if remove_stopwords and language in stopwords.fileids():
        stop_words = get_stopwords(language)
        tokens = [token for token in tokens if token.lower() not in stop_words]
    
    # 对英语等语言进行词干提取或词形还原
    if language == 'english':
        if stemming:
            stemmer = PorterStemmer()
            tokens = [stemmer.stem(token) for token in tokens]
        elif lemmatization:
            lemmatizer = WordNetLemmatizer()
            tokens = [lemmatizer.lemmatize(token) for token in tokens]
    
    return tokens

def extract_keywords(text, language, n_keywords=20):
    """提取关键词"""
    if not text:
        return []
    
    # 分词
    tokens = tokenize_text(text, language)
    
    # 处理分词
    processed_tokens = process_tokens(tokens, language)
    
    # 使用TF-IDF提取关键词
    if len(processed_tokens) > 20:  # 只在文本足够长时使用TF-IDF
        try:
            vectorizer = TfidfVectorizer(max_features=n_keywords * 2)
            X = vectorizer.fit_transform([text])
            feature_names = vectorizer.get_feature_names_out()
            
            tfidf_scores = zip(feature_names, X.toarray()[0])
            sorted_keywords = sorted(tfidf_scores, key=lambda x: x[1], reverse=True)
            
            return [(word, score) for word, score in sorted_keywords[:n_keywords]]
        
        except Exception as e:
            logger.error(f"TF-IDF提取关键词出错: {e}")
    
    # 回退到频率分析
    fdist = FreqDist(processed_tokens)
    return fdist.most_common(n_keywords)

def extract_summary(text, language, n_sentences=5):
    """提取摘要（最重要的句子）"""
    if not text:
        return ""
    
    # 分割句子
    sentences = sent_tokenize(text)
    
    if len(sentences) <= n_sentences:
        return text
    
    # 计算每个句子的权重
    sentence_weights = {}
    
    # 从整个文本中提取关键词
    keywords = extract_keywords(text, language, n_keywords=30)
    keyword_dict = {word: score for word, score in keywords}
    
    for sentence in sentences:
        tokens = tokenize_text(sentence, language)
        processed_tokens = process_tokens(tokens, language)
        
        # 句子权重基于其包含的关键词
        weight = sum(keyword_dict.get(token, 0) for token in processed_tokens)
        
        # 句子长度也考虑进去（避免太短的句子）
        length_factor = min(1.0, len(processed_tokens) / 20.0)
        
        # 综合权重
        sentence_weights[sentence] = weight * length_factor
    
    # 根据权重选择最重要的句子
    important_sentences = sorted(sentence_weights.items(), key=lambda x: x[1], reverse=True)
    
    # 保持句子原有顺序
    summary_sentences = [s for s, _ in important_sentences[:n_sentences]]
    ordered_summary = [s for s in sentences if s in summary_sentences]
    
    return " ".join(ordered_summary)

def create_wordcloud(text, language, output_path):
    """创建词云"""
    if not text:
        return False
    
    try:
        # 分词和处理
        tokens = tokenize_text(text, language)
        processed_tokens = process_tokens(tokens, language)
        
        # 创建词频字典
        word_freq = FreqDist(processed_tokens)
        
        # 设置词云参数
        if language in ['chinese', 'japanese']:
            font_path = None
            # 尝试找到支持中文/日文的字体
            possible_fonts = [
                '/System/Library/Fonts/PingFang.ttc',  # macOS
                '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',  # Linux
                'C:/Windows/Fonts/simhei.ttf',  # Windows
                'C:/Windows/Fonts/msgothic.ttc'  # Windows (日文)
            ]
            for font in possible_fonts:
                if os.path.exists(font):
                    font_path = font
                    break
            
            wordcloud = WordCloud(
                font_path=font_path,
                width=800, height=400,
                background_color='white',
                max_words=100
            )
        else:
            wordcloud = WordCloud(
                width=800, height=400,
                background_color='white',
                max_words=100
            )
        
        wordcloud.generate_from_frequencies(word_freq)
        
        # 保存词云图片
        plt.figure(figsize=(10, 5))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return True
    
    except Exception as e:
        logger.error(f"创建词云时出错: {e}")
        return False

def create_page_distribution_chart(page_texts, output_path):
    """创建页面内容分布图表"""
    try:
        # 计算每页的字符数
        page_lengths = {page: len(text) for page, text in page_texts.items()}
        
        pages = sorted(page_lengths.keys())
        lengths = [page_lengths[page] for page in pages]
        
        # 页码从1开始显示
        x_labels = [str(page + 1) for page in pages]
        
        plt.figure(figsize=(12, 6))
        plt.bar(x_labels, lengths, color='skyblue')
        plt.xlabel('页码')
        plt.ylabel('字符数')
        plt.title('PDF页面内容分布')
        plt.xticks(rotation=90)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return True
    
    except Exception as e:
        logger.error(f"创建页面分布图表时出错: {e}")
        return False

def save_table_as_csv(table, output_path):
    """将表格保存为CSV文件"""
    try:
        df = pd.DataFrame(table)
        df.to_csv(output_path, index=False, header=False, encoding='utf-8-sig')
        return True
    except Exception as e:
        logger.error(f"保存表格为CSV时出错: {e}")
        return False

def save_table_as_excel(table, output_path):
    """将表格保存为Excel文件"""
    try:
        df = pd.DataFrame(table)
        df.to_excel(output_path, index=False, header=False)
        return True
    except Exception as e:
        logger.error(f"保存表格为Excel时出错: {e}")
        return False

def save_table_as_json(table, output_path):
    """将表格保存为JSON文件"""
    try:
        # 假设第一行为表头
        if len(table) > 1:
            headers = table[0]
            data = []
            for row in table[1:]:
                row_dict = {}
                for i, cell in enumerate(row):
                    if i < len(headers):
                        row_dict[headers[i]] = cell
                    else:
                        row_dict[f"列{i+1}"] = cell
                data.append(row_dict)
        else:
            # 没有表头，使用列号
            data = []
            for row in table:
                row_dict = {f"列{i+1}": cell for i, cell in enumerate(row)}
                data.append(row_dict)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        return True
    
    except Exception as e:
        logger.error(f"保存表格为JSON时出错: {e}")
        return False

def generate_report(pdf_info, output_path):
    """生成分析报告"""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# PDF分析报告\n\n")
            
            f.write(f"## 基本信息\n\n")
            f.write(f"- **文件名**: {pdf_info['filename']}\n")
            f.write(f"- **路径**: {pdf_info['filepath']}\n")
            f.write(f"- **页数**: {pdf_info['page_count']}\n")
            f.write(f"- **处理时间**: {pdf_info['timestamp']}\n\n")
            
            # 元数据
            if pdf_info.get('metadata'):
                f.write(f"## 元数据\n\n")
                for key, value in pdf_info['metadata'].items():
                    if value:
                        f.write(f"- **{key}**: {value}\n")
                f.write("\n")
            
            # 内容统计
            f.write(f"## 内容统计\n\n")
            f.write(f"- **总字符数**: {pdf_info['char_count']}\n")
            f.write(f"- **总单词数**: {pdf_info['word_count']}\n")
            f.write(f"- **总句子数**: {pdf_info['sentence_count']}\n")
            
            if pdf_info.get('tables_count', 0) > 0:
                f.write(f"- **表格数**: {pdf_info['tables_count']}\n")
            
            if pdf_info.get('images_count', 0) > 0:
                f.write(f"- **图片数**: {pdf_info['images_count']}\n")
            
            f.write("\n")
            
            # 关键词
            if pdf_info.get('keywords'):
                f.write(f"## 关键词\n\n")
                for keyword, score in pdf_info['keywords']:
                    f.write(f"- **{keyword}** ({score:.4f})\n")
                f.write("\n")
            
            # 摘要
            if pdf_info.get('summary'):
                f.write(f"## 摘要\n\n")
                f.write(f"{pdf_info['summary']}\n\n")
            
            # 可视化引用
            if pdf_info.get('visualizations'):
                f.write(f"## 可视化\n\n")
                for vis_name, vis_path in pdf_info['visualizations'].items():
                    rel_path = os.path.relpath(vis_path, os.path.dirname(output_path))
                    f.write(f"### {vis_name}\n\n")
                    f.write(f"![{vis_name}]({rel_path})\n\n")
        
        return True
    
    except Exception as e:
        logger.error(f"生成报告时出错: {e}")
        return False

def analyze_pdf(args):
    """分析PDF文件"""
    pdf_path = args.pdf_file
    
    # 验证文件
    if not validate_file(pdf_path):
        return
    
    logger.info(f"开始分析PDF: {pdf_path}")
    
    # 创建输出目录
    output_dirs = create_output_directory(pdf_path, args.output)
    logger.info(f"输出目录: {output_dirs['root']}")
    
    # 打开PDF
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # 基本信息
            page_count = len(pdf.pages)
            logger.info(f"PDF共有 {page_count} 页")
            
            # 解析页面范围
            pages = parse_page_range(args.pages, page_count)
            logger.info(f"将处理 {len(pages)} 页")
            
            # 提取元数据
            metadata = {}
            if args.metadata:
                metadata = extract_pdf_metadata(pdf)
                logger.info(f"已提取元数据")
            
            # 提取文本
            all_text = ""
            page_texts = {}
            if args.extract_mode in ["text", "all"]:
                all_text, page_texts = extract_text_from_pdf(pdf, pages, args.clean)
                
                # 保存整体文本
                text_file = os.path.join(output_dirs["text"], "完整文本.txt")
                with open(text_file, 'w', encoding='utf-8') as f:
                    f.write(all_text)
                
                # 保存每页文本
                for page_num, text in page_texts.items():
                    page_file = os.path.join(output_dirs["text"], f"页面{page_num+1}.txt")
                    with open(page_file, 'w', encoding='utf-8') as f:
                        f.write(text)
                
                logger.info(f"已提取并保存文本")
            
            # 检测语言
            language = args.language
            if args.detect_language and all_text:
                detected_code = detect_language(all_text)
                if detected_code:
                    for lang, code in SUPPORTED_LANGUAGES.items():
                        if code.startswith(detected_code):
                            language = lang
                            logger.info(f"检测到文档语言: {language}")
                            break
            
            # 提取表格
            all_tables = []
            page_tables = {}
            if args.extract_mode in ["tables", "all"]:
                all_tables, page_tables = extract_tables_from_pdf(pdf, pages, output_dirs, args.table_format)
                logger.info(f"已提取并保存 {len(all_tables)} 个表格")
            
            # 提取图片
            page_images = {}
            total_images = 0
            if args.extract_mode in ["images", "all"]:
                try:
                    import fitz
                    page_images, total_images = extract_images_from_pdf(pdf, pages, output_dirs)
                    logger.info(f"已提取并保存 {total_images} 张图片")
                except ImportError:
                    logger.warning("未安装PyMuPDF(fitz)，无法提取图片")
            
            # 文本分析（如果有文本）
            text_stats = {
                "char_count": len(all_text),
                "word_count": len(all_text.split()),
                "sentence_count": len(sent_tokenize(all_text)) if all_text else 0
            }
            
            # 提取关键词
            keywords = []
            if all_text:
                keywords = extract_keywords(all_text, language, args.keywords)
                
                # 保存关键词
                keyword_file = os.path.join(output_dirs["analysis"], "关键词.txt")
                with open(keyword_file, 'w', encoding='utf-8') as f:
                    for word, score in keywords:
                        f.write(f"{word}: {score}\n")
                
                logger.info(f"已提取并保存关键词")
            
            # 提取摘要
            summary = ""
            if all_text:
                summary = extract_summary(all_text, language, args.summary_length)
                
                # 保存摘要
                summary_file = os.path.join(output_dirs["analysis"], "摘要.txt")
                with open(summary_file, 'w', encoding='utf-8') as f:
                    f.write(summary)
                
                logger.info(f"已生成并保存摘要")
            
            # 可视化
            visualizations = {}
            if args.visualize and all_text:
                # 词云
                wordcloud_path = os.path.join(output_dirs["analysis"], "词云.png")
                if create_wordcloud(all_text, language, wordcloud_path):
                    visualizations["词云"] = wordcloud_path
                    logger.info(f"已生成词云")
                
                # 页面分布图
                if page_texts:
                    distribution_path = os.path.join(output_dirs["analysis"], "页面分布.png")
                    if create_page_distribution_chart(page_texts, distribution_path):
                        visualizations["页面分布"] = distribution_path
                        logger.info(f"已生成页面分布图")
            
            # 汇总信息
            pdf_info = {
                "filename": os.path.basename(pdf_path),
                "filepath": pdf_path,
                "page_count": page_count,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "metadata": metadata,
                "char_count": text_stats["char_count"],
                "word_count": text_stats["word_count"],
                "sentence_count": text_stats["sentence_count"],
                "tables_count": len(all_tables),
                "images_count": total_images,
                "keywords": keywords,
                "summary": summary,
                "visualizations": visualizations
            }
            
            # 生成报告
            report_path = os.path.join(output_dirs["root"], "分析报告.md")
            if generate_report(pdf_info, report_path):
                logger.info(f"已生成分析报告: {report_path}")
            
            # 保存元数据
            if metadata:
                meta_path = os.path.join(output_dirs["analysis"], "元数据.json")
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=4)
            
            # 完成
            logger.info(f"PDF分析完成！所有结果已保存到: {output_dirs['root']}")
    
    except Exception as e:
        logger.error(f"分析PDF时出错: {e}")

def main():
    """主函数"""
    args = parse_arguments()
    
    # 设置日志级别
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # 分析PDF
    analyze_pdf(args)

if __name__ == "__main__":
    main()
