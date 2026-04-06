#!/usr/bin/env python3
"""
render_v4.py — Convert AITF v4 structured .md files into static HTML pages.

Usage: python3 render_v4.py [YYYY-MM-DD]
  If no date given, processes today's v4/ directory.

What it does:
1. Reads workspace/v4/YYYY-MM-DD/*.md files
2. Parses YAML front matter and v4 node structure
3. Generates HTML pages:
   - brief_*.md → aggregated into news/YYYY-MM-DD.html
   - analysis_*.md → independent page at analysis/YYYY-MM-DD-slug.html
     + card entry in news/YYYY-MM-DD.html
   - paper_candidates.md → papers/YYYY-MM-DD.html
   - insight_*.md → independent page at insights/YYYY-MM-DD-slug.html
4. All HTML uses same styles as aitf.today homepage
"""

import os
import re
import sys
from datetime import datetime, date

# === CONFIGURATION ===
V4_DIR = "workspace/v4"
SITE_DIR = "workspace/sites/news"
SITE_URL = "https://aitf.today"

# === NODE MARKER PATTERNS ===
NODE_PATTERN = re.compile(
    r'^(\s*)'                          # indentation
    r'(C|E|P|K|G|A|M|S|D|R|'          # analysis node types
    r'CON|DEF|REL|PRO|EXA|CTR|APP|SRC|TAG|GAP|'  # knowledge nodes
    r'OBJ|CTX|IN|OUT|CST|ACC|DEP|Q|LOG|'  # task nodes
    r'SUG|RSP|JUS|MOD)'               # collaboration nodes
    r'\(([^)]+)\)'                     # annotation in parentheses
    r':\s*'                            # colon separator
    r'(.+)$',                          # content
    re.MULTILINE
)

STATUS_PATTERN = re.compile(r'\s*\[(V|U|X|N)\]\s*$')

# === CSS CLASSES FOR NODE TYPES ===
NODE_COLORS = {
    'C': 'conclusion', 'E': 'evaluation', 'P': 'evidence',
    'K': 'risk', 'G': 'gap', 'A': 'assumption',
    'M': 'mechanism', 'S': 'solution', 'D': 'dependency',
    'R': 'rule',
    'CON': 'concept', 'DEF': 'definition', 'REL': 'evaluation',
    'PRO': 'mechanism', 'EXA': 'evidence', 'CTR': 'risk',
    'APP': 'mechanism', 'SRC': 'source', 'TAG': 'tag',
    'GAP': 'gap',
    'OBJ': 'conclusion', 'CTX': 'evaluation', 'IN': 'evidence',
    'OUT': 'conclusion', 'CST': 'risk', 'ACC': 'conclusion',
    'DEP': 'dependency', 'Q': 'gap', 'LOG': 'source',
    'SUG': 'evaluation', 'RSP': 'mechanism', 'JUS': 'evidence',
    'MOD': 'mechanism',
}


def parse_yaml_header(content):
    """Extract YAML front matter from .md content."""
    if not content.startswith('---'):
        return {}, content

    end = content.find('---', 3)
    if end == -1:
        return {}, content

    yaml_text = content[3:end].strip()
    body = content[end + 3:].strip()

    meta = {}
    for line in yaml_text.split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip()
            # Handle list values [a, b, c]
            if val.startswith('[') and val.endswith(']'):
                val = [v.strip().strip('"').strip("'")
                       for v in val[1:-1].split(',') if v.strip()]
            meta[key] = val
    return meta, body


