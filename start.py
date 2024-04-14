import os
import hashlib
import yaml
import subprocess
import json
import re
import logging
from bs4 import BeautifulSoup
from datetime import datetime, time, date
import PyRSS2Gen
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# 设置日志格式和级别
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 文件和目录路径
root_dir = Path('.')  
content_dir = Path('content')
output_dir = Path('post')
static_dir = Path('static')
template_file = static_dir / 'page.html'
hashes_json = Path('hashes.json')
index_html_path = Path('index.html')


# 从上次运行中获取文件哈希值
last_hashes = {}
if hashes_json.exists():
    try:
        with hashes_json.open('r') as f:
            last_hashes = json.load(f)
    except json.JSONDecodeError as e:
        logging.error("读取哈希值文件时出错：%s", e)
        last_hashes = {}

# 辅助函数
def file_hash(filepath: Path) -> str:
    """ 计算给定文件的哈希值 """
    sha256_hash = hashlib.sha256()
    with filepath.open('rb') as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def parse_front_matter(md_content: str) -> dict:
    """ 解析 Markdown 文件的前导内容（包含元数据） """
    split_content = md_content.split('---', 2)
    if len(split_content) != 3:
        raise ValueError("文件的前导内容无效")
    return yaml.safe_load(split_content[1])

def render_to_html(md_file_path: Path, html_output_path: Path, template_path: Path, description: str):
    """ 使用 Pandoc 和提供的模板将 Markdown 文件渲染成 HTML 文件 """
    try:
        subprocess.run([
            'pandoc',
            '--standalone',
            f'--template={template_path}',
            f'--metadata=description:\'{description}\'',
            '-o', html_output_path,
            md_file_path],
            check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"渲染Markdown到HTML失败: {e}")

def add_lazy_loading_to_images(html_file_path: Path):
    """ 在 HTML 文件中的所有图片标签后增加 `loading="lazy"` 属性 """
    with html_file_path.open('r', encoding='utf-8') as file:
        html_content = BeautifulSoup(file, 'html.parser')

    for img in html_content.find_all('img', attrs={'loading': None}):
        img['loading'] = 'lazy'

    with html_file_path.open('w', encoding='utf-8') as file:
        file.write(str(html_content.prettify()))

def static_files_changed(static_dir: Path, last_hashes: dict) -> bool:
    """ 检查 `static` 文件夹中的文件是否被修改 """
    changed = False
    for file_path in static_dir.rglob('*'):  # 使用 rglob('*') 以递归检查所有文件
        if file_path.is_file():
            new_hash = file_hash(file_path)
            old_hash = last_hashes.get(str(file_path))
            if old_hash is None or old_hash != new_hash:
                logging.info("静态文件发生改变：%s", file_path.name)
                last_hashes[str(file_path)] = new_hash
                changed = True
    return changed


def format_date(date_obj: date) -> str:
    """ 格式化日期对象为字符串 """
    return date_obj.strftime('%Y-%m-%d')

