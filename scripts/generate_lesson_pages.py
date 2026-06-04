#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为每课预渲染独立的、可被搜索引擎收录的静态 HTML（SEO L3）。

数据源：
  - static/data.json    各册课程清单 {"1":[{title,filename},...], ...}
  - NCE{n}/{filename}.lrc 每课全文（[时间]英文|中文，元数据行 [al|ar|ti|by:...]）

产物（提交进仓库；edge / Docker 直接发布）：
  - NCE{n}/{slug}.html   每课静态页（正文 + SEO + JSON-LD + 点读入口 + 上下课内链）
  - NCE{n}/index.html    各册课文目录页（内链枢纽）
  - sitemap.xml          全量站点地图（首页 + 关于 + 册目录 + 所有课页）

课程内容变动后重跑：  python3 scripts/generate_lesson_pages.py
"""
import os
import re
import json
import html

SITE = 'https://nce.luzhenhua.cn'
DATA_FILE = 'static/data.json'
SITEMAP_FILE = 'sitemap.xml'

TIME_RE = re.compile(r'\[\d+:\d+(?:\.\d+)?\]')
META_RE = re.compile(r'^\[(al|ar|ti|by):.+\]$', re.IGNORECASE)


def parse_lrc(path):
    """解析 .lrc，返回内容句子 [{'en','cn'}]（剔除时间戳与 al/ar/ti/by 元数据行）。"""
    items = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except OSError:
        return items
    for line in lines:
        line = line.strip()
        if not line or META_RE.match(line):
            continue
        clean = TIME_RE.sub('', line).strip()
        if not clean:
            continue
        en, cn = clean, ''
        if '|' in clean:
            parts = clean.split('|', 1)
            en, cn = parts[0].strip(), parts[1].strip()
        if en or cn:
            items.append({'en': en, 'cn': cn})
    return items


def slugify(name):
    """001&002－Excuse Me -> 001-002-excuse-me；非 a-z0-9 一律转连字符。"""
    s = name.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s


def lesson_no(filename):
    """从 filename 开头的数字提取课号显示：001&002 -> '1-2'，015 -> '15'。"""
    head = re.match(r'^[\d&]+', filename)
    if not head:
        return ''
    nums = re.findall(r'\d+', head.group(0))
    return '-'.join(str(int(x)) for x in nums)


def make_desc(book_n, title, items):
    sample = ' '.join(it['en'] for it in items if it['en'])
    sample = re.sub(r'\s+', ' ', sample).strip()
    desc = f"新概念英语第{book_n}册《{title}》课文原文与中英文对照翻译。{sample}"
    return desc[:155]


CSS = """:root{color-scheme:light dark}*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.7;color:#1a1a1a;background:#fff}
@media(prefers-color-scheme:dark){body{color:#e5e5e5;background:#0f0f12}}
.wrap{max-width:760px;margin:0 auto;padding:24px 20px 64px}
.crumb{font-size:13px;color:#888;margin-bottom:10px}.crumb a{color:#6366f1;text-decoration:none}
h1{font-size:26px;margin:.2em 0 .1em}.meta{color:#888;font-size:14px;margin:0 0 18px}
.cta{display:inline-block;background:#6366f1;color:#fff;text-decoration:none;padding:10px 18px;border-radius:10px;font-weight:600;margin-bottom:24px}
.sentences{list-style:none;padding:0;margin:0}.sentences li{padding:11px 0;border-bottom:1px solid rgba(128,128,128,.15)}
.en{display:block;font-size:17px}.cn{display:block;color:#888;font-size:15px;margin-top:2px}
.pager{display:flex;justify-content:space-between;gap:12px;margin-top:32px;flex-wrap:wrap;font-size:15px}
.pager a{color:#6366f1;text-decoration:none}
.toc{list-style:none;padding:0;margin:0}.toc li{padding:9px 0;border-bottom:1px solid rgba(128,128,128,.15)}
.toc a{color:#6366f1;text-decoration:none}.toc .no{color:#aaa;font-size:13px;margin-right:8px}"""


def esc(s):
    return html.escape(s, quote=True)


def render_lesson(book, book_n, title, filename, slug, items, prev_item, next_item):
    url = f"{SITE}/{book}/{slug}.html"
    desc = make_desc(book_n, title, items)
    no = lesson_no(filename)
    # 点读链接指向交互版（hash 路由，与 index.html/​search.js 一致）；课页在 NCE{n}/ 下，故 ../lesson.html
    play_href = esc(f"../lesson.html#{book}/{filename}")

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "LearningResource",
        "name": title,
        "description": desc,
        "inLanguage": ["en", "zh-CN"],
        "learningResourceType": "课文",
        "educationalLevel": f"新概念英语第{book_n}册",
        "isPartOf": {"@type": "Course", "name": f"新概念英语第{book_n}册", "url": f"{SITE}/{book}/"},
        "url": url
    }, ensure_ascii=False)

    rows = []
    for it in items:
        en = f'<span class="en">{esc(it["en"])}</span>' if it['en'] else ''
        cn = f'<span class="cn">{esc(it["cn"])}</span>' if it['cn'] else ''
        rows.append(f'      <li>{en}{cn}</li>')
    sentences = '\n'.join(rows)

    pager = []
    if prev_item:
        pager.append(f'<a href="{esc(prev_item["slug"])}.html">← 上一课：{esc(prev_item["title"])}</a>')
    else:
        pager.append('<span></span>')
    pager.append('<a href="./">本册目录</a>')
    if next_item:
        pager.append(f'<a href="{esc(next_item["slug"])}.html">下一课：{esc(next_item["title"])} →</a>')
    else:
        pager.append('<span></span>')
    pager_html = '\n      '.join(pager)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} - 新概念英语第{book_n}册课文 · 中英对照 | NCE Flow</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{url}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="NCE Flow">
  <meta property="og:locale" content="zh_CN">
  <meta property="og:title" content="{esc(title)} - 新概念英语第{book_n}册课文">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{SITE}/icons/icon-512x512.png">
  <meta name="twitter:card" content="summary">
  <link rel="icon" href="../favicon.ico">
  <style>{CSS}</style>
  <script type="application/ld+json">{jsonld}</script>
</head>
<body>
  <main class="wrap">
    <nav class="crumb"><a href="../index.html">首页</a> › <a href="./">新概念英语第{book_n}册</a> › {esc(title)}</nav>
    <h1>{esc(title)}</h1>
    <p class="meta">新概念英语第{book_n}册 · 第 {esc(no)} 课 · 中英文对照课文</p>
    <a class="cta" href="{play_href}">▶ 点读 / 听力练习</a>
    <ol class="sentences">
{sentences}
    </ol>
    <nav class="pager">
      {pager_html}
    </nav>
  </main>
</body>
</html>
"""


def render_book_index(book, book_n, lessons):
    url = f"{SITE}/{book}/"
    items_html = '\n'.join(
        f'      <li><a href="{esc(l["slug"])}.html"><span class="no">{esc(lesson_no(l["filename"]))}</span>{esc(l["title"])}</a></li>'
        for l in lessons
    )
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Course",
        "name": f"新概念英语第{book_n}册",
        "description": f"新概念英语第{book_n}册全部课文目录，含中英文对照与点读听力。",
        "inLanguage": ["en", "zh-CN"],
        "url": url
    }, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>新概念英语第{book_n}册 课文目录（中英对照） | NCE Flow</title>
  <meta name="description" content="新概念英语第{book_n}册全部课文目录，提供课文原文、中英文对照翻译与在线点读听力练习。">
  <link rel="canonical" href="{url}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="NCE Flow">
  <meta property="og:locale" content="zh_CN">
  <meta property="og:title" content="新概念英语第{book_n}册 课文目录">
  <meta property="og:description" content="新概念英语第{book_n}册全部课文目录，中英文对照与在线点读。">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{SITE}/icons/icon-512x512.png">
  <meta name="twitter:card" content="summary">
  <link rel="icon" href="../favicon.ico">
  <style>{CSS}</style>
  <script type="application/ld+json">{jsonld}</script>
</head>
<body>
  <main class="wrap">
    <nav class="crumb"><a href="../index.html">首页</a> › 新概念英语第{book_n}册</nav>
    <h1>新概念英语第{book_n}册 · 课文目录</h1>
    <p class="meta">共 {len(lessons)} 课 · 中英文对照 · 在线点读</p>
    <ul class="toc">
{items_html}
    </ul>
  </main>
</body>
</html>
"""


def main():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    sitemap_urls = [(f"{SITE}/", 'weekly', '1.0'),
                    (f"{SITE}/about.html", 'monthly', '0.5')]
    total = 0
    missing = []

    for book_key in sorted(data.keys()):
        book = f"NCE{book_key}"
        book_n = book_key
        lessons = []
        seen_slugs = {}
        # 先算好每课的 slug（供上下课互链）
        for entry in data[book_key]:
            filename = entry['filename']
            slug = slugify(filename) or f"lesson-{len(lessons)+1}"
            if slug in seen_slugs:
                slug = f"{slug}-{len(lessons)+1}"
                print(f"  ! slug 碰撞，已加序号: {book}/{filename} -> {slug}")
            seen_slugs[slug] = True
            lessons.append({'title': entry['title'], 'filename': filename, 'slug': slug})

        if not os.path.isdir(book):
            print(f"  ! 跳过：目录不存在 {book}")
            continue

        sitemap_urls.append((f"{SITE}/{book}/", 'weekly', '0.8'))
        for i, l in enumerate(lessons):
            lrc_path = os.path.join(book, l['filename'] + '.lrc')
            items = parse_lrc(lrc_path)
            if not items:
                missing.append(lrc_path)
                continue
            prev_item = lessons[i - 1] if i > 0 else None
            next_item = lessons[i + 1] if i + 1 < len(lessons) else None
            page = render_lesson(book, book_n, l['title'], l['filename'], l['slug'],
                                 items, prev_item, next_item)
            out = os.path.join(book, l['slug'] + '.html')
            with open(out, 'w', encoding='utf-8') as f:
                f.write(page)
            sitemap_urls.append((f"{SITE}/{book}/{l['slug']}.html", 'monthly', '0.7'))
            total += 1

        # 册目录页
        with open(os.path.join(book, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(render_book_index(book, book_n, lessons))
        print(f"  {book}: {len(lessons)} 课")

    # 全量 sitemap
    rows = []
    for loc, freq, pri in sitemap_urls:
        rows.append(f"  <url>\n    <loc>{loc}</loc>\n    <changefreq>{freq}</changefreq>\n    <priority>{pri}</priority>\n  </url>")
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + '\n'.join(rows) + '\n</urlset>\n')
    with open(SITEMAP_FILE, 'w', encoding='utf-8') as f:
        f.write(sitemap)

    print(f"\n✅ 生成课页 {total} 个，sitemap 含 {len(sitemap_urls)} 条 URL。")
    if missing:
        print(f"⚠ 缺失/空 .lrc {len(missing)} 个：")
        for m in missing[:10]:
            print(f"   - {m}")


if __name__ == '__main__':
    main()
