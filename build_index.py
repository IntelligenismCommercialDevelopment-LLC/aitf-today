#!/usr/bin/env python3
"""
build_index.py — Scan generated HTML pages, inject latest content cards
into index.html, and generate sitemap.xml.

Usage: python3 build_index.py

What it does:
1. Scans news/, analysis/, papers/, insights/ directories for .html files
2. Extracts metadata (title, date, type, description) from each page
3. Injects latest content cards into index.html between marker comments
4. Generates sitemap.xml with all pages
5. Generates simple archive index pages for each section

Markers in index.html:
  <!-- BUILD_PAGES_NEWS_START -->...<!-- BUILD_PAGES_NEWS_END -->
  <!-- BUILD_PAGES_PAPERS_START -->...<!-- BUILD_PAGES_PAPERS_END -->
  <!-- BUILD_PAGES_INSIGHTS_START -->...<!-- BUILD_PAGES_INSIGHTS_END -->
"""

import os
import re
from datetime import date

# === CONFIGURATION ===
SITE_DIR = "workspace/sites/news"
INDEX_FILE = os.path.join(SITE_DIR, "index.html")
SITEMAP_FILE = os.path.join(SITE_DIR, "sitemap.xml")
SITE_URL = "https://aitf.today"

# How many recent items to show on homepage
MAX_NEWS_DAYS = 5
MAX_PAPERS_DAYS = 5
MAX_INSIGHTS = 7
MAX_ANALYSIS = 7