def sort_posts(post_data: list) -> list:
    """根据日期对文章数据进行排序，日期新的在前"""
    return sorted(post_data, key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d') if isinstance(x['date'], str) else x['date'], reverse=True)


# 用于更新首页的函数
def update_index(post_data: list, index_html_path: Path):
    try:
        with index_html_path.open('r', encoding='utf-8') as file:
            soup = BeautifulSoup(file.read(), 'html.parser')

        article_element = soup.find('article')
        ul_element = article_element.find('ul')
        if not ul_element:
            ul_element = soup.new_tag('ul')
            article_element.append(ul_element)
        else:
            # 清空现有的文章列表
            ul_element.clear()

        post_data = sort_posts(post_data)

        for post in post_data:
            # 创建新的 <li> 元素
            li = soup.new_tag('li')
            span_date = soup.new_tag('span')
            span_date.string = format_date(post['date']) if isinstance(post['date'], date) else post['date']
            li.append(span_date)
            
            # 修正链接格式，确保使用正斜杠('/')
            href_link = f"{output_dir.as_posix()}/{post['slug']}"
            a_title = soup.new_tag('a', href=href_link)
            a_title.string = post['title']
            li.append(a_title)
            
            # 直接添加到ul_element中
            ul_element.append(li)


        with index_html_path.open('w', encoding='utf-8') as file:
            file.write(str(soup.prettify()))

        logging.info("首页更新成功。")
    except Exception as e:
        logging.error("更新首页时出错：%s", e)
# 描述
def extract_description(md_content: str) -> str:
    """
    提取内容的第一句作为描述
    这里的逻辑假定您的Markdown文件在前导内容与正文之间有两个换行符。
    如果您的Markdown文件结构不同，请相应调整这个函数。
    """
    paragraphs = md_content.split('\n\n', 1)
    if len(paragraphs) <= 1:
        return ""
    first_paragraph = paragraphs[1].strip()
    first_paragraph = re.split(r'\.\s+|\n', first_paragraph)[0]
    return first_paragraph

# 生成RSS订阅源的函数
def generate_rss(post_data: list, root_dir: Path, base_url: str):
    rss_items = []
    
    for post in post_data:
        pub_date = datetime.strptime(post['date'], "%Y-%m-%d") if isinstance(post['date'], str) else datetime.combine(post['date'], time()) if isinstance(post['date'], date) else post['date']
        
        rss_items.append(PyRSS2Gen.RSSItem(
            title=post['title'],
            link=f"{base_url}/{output_dir}/{post['slug']}",
            description=post['description'],
            guid=PyRSS2Gen.Guid(f"{base_url}/{output_dir}/{post['slug']}"),
            pubDate=pub_date
        ))

    rss_feed = PyRSS2Gen.RSS2(
        title="涵有闲",
        link=base_url,
        description="想做就去做吧",
        lastBuildDate=datetime.now(),
        items=rss_items
    )

    # 使用utf-8编码写入RSS XML到文件
    rss_xml = rss_feed.to_xml(encoding="utf-8")

    with (root_dir / 'rss.xml').open('w', encoding='utf-8') as f:
        f.write(rss_xml)

# 主处理流程
def main():
    # 从上次运行中获取文件哈希值
    last_hashes = {}
    if hashes_json.exists():
        try:
            with hashes_json.open('r') as f:
                last_hashes = json.load(f)
        except json.JSONDecodeError as e:
            logging.error("读取哈希值文件时出错：%s", e)
            last_hashes = {}
    
    is_first_run = not hashes_json.exists() or os.stat(hashes_json).st_size == 0
    static_changed = static_files_changed(static_dir, last_hashes)
    post_data = []
    post_meta_changed = False
    need_update = False

    with ThreadPoolExecutor() as executor:
        futures = []
        existing_html_slugs = {html_file.stem for html_file in output_dir.glob('*.html')}

        for md_file_path in content_dir.glob('*.md'):
            try:
                with md_file_path.open('r', encoding='utf-8') as f:
                    md_content = f.read()
                front_matter = parse_front_matter(md_content)
            except (IOError, ValueError) as e:
                logging.error(f"Error processing file {md_file_path}: {e}")
                continue

            slug = front_matter.get('slug')
            title = front_matter.get('title', 'Untitled Post')
            date = front_matter.get('date')

            if not (slug and title and date):
                logging.error(f"Missing required front matter fields in {md_file_path}")
                continue

            description = extract_description(md_content)
            current_hash = file_hash(md_file_path)
            needs_render = static_changed or last_hashes.get(str(md_file_path)) != current_hash

            if needs_render:
                logging.info(f"Rendering {md_file_path.name}...")
                html_output_path = output_dir / f"{slug}.html"
                future = executor.submit(render_to_html, md_file_path, html_output_path, template_file, description)
                futures.append(future)
                need_update = True
                last_hashes[str(md_file_path)] = current_hash

            if slug in existing_html_slugs:
                existing_html_slugs.remove(slug)
                for post in post_data:
                    if post['slug'] == slug and (post['title'] != title or post['date'] != date or post['description'] != description):
                        post_meta_changed = True
                        break

            post_data.append({
                'date': date,
                'title': title,
                'slug': slug,
                'description': description
            })

        for future in futures:
            future.result()

        for html_output_path in output_dir.glob('*.html'):
            add_lazy_loading_to_images(html_output_path)

    for slug in existing_html_slugs:
        logging.info(f"Deleting post/{slug}.html...")
        (output_dir / f"{slug}.html").unlink()
        need_update = True

    with hashes_json.open('w') as f:
        json.dump(last_hashes, f)

    if need_update or post_meta_changed or is_first_run:
        post_data = sort_posts(post_data)  # 对文章数据进行排序
        update_index(post_data, index_html_path)
        generate_rss(post_data, root_dir, "https://hyx.ink")
        logging.info("首页和RSS feed已更新。")

if __name__ == "__main__":
    main()