def parse_v4_nodes(body):
    """Parse v4 structured text into a list of node dicts."""
    nodes = []
    lines = body.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for section headers (## Agent Commentary, ---, # Title)
        stripped = line.strip()
        if stripped.startswith('## '):
            nodes.append({
                'type': 'section_header',
                'text': stripped[3:],
                'indent': 0,
            })
            i += 1
            continue

        if stripped.startswith('# '):
            nodes.append({
                'type': 'title',
                'text': stripped[2:],
                'indent': 0,
            })
            i += 1
            continue

        if stripped == '---':
            nodes.append({'type': 'divider', 'indent': 0})
            i += 1
            continue

        # Try to match a v4 node
        match = NODE_PATTERN.match(line)
        if match:
            indent = len(match.group(1))
            node_type = match.group(2)
            annotation = match.group(3)
            content = match.group(4)

            # Collect continuation lines (indented text without node marker)
            while i + 1 < len(lines):
                next_line = lines[i + 1]
                next_stripped = next_line.strip()
                if not next_stripped:
                    break
                if NODE_PATTERN.match(next_line):
                    break
                if next_stripped.startswith('## ') or next_stripped.startswith('# '):
                    break
                if next_stripped == '---':
                    break
                content += ' ' + next_stripped
                i += 1

            # Extract status code
            status = None
            status_match = STATUS_PATTERN.search(content)
            if status_match:
                status = status_match.group(1)
                content = content[:status_match.start()].strip()

            # Determine indent level (0, 1, 2, ...)
            indent_level = indent // 2 if indent > 0 else 0

            nodes.append({
                'type': 'node',
                'node_type': node_type,
                'annotation': annotation,
                'content': content,
                'status': status,
                'indent': indent_level,
                'color_class': NODE_COLORS.get(node_type, 'evaluation'),
            })
        elif stripped:
            # Plain text line
            nodes.append({
                'type': 'text',
                'text': stripped,
                'indent': 0,
            })

        i += 1

    return nodes


def render_node_html(node):
    """Render a single v4 node to HTML."""
    if node['type'] == 'title':
        return f'<h1 class="article-title">{node["text"]}</h1>\n'

    if node['type'] == 'section_header':
        return f'<h2 class="article-section-header">{node["text"]}</h2>\n'

    if node['type'] == 'divider':
        return '<hr class="article-divider">\n'

    if node['type'] == 'text':
        return f'<p class="article-text">{node["text"]}</p>\n'

    if node['type'] == 'node':
        indent_class = f' v4-node-indent-{node["indent"]}' if node['indent'] > 0 else ''
        color_class = node['color_class']
        marker = f'{node["node_type"]}({node["annotation"]})'
        content = node['content']

        # Handle TAG nodes specially — render as pills
        if node['node_type'] == 'TAG':
            tags_text = content.strip('[]')
            tags = [t.strip() for t in tags_text.split(',') if t.strip()]
            pills = ''.join(f'<span class="tag-pill">{t}</span>' for t in tags)
            return (
                f'<div class="v4-node{indent_class}">'
                f'<span class="node-marker node-marker-{color_class}">{marker}:</span> '
                f'<div class="card-tags">{pills}</div>'
                f'</div>\n'
            )

        # Handle SRC nodes — make URLs clickable
        if node['node_type'] == 'SRC':
            url_match = re.search(r'(https?://\S+)', content)
            if url_match:
                url = url_match.group(1)
                display = content.replace(url, f'<a href="{url}" target="_blank" rel="noopener">{url}</a>')
                content = display

        status_html = ''
        if node['status']:
            status_class = f'status-{node["status"].lower()}'
            status_html = f' <span class="node-status {status_class}">{node["status"]}</span>'

        return (
            f'<div class="v4-node{indent_class}">'
            f'<span class="node-marker node-marker-{color_class}">{marker}:</span> '
            f'<span class="node-text">{content}</span>'
            f'{status_html}'
            f'</div>\n'
        )

    return ''


def render_nodes_html(nodes):
    """Render a list of nodes to HTML string."""
    return ''.join(render_node_html(n) for n in nodes)


def get_first_conclusion(nodes):
    """Extract the first C(Conclusion) or CON(Concept) text for meta description."""
    for n in nodes:
        if n['type'] == 'node' and n['node_type'] in ('C', 'CON'):
            return n['content'][:200]
    # Fallback to first node content
    for n in nodes:
        if n['type'] == 'node':
            return n['content'][:200]
    return ''


def slugify(text):
    """Convert title text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:60].strip('-')


def get_title(nodes):
    """Extract title from parsed nodes."""
    for n in nodes:
        if n['type'] == 'title':
            return n['text']
    return 'Untitled'


# === HTML TEMPLATES ===

def page_template(title, description, content_html, page_type="article",
                   date_str="", nav_active=""):
    """Generate a complete HTML page."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | AITF.TODAY</title>
    <meta name="description" content="{description}">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:type" content="article">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=VT323&family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #FAF9F6;
            --bg-alt: #F3F1EC;
            --text: #1a1a1a;
            --text-dim: #6b6560;
            --text-light: #9a9590;
            --title: #2c2520;
            --border: #d8d4cf;
            --border-light: #e8e5e0;
            --node-conclusion: #1a6b3c;
            --node-evaluation: #2c5aa0;
            --node-evidence: #5c4a9e;
            --node-risk: #c43030;
            --node-gap: #b85c00;
            --node-assumption: #7a6850;
            --node-mechanism: #3a7070;
            --node-concept: #1a6b3c;
            --node-source: #6b6560;
            --node-tag: #5c4a9e;
            --node-definition: #2c5aa0;
            --node-solution: #1a6b3c;
            --node-dependency: #7a6850;
            --node-rule: #c43030;
            --status-v: #1a6b3c;
            --status-u: #7a7570;
            --status-x: #b85c00;
            --status-n: #c43030;
            --type-brief-border: #b0aaa0;
            --type-analysis-border: #4a9060;
            --type-paper-border: #6a5a9e;
            --type-insight-border: #c8a050;
            --font-pixel: 'VT323', monospace;
            --font-mono: 'IBM Plex Mono', monospace;
            --font-body: 'IBM Plex Sans', sans-serif;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: var(--font-body);
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            font-size: 15px;
        }}
        .container {{ max-width: 960px; margin: 0 auto; padding: 0 24px; }}

        /* Header */
        header {{
            border-bottom: 2px solid var(--title);
            padding: 20px 0 16px;
        }}
        .site-title {{
            font-family: var(--font-pixel);
            font-size: 36px;
            color: var(--title);
            letter-spacing: 2px;
            text-decoration: none;
            line-height: 1;
        }}
        .site-title span {{ color: var(--node-conclusion); }}

        /* Nav */
        nav {{
            border-bottom: 1px solid var(--border);
            padding: 12px 0;
            background: var(--bg);
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        nav .container {{ display: flex; gap: 28px; align-items: center; }}
        nav a {{
            font-family: var(--font-mono);
            font-size: 13px;
            font-weight: 500;
            color: var(--text-dim);
            text-decoration: none;
            letter-spacing: 0.5px;
            padding: 4px 0;
            border-bottom: 2px solid transparent;
            transition: color 0.2s, border-color 0.2s;
        }}
        nav a:hover, nav a.active {{ color: var(--title); border-bottom-color: var(--title); }}
        nav .nav-spacer {{ flex: 1; }}
        nav .nav-date {{ font-family: var(--font-mono); font-size: 12px; color: var(--text-light); }}

        /* Article content */
        .article-container {{
            padding: 40px 0;
            max-width: 760px;
        }}
        .article-meta {{
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--text-light);
            margin-bottom: 8px;
            display: flex;
            gap: 16px;
            align-items: center;
        }}
        .article-type-badge {{
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 2px 8px;
            border-radius: 2px;
            color: #fff;
        }}
        .badge-analysis {{ background: var(--type-analysis-border); }}
        .badge-brief {{ background: var(--type-brief-border); }}
        .badge-paper {{ background: var(--type-paper-border); }}
        .badge-insight {{ background: var(--type-insight-border); }}
        .article-title {{
            font-family: var(--font-mono);
            font-size: 22px;
            font-weight: 700;
            color: var(--title);
            line-height: 1.35;
            margin-bottom: 28px;
        }}
        .article-section-header {{
            font-family: var(--font-mono);
            font-size: 16px;
            font-weight: 600;
            color: var(--title);
            margin: 28px 0 16px;
            padding-top: 16px;
        }}
        .article-divider {{
            border: none;
            border-top: 1px solid var(--border);
            margin: 28px 0;
        }}
        .article-text {{
            font-size: 14.5px;
            color: var(--text);
            margin-bottom: 12px;
        }}

        /* V4 Nodes */
        .v4-node {{ margin-bottom: 14px; line-height: 1.65; }}
        .v4-node-indent-1 {{ padding-left: 28px; }}
        .v4-node-indent-2 {{ padding-left: 56px; }}
        .v4-node-indent-3 {{ padding-left: 84px; }}
        .node-marker {{
            font-family: var(--font-mono);
            font-weight: 600;
            font-size: 13px;
            letter-spacing: 0.3px;
        }}
        .node-marker-conclusion {{ color: var(--node-conclusion); }}
        .node-marker-evaluation {{ color: var(--node-evaluation); }}
        .node-marker-evidence {{ color: var(--node-evidence); }}
        .node-marker-risk {{ color: var(--node-risk); }}
        .node-marker-gap {{ color: var(--node-gap); }}
        .node-marker-assumption {{ color: var(--node-assumption); }}
        .node-marker-mechanism {{ color: var(--node-mechanism); }}
        .node-marker-concept {{ color: var(--node-concept); }}
        .node-marker-source {{ color: var(--node-source); }}
        .node-marker-tag {{ color: var(--node-tag); }}
        .node-marker-definition {{ color: var(--node-definition); }}
        .node-marker-solution {{ color: var(--node-solution); }}
        .node-marker-dependency {{ color: var(--node-dependency); }}
        .node-marker-rule {{ color: var(--node-rule); }}
        .node-text {{ color: var(--text); font-size: 14.5px; }}
        .node-status {{
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 600;
            padding: 1px 6px;
            border-radius: 3px;
            margin-left: 6px;
            vertical-align: 1px;
        }}
        .status-v {{ background: #e6f4ea; color: var(--status-v); }}
        .status-u {{ background: #f0eeeb; color: var(--status-u); }}
        .status-x {{ background: #fef0e0; color: var(--status-x); }}
        .status-n {{ background: #fde8e8; color: var(--status-n); }}

        /* Tags */
        .card-tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; display: inline-flex; }}
        .tag-pill {{
            font-family: var(--font-mono);
            font-size: 10px;
            color: var(--node-tag);
            background: rgba(92, 74, 158, 0.08);
            padding: 2px 8px;
            border-radius: 10px;
            border: 1px solid rgba(92, 74, 158, 0.2);
        }}

        /* Aggregation page cards */
        .agg-card {{
            border: 1px solid var(--border);
            border-radius: 3px;
            padding: 20px 24px;
            margin-bottom: 16px;
        }}
        .agg-card-brief {{
            background: #F3F1EC;
            border-left: 4px solid var(--type-brief-border);
        }}
        .agg-card-analysis {{
            background: #e6efe8;
            border-left: 4px solid var(--type-analysis-border);
        }}
        .agg-card-paper {{
            background: #e8e6f0;
            border-left: 4px solid var(--type-paper-border);
        }}
        .agg-card-title {{
            font-family: var(--font-mono);
            font-size: 15px;
            font-weight: 600;
            color: var(--title);
            margin-bottom: 10px;
            line-height: 1.4;
        }}
        .agg-card-title a {{
            color: var(--title);
            text-decoration: none;
            border-bottom: 1px dashed var(--border);
        }}
        .agg-card-title a:hover {{ border-bottom-color: var(--title); }}

        /* Back link */
        .back-link {{
            font-family: var(--font-mono);
            font-size: 13px;
            color: var(--text-dim);
            text-decoration: none;
            display: inline-block;
            margin-bottom: 20px;
        }}
        .back-link:hover {{ color: var(--title); }}

        /* Footer */
        footer {{
            padding: 40px 0;
            text-align: center;
            border-top: 1px solid var(--border);
            margin-top: 40px;
        }}
        .footer-text {{
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--text-light);
            line-height: 2;
        }}
        .footer-text a {{
            color: var(--text-dim);
            text-decoration: none;
            border-bottom: 1px dashed var(--text-light);
        }}
        .footer-text a:hover {{ color: var(--title); border-bottom-color: var(--title); }}

        @media (max-width: 640px) {{
            .article-title {{ font-size: 18px; }}
            .v4-node-indent-1 {{ padding-left: 16px; }}
            .v4-node-indent-2 {{ padding-left: 32px; }}
            .v4-node-indent-3 {{ padding-left: 48px; }}
            nav .container {{ flex-wrap: wrap; gap: 12px; }}
        }}
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
            <a href="/news/"{' class="active"' if nav_active == 'news' else ''}>News</a>
            <a href="/papers/"{' class="active"' if nav_active == 'papers' else ''}>Papers</a>
            <a href="/analysis/"{' class="active"' if nav_active == 'analysis' else ''}>Analysis</a>
            <a href="/insights/"{' class="active"' if nav_active == 'insights' else ''}>Insights</a>
            <a href="/format.html">AITF Format</a>
            <a href="/about.html">About</a>
            <span class="nav-spacer"></span>
            <span class="nav-date">{date_str}</span>
        </div>
    </nav>
    <div class="container">
        <div class="article-container">
{content_html}
        </div>
    </div>
    <footer>
        <div class="container">
            <div class="footer-text">
                AITF.TODAY — Agent Interaction Text Format<br>
                Content structured in <a href="/format.html">AITF v4.0</a><br>
                <a href="https://intelligenism.club">Intelligenism Commercial Development LLC</a>
            </div>
        </div>
    </footer>
</body>
</html>'''


def render_independent_page(meta, nodes, page_type):
    """Render an analysis or insight article as an independent HTML page."""
    title = get_title(nodes)
    description = get_first_conclusion(nodes)
    date_str = meta.get('date', '')

    badge_class = f'badge-{page_type}'
    badge_text = page_type.upper()

    content_parts = []
    content_parts.append(f'            <a href="/" class="back-link">← Back to Home</a>\n')
    content_parts.append(
        f'            <div class="article-meta">\n'
        f'                <span class="article-type-badge {badge_class}">{badge_text}</span>\n'
        f'                <span>{date_str}</span>\n'
        f'                <span>{meta.get("source", "")}</span>\n'
        f'            </div>\n'
    )
    content_parts.append(render_nodes_html(nodes))

    content_html = ''.join(content_parts)
    nav_active = 'analysis' if page_type == 'analysis' else 'insights'

    return page_template(title, description, content_html,
                         date_str=date_str, nav_active=nav_active)


def render_daily_news_page(date_str, briefs_data, analysis_data):
    """Render a daily news aggregation page with briefs and analysis cards."""
    content_parts = []
    content_parts.append(f'            <a href="/" class="back-link">← Back to Home</a>\n')
    content_parts.append(f'            <h1 class="article-title">News — {date_str}</h1>\n')

    # Analyses first (more important)
    for meta, nodes, slug in analysis_data:
        title = get_title(nodes)
        conclusion = get_first_conclusion(nodes)
        link = f'/analysis/{date_str}-{slug}.html'
        content_parts.append(
            f'            <div class="agg-card agg-card-analysis">\n'
            f'                <div class="article-meta">\n'
            f'                    <span class="article-type-badge badge-analysis">ANALYSIS</span>\n'
            f'                    <span>{meta.get("source", "")}</span>\n'
            f'                </div>\n'
            f'                <div class="agg-card-title"><a href="{link}">{title}</a></div>\n'
            f'                <div class="v4-node">\n'
            f'                    <span class="node-marker node-marker-conclusion">C(Conclusion):</span>\n'
            f'                    <span class="node-text">{conclusion}</span>\n'
            f'                </div>\n'
            f'            </div>\n'
        )

    # Briefs (inline, full v4 content)
    for meta, nodes in briefs_data:
        title = get_title(nodes)
        content_parts.append(
            f'            <div class="agg-card agg-card-brief">\n'
            f'                <div class="article-meta">\n'
            f'                    <span class="article-type-badge badge-brief">BRIEF</span>\n'
            f'                    <span>{meta.get("source", "")}</span>\n'
            f'                </div>\n'
        )
        # Render all nodes inline (briefs are short enough)
        for n in nodes:
            if n['type'] != 'title':
                content_parts.append('                ' + render_node_html(n))
        content_parts.append('            </div>\n')

    if not briefs_data and not analysis_data:
        content_parts.append(
            '            <p class="article-text" style="color: var(--text-light); '
            'font-style: italic;">No signals collected for this date.</p>\n'
        )

    content_html = ''.join(content_parts)
    return page_template(f'News — {date_str}', f'Daily AI agent industry signals for {date_str}',
                         content_html, date_str=date_str, nav_active='news')


def render_daily_papers_page(date_str, meta, nodes):
    """Render a daily paper candidates aggregation page."""
    title = get_title(nodes)
    description = f'Paper candidates for {date_str}'

    content_parts = []
    content_parts.append(f'            <a href="/" class="back-link">← Back to Home</a>\n')
    content_parts.append(
        f'            <div class="article-meta">\n'
        f'                <span class="article-type-badge badge-paper">PAPERS</span>\n'
        f'                <span>{date_str}</span>\n'
        f'            </div>\n'
    )

    # Render nodes, wrapping each paper section in a card
    in_card = False
    card_html = []

    for n in nodes:
        if n['type'] == 'title':
            content_parts.append(render_node_html(n))
            continue

        if n['type'] == 'divider':
            if in_card and card_html:
                content_parts.append(
                    '            <div class="agg-card agg-card-paper">\n'
                    + ''.join('                ' + h for h in card_html)
                    + '            </div>\n'
                )
                card_html = []
            in_card = True
            continue

        if in_card:
            card_html.append(render_node_html(n))
        else:
            content_parts.append(render_node_html(n))

    # Flush last card
    if in_card and card_html:
        content_parts.append(
            '            <div class="agg-card agg-card-paper">\n'
            + ''.join('                ' + h for h in card_html)
            + '            </div>\n'
        )

    content_html = ''.join(content_parts)
    return page_template(title, description, content_html,
                         date_str=date_str, nav_active='papers')


def process_date(date_str):
    """Process all v4 .md files for a given date."""
    v4_date_dir = os.path.join(V4_DIR, date_str)
    if not os.path.isdir(v4_date_dir):
        print(f"No v4 directory for {date_str}")
        return

    # Ensure output directories exist
    for subdir in ['news', 'papers', 'analysis', 'insights']:
        os.makedirs(os.path.join(SITE_DIR, subdir), exist_ok=True)

    briefs_data = []
    analysis_data = []
    papers_meta = None
    papers_nodes = None

    files = sorted(os.listdir(v4_date_dir))
    for filename in files:
        if not filename.endswith('.md'):
            continue

        filepath = os.path.join(v4_date_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        meta, body = parse_yaml_header(content)
        nodes = parse_v4_nodes(body)
        content_type = meta.get('type', '')

        if content_type == 'brief' or filename.startswith('brief_'):
            briefs_data.append((meta, nodes))
            print(f"  [BRIEF] {filename}")

        elif content_type == 'analysis' or filename.startswith('analysis_'):
            title = get_title(nodes)
            slug = slugify(title)
            analysis_data.append((meta, nodes, slug))

            # Generate independent page
            html = render_independent_page(meta, nodes, 'analysis')
            out_path = os.path.join(SITE_DIR, 'analysis', f'{date_str}-{slug}.html')
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"  [ANALYSIS] {filename} → analysis/{date_str}-{slug}.html")

        elif content_type == 'paper_candidates' or filename.startswith('paper_'):
            papers_meta = meta
            papers_nodes = nodes
            print(f"  [PAPERS] {filename}")

        elif content_type == 'insight' or filename.startswith('insight_'):
            title = get_title(nodes)
            slug = slugify(title)

            html = render_independent_page(meta, nodes, 'insight')
            out_path = os.path.join(SITE_DIR, 'insights', f'{date_str}-{slug}.html')
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"  [INSIGHT] {filename} → insights/{date_str}-{slug}.html")

    # Generate daily news aggregation page
    if briefs_data or analysis_data:
        html = render_daily_news_page(date_str, briefs_data, analysis_data)
        out_path = os.path.join(SITE_DIR, 'news', f'{date_str}.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  [NEWS PAGE] news/{date_str}.html "
              f"({len(analysis_data)} analyses, {len(briefs_data)} briefs)")

    # Generate daily papers page
    if papers_meta and papers_nodes:
        html = render_daily_papers_page(date_str, papers_meta, papers_nodes)
        out_path = os.path.join(SITE_DIR, 'papers', f'{date_str}.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  [PAPERS PAGE] papers/{date_str}.html")


def main():
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = date.today().isoformat()

    print(f"render_v4.py — Processing {date_str}")
    process_date(date_str)
    print("Done.")


if __name__ == '__main__':
    main()