def extract_meta_from_html(filepath):
    """Extract title and description from an HTML file's meta tags."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read(4000)  # Only need the head section

    title_match = re.search(r'<title>([^<]*)\|', content)
    title = title_match.group(1).strip() if title_match else os.path.basename(filepath)

    desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', content)
    description = desc_match.group(1) if desc_match else ''

    return title, description


def scan_section(section_name):
    """Scan a section directory for HTML files and extract metadata."""
    section_dir = os.path.join(SITE_DIR, section_name)
    if not os.path.isdir(section_dir):
        return []

    pages = []
    for filename in sorted(os.listdir(section_dir), reverse=True):
        if not filename.endswith('.html') or filename == 'index.html':
            continue

        filepath = os.path.join(section_dir, filename)
        title, description = extract_meta_from_html(filepath)

        # Extract date from filename (YYYY-MM-DD prefix)
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
        file_date = date_match.group(1) if date_match else '1970-01-01'

        pages.append({
            'filename': filename,
            'path': f'/{section_name}/{filename}',
            'title': title,
            'description': description[:200],
            'date': file_date,
            'section': section_name,
        })

    return pages


def generate_news_card(page):
    """Generate a news card for homepage injection."""
    # Determine if this is a daily aggregation page
    badge_class = 'badge-analysis' if 'analysis' in page.get('section', '') else 'badge-brief'
    badge_text = page.get('section', 'news').upper()

    return (
        f'            <a href="{page["path"]}" class="card-analysis" style="text-decoration:none;">\n'
        f'                <div style="display:flex; gap:12px; align-items:center; margin-bottom:6px;">\n'
        f'                    <span class="card-type-badge badge-analysis">NEWS</span>\n'
        f'                    <span style="font-family:var(--font-mono);font-size:11px;color:var(--text-light);">{page["date"]}</span>\n'
        f'                </div>\n'
        f'                <div class="card-title">{page["title"]}</div>\n'
        f'                <div class="card-conclusion">{page["description"]}</div>\n'
        f'            </a>\n'
    )


def generate_paper_card(page):
    """Generate a paper card for homepage injection."""
    return (
        f'            <a href="{page["path"]}" class="card-paper" style="text-decoration:none;">\n'
        f'                <div style="display:flex; gap:12px; align-items:center; margin-bottom:6px;">\n'
        f'                    <span class="card-type-badge badge-paper">PAPERS</span>\n'
        f'                    <span style="font-family:var(--font-mono);font-size:11px;color:var(--text-light);">{page["date"]}</span>\n'
        f'                </div>\n'
        f'                <div class="card-title">{page["title"]}</div>\n'
        f'            </a>\n'
    )


def generate_insight_card(page):
    """Generate an insight/analysis card for homepage injection."""
    section = page['section']
    if section == 'insights':
        badge_class = 'badge-insight'
        badge_text = 'INSIGHT'
        card_class = 'card-insight'
    else:
        badge_class = 'badge-analysis'
        badge_text = 'ANALYSIS'
        card_class = 'card-analysis'

    return (
        f'            <a href="{page["path"]}" class="{card_class}" style="text-decoration:none;">\n'
        f'                <div style="display:flex; gap:12px; align-items:center; margin-bottom:6px;">\n'
        f'                    <span class="card-type-badge {badge_class}">{badge_text}</span>\n'
        f'                    <span style="font-family:var(--font-mono);font-size:11px;color:var(--text-light);">{page["date"]}</span>\n'
        f'                </div>\n'
        f'                <div class="card-title">{page["title"]}</div>\n'
        f'                <div class="card-conclusion">{page["description"]}</div>\n'
        f'            </a>\n'
    )


def inject_into_index(news_pages, paper_pages, insight_pages):
    """Read index.html, inject latest content between markers, write back."""
    if not os.path.isfile(INDEX_FILE):
        print(f"WARNING: {INDEX_FILE} not found. Skipping injection.")
        return

    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    # === NEWS ===
    news_html = ""
    recent_news = news_pages[:MAX_NEWS_DAYS]
    if recent_news:
        for p in recent_news:
            news_html += generate_news_card(p)
    else:
        news_html = ('            <p class="placeholder-msg">'
                     'Pipeline initializing. First signals arriving soon.</p>\n')

    news_pattern = r'(<!-- BUILD_PAGES_NEWS_START -->\n).*?(<!-- BUILD_PAGES_NEWS_END -->)'
    html, count = re.subn(news_pattern, rf'\g<1>{news_html}            \2', html, flags=re.DOTALL)
    if count == 0:
        print("WARNING: BUILD_PAGES_NEWS markers not found in index.html")

    # === PAPERS ===
    papers_html = ""
    recent_papers = paper_pages[:MAX_PAPERS_DAYS]
    if recent_papers:
        for p in recent_papers:
            papers_html += generate_paper_card(p)
    else:
        papers_html = ('            <p class="placeholder-msg">'
                       'Paper scanning pipeline initializing.</p>\n')

    papers_pattern = r'(<!-- BUILD_PAGES_PAPERS_START -->\n).*?(<!-- BUILD_PAGES_PAPERS_END -->)'
    html, count = re.subn(papers_pattern, rf'\g<1>{papers_html}            \2', html, flags=re.DOTALL)
    if count == 0:
        print("WARNING: BUILD_PAGES_PAPERS markers not found in index.html")

    # === INSIGHTS (insights + analysis combined, sorted by date) ===
    insights_html = ""
    recent_insights = insight_pages[:MAX_INSIGHTS]
    if recent_insights:
        for p in recent_insights:
            insights_html += generate_insight_card(p)
    else:
        insights_html = ('            <p class="placeholder-msg">'
                         'First insight arriving after paper review cycle.</p>\n')

    insights_pattern = r'(<!-- BUILD_PAGES_INSIGHTS_START -->\n).*?(<!-- BUILD_PAGES_INSIGHTS_END -->)'
    html, count = re.subn(insights_pattern, rf'\g<1>{insights_html}            \2', html, flags=re.DOTALL)
    if count == 0:
        print("WARNING: BUILD_PAGES_INSIGHTS markers not found in index.html")

    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Injected {len(recent_news)} news, {len(recent_papers)} papers, "
          f"{len(recent_insights)} insights into index.html")


def generate_sitemap(all_pages):
    """Generate sitemap.xml with homepage + all pages."""
    today = date.today().isoformat()

    urls = []
    # Homepage
    urls.append(
        f'  <url>\n'
        f'    <loc>{SITE_URL}/</loc>\n'
        f'    <lastmod>{today}</lastmod>\n'
        f'    <changefreq>daily</changefreq>\n'
        f'  </url>'
    )

    # Static pages
    for static in ['format.html', 'about.html']:
        urls.append(
            f'  <url>\n'
            f'    <loc>{SITE_URL}/{static}</loc>\n'
            f'    <lastmod>{today}</lastmod>\n'
            f'    <changefreq>monthly</changefreq>\n'
            f'  </url>'
        )

    # Section index pages
    for section in ['news', 'papers', 'analysis', 'insights']:
        urls.append(
            f'  <url>\n'
            f'    <loc>{SITE_URL}/{section}/</loc>\n'
            f'    <lastmod>{today}</lastmod>\n'
            f'    <changefreq>daily</changefreq>\n'
            f'  </url>'
        )

    # All content pages
    for p in all_pages:
        lastmod = p['date'] if p['date'] != '1970-01-01' else today
        urls.append(
            f'  <url>\n'
            f'    <loc>{SITE_URL}{p["path"]}</loc>\n'
            f'    <lastmod>{lastmod}</lastmod>\n'
            f'  </url>'
        )

    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(urls) + '\n'
        '</urlset>\n'
    )

    with open(SITEMAP_FILE, 'w', encoding='utf-8') as f:
        f.write(sitemap)

    print(f"Generated sitemap.xml with {len(urls)} URLs.")


def generate_section_index(section_name, pages, display_name):
    """Generate a simple archive index page for a section."""
    items_html = ""

    if not pages:
        items_html = ('<p style="font-family:var(--font-mono);font-size:13px;'
                      'color:#9a9590;font-style:italic;">No content yet.</p>\n')
    else:
        # Group by month
        months = {}
        for p in pages:
            month_key = p['date'][:7]  # YYYY-MM
            if month_key not in months:
                months[month_key] = []
            months[month_key].append(p)

        for month_key in sorted(months.keys(), reverse=True):
            items_html += (
                f'<div style="font-family:var(--font-pixel);font-size:24px;'
                f'color:#2c2520;margin:28px 0 12px;letter-spacing:1px;">'
                f'{month_key}</div>\n'
            )
            for p in months[month_key]:
                items_html += (
                    f'<a href="{p["path"]}" style="display:block;font-family:var(--font-mono);'
                    f'font-size:14px;color:#2c2520;text-decoration:none;padding:8px 0;'
                    f'border-bottom:1px solid #e8e5e0;">'
                    f'<span style="color:#9a9590;margin-right:12px;">{p["date"]}</span>'
                    f'{p["title"]}'
                    f'</a>\n'
                )

    page_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{display_name} Archive | AITF.TODAY</title>
    <meta name="description" content="{display_name} archive — AITF.TODAY">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=VT323&family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #FAF9F6; --text: #1a1a1a; --text-dim: #6b6560;
            --text-light: #9a9590; --title: #2c2520; --border: #d8d4cf;
            --node-conclusion: #1a6b3c;
            --font-pixel: 'VT323', monospace;
            --font-mono: 'IBM Plex Mono', monospace;
            --font-body: 'IBM Plex Sans', sans-serif;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: var(--font-body); background: var(--bg); color: var(--text);
               line-height: 1.7; font-size: 15px; }}
        .container {{ max-width: 960px; margin: 0 auto; padding: 0 24px; }}
        header {{ border-bottom: 2px solid var(--title); padding: 20px 0 16px; }}
        .site-title {{ font-family: var(--font-pixel); font-size: 36px; color: var(--title);
                       letter-spacing: 2px; text-decoration: none; line-height: 1; }}
        .site-title span {{ color: var(--node-conclusion); }}
        nav {{ border-bottom: 1px solid var(--border); padding: 12px 0; background: var(--bg);
               position: sticky; top: 0; z-index: 100; }}
        nav .container {{ display: flex; gap: 28px; align-items: center; }}
        nav a {{ font-family: var(--font-mono); font-size: 13px; font-weight: 500;
                 color: var(--text-dim); text-decoration: none; letter-spacing: 0.5px;
                 padding: 4px 0; border-bottom: 2px solid transparent; }}
        nav a:hover, nav a.active {{ color: var(--title); border-bottom-color: var(--title); }}
        nav .nav-spacer {{ flex: 1; }}
        .content {{ padding: 40px 0; max-width: 760px; }}
        .page-title {{ font-family: var(--font-pixel); font-size: 40px; color: var(--title);
                       letter-spacing: 1px; margin-bottom: 8px; }}
        .page-desc {{ font-family: var(--font-mono); font-size: 13px; color: var(--text-light);
                      margin-bottom: 32px; }}
        footer {{ padding: 40px 0; text-align: center; border-top: 1px solid var(--border);
                  margin-top: 40px; }}
        .footer-text {{ font-family: var(--font-mono); font-size: 12px; color: var(--text-light);
                        line-height: 2; }}
        .footer-text a {{ color: var(--text-dim); text-decoration: none;
                          border-bottom: 1px dashed var(--text-light); }}
        @media (max-width: 640px) {{ nav .container {{ flex-wrap: wrap; gap: 12px; }} }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <a href="/" class="site-title">AITF<span>.</span>TODAY</a>
        </div>
    </header>
    <nav>
        <div class="container">
            <a href="/">Home</a>
            <a href="/news/"{' class="active"' if section_name == "news" else ""}>News</a>
            <a href="/papers/"{' class="active"' if section_name == "papers" else ""}>Papers</a>
            <a href="/analysis/"{' class="active"' if section_name == "analysis" else ""}>Analysis</a>
            <a href="/insights/"{' class="active"' if section_name == "insights" else ""}>Insights</a>
            <a href="/format.html">AITF Format</a>
            <a href="/about.html">About</a>
            <span class="nav-spacer"></span>
        </div>
    </nav>
    <div class="container">
        <div class="content">
            <div class="page-title">{display_name}</div>
            <div class="page-desc">Archive — all {display_name.lower()} sorted by date</div>
            {items_html}
        </div>
    </div>
    <footer>
        <div class="container">
            <div class="footer-text">
                AITF.TODAY — Agent Interaction Text Format<br>
                <a href="https://intelligenism.club">Intelligenism Commercial Development LLC</a>
            </div>
        </div>
    </footer>
</body>
</html>'''

    out_path = os.path.join(SITE_DIR, section_name, 'index.html')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(page_html)

    print(f"Generated {section_name}/index.html ({len(pages)} entries)")


def main():
    # 1. Scan all sections
    news_pages = scan_section('news')
    paper_pages = scan_section('papers')
    analysis_pages = scan_section('analysis')
    insight_pages = scan_section('insights')

    # Combine insights and analysis for the homepage Insights section
    combined_insights = sorted(
        analysis_pages + insight_pages,
        key=lambda p: p['date'],
        reverse=True
    )

    all_pages = news_pages + paper_pages + analysis_pages + insight_pages

    print(f"Scanned: {len(news_pages)} news, {len(paper_pages)} papers, "
          f"{len(analysis_pages)} analyses, {len(insight_pages)} insights")

    # 2. Inject into index.html
    inject_into_index(news_pages, paper_pages, combined_insights)

    # 3. Generate sitemap
    generate_sitemap(all_pages)

    # 4. Generate section archive index pages
    generate_section_index('news', news_pages, 'News')
    generate_section_index('papers', paper_pages, 'Papers')
    generate_section_index('analysis', analysis_pages, 'Analysis')
    generate_section_index('insights', insight_pages, 'Insights')

    # 5. Summary
    print(f"\nTotal pages: {len(all_pages)}")
    for p in all_pages[:10]:
        print(f"  [{p['section']}] {p['date']} — {p['title']}")
    if len(all_pages) > 10:
        print(f"  ... and {len(all_pages) - 10} more")


if __name__ == '__main__':
    main()
