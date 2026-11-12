"""
Consolida o Manual Completo do Usuário (docs/MANUAL_DO_USUARIO.md e docs/manual/*.md)
em um arquivo HTML único otimizado para leitura e exportação direta para PDF
via navegador (Ctrl+P -> Salvar como PDF).

Uso:
    uv run python scripts/build_manual_html.py
    uv run python scripts/build_manual_html.py --embed-images
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from html import escape
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"
MANUAL_INDEX = DOCS_DIR / "MANUAL_DO_USUARIO.md"
MANUAL_CHAPTERS_DIR = DOCS_DIR / "manual"
DEFAULT_OUTPUT = DOCS_DIR / "MANUAL_DO_USUARIO.html"

ALERT_META: Dict[str, Tuple[str, str]] = {
    "NOTE": ("Nota", "ℹ️"),
    "TIP": ("Dica", "💡"),
    "IMPORTANT": ("Importante", "❗"),
    "WARNING": ("Aviso", "⚠️"),
    "CAUTION": ("Cuidado", "🛑"),
}

RE_FENCE = re.compile(r"^```(\S*)\s*$")
RE_HEADING = re.compile(r"^(#{1,4})\s+(.+)$")
RE_IMAGE_LINE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
RE_OL_ITEM = re.compile(r"^(\s*)(\d+)\.\s+(.+)$")
RE_UL_ITEM = re.compile(r"^(\s*)[*-]\s+(.+)$")
RE_TABLE_SEP = re.compile(r"^\|\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
RE_ALERT_TAG = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$")


@dataclass
class DocSection:
    anchor_id: str
    title: str
    source_path: Path
    chapter_num: Optional[int]


def _slugify(text: str) -> str:
    clean = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", clean)


def _split_table_row(line: str) -> List[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    cells: List[str] = []
    cur: List[str] = []
    i = 0
    while i < len(stripped):
        if stripped[i] == "\\" and i + 1 < len(stripped) and stripped[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if stripped[i] == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(stripped[i])
        i += 1
    cells.append("".join(cur).strip())
    return cells


def _parse_alignments(sep_line: str) -> List[str]:
    aligns: List[str] = []
    for cell in _split_table_row(sep_line):
        c = cell.strip()
        if c.startswith(":") and c.endswith(":"):
            aligns.append("center")
        elif c.endswith(":"):
            aligns.append("right")
        else:
            aligns.append("left")
    return aligns


class ManualConverter:
    def __init__(
        self,
        chapter_map: Dict[Path, str],
        embed_images: bool = False,
    ) -> None:
        self.chapter_map = chapter_map
        self.embed_images = embed_images
        self._b64_cache: Dict[Path, str] = {}

    def _resolve_img_src(self, raw_src: str, current_file: Path) -> str:
        target = (current_file.parent / raw_src).resolve()
        if not target.exists():
            return raw_src
        if self.embed_images:
            if target not in self._b64_cache:
                mime = "image/png" if target.suffix.lower() == ".png" else "image/jpeg"
                b64 = base64.b64encode(target.read_bytes()).decode("ascii")
                self._b64_cache[target] = f"data:{mime};base64,{b64}"
            return self._b64_cache[target]
        try:
            return target.relative_to(DOCS_DIR.resolve()).as_posix()
        except ValueError:
            return raw_src

    def _resolve_href(self, raw_href: str, current_file: Path) -> str:
        if raw_href.startswith(("http://", "https://", "mailto:", "#")):
            return raw_href
        path_part, _, _frag = raw_href.partition("#")
        resolved = (current_file.parent / path_part).resolve()
        if resolved in self.chapter_map:
            return f"#{self.chapter_map[resolved]}"
        try:
            return resolved.relative_to(DOCS_DIR.resolve()).as_posix()
        except ValueError:
            return raw_href

    def render_inline(self, text: str, current_file: Path) -> str:
        # 1. Protege spans de código inline `...` antes de escapar/formatar
        tokens: List[str] = []

        def _stash(html_snippet: str) -> str:
            idx = len(tokens)
            tokens.append(html_snippet)
            return f"\x00TOK{idx}\x00"

        def _code_repl(m: re.Match[str]) -> str:
            return _stash(f"<code>{escape(m.group(1))}</code>")

        text = re.sub(r"`([^`]+)`", _code_repl, text)

        # 2. Protege imagens inline e links [texto](url)
        def _img_repl(m: re.Match[str]) -> str:
            alt = escape(m.group(1))
            src = escape(self._resolve_img_src(m.group(2).strip(), current_file))
            return _stash(f'<img src="{src}" alt="{alt}" class="inline-img">')

        def _link_repl(m: re.Match[str]) -> str:
            label_raw = m.group(1)
            href = self._resolve_href(m.group(2).strip(), current_file)
            label_html = self._format_emphasis(escape(label_raw))
            target_attr = ' target="_blank" rel="noopener"' if href.startswith(("http://", "https://")) else ""
            return _stash(f'<a href="{escape(href)}"{target_attr}>{label_html}</a>')

        text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _img_repl, text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link_repl, text)

        escaped = escape(text)
        formatted = self._format_emphasis(escaped)

        def _unstash(match: re.Match[str]) -> str:
            return tokens[int(match.group(1))]

        # Pode haver tokens aninhados (ex: código dentro de texto de link já resolvido)
        for _ in range(2):
            formatted = re.sub(r"\x00TOK(\d+)\x00", _unstash, formatted)
        return formatted

    @staticmethod
    def _format_emphasis(text: str) -> str:
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<!\w)\*([^\s*][^*]*?[^\s*]|[^\s*])\*(?!\w)", r"<em>\1</em>", text)
        return text

    def convert_markdown(self, md_text: str, section: DocSection) -> str:
        lines = md_text.replace("\r\n", "\n").split("\n")
        out: List[str] = []
        i = 0
        n = len(lines)
        current_file = section.source_path

        while i < n:
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            # Bloco de código com crases
            m_fence = RE_FENCE.match(line)
            if m_fence:
                lang = m_fence.group(1).strip()
                i += 1
                code_lines: List[str] = []
                while i < n and not RE_FENCE.match(lines[i]):
                    code_lines.append(lines[i])
                    i += 1
                i += 1
                lang_cls = f' class="language-{escape(lang)}"' if lang else ""
                out.append(f"<pre><code{lang_cls}>{escape(chr(10).join(code_lines))}</code></pre>")
                continue

            # Linha horizontal
            if stripped in ("---", "***", "___"):
                out.append("<hr>")
                i += 1
                continue

            # Títulos h1..h4
            m_head = RE_HEADING.match(line)
            if m_head:
                level = len(m_head.group(1))
                title_raw = m_head.group(2).strip()
                hid = f"{section.anchor_id}-{_slugify(title_raw)}" if level > 1 else section.anchor_id
                out.append(
                    f'<h{level} id="{escape(hid)}">{self.render_inline(title_raw, current_file)}</h{level}>'
                )
                i += 1
                continue

            # Imagem isolada como figura
            m_img = RE_IMAGE_LINE.match(stripped)
            if m_img:
                alt = m_img.group(1).strip()
                src = self._resolve_img_src(m_img.group(2).strip(), current_file)
                cap_html = f"<figcaption>{escape(alt)}</figcaption>" if alt else ""
                out.append(
                    f'<figure class="screenshot"><img src="{escape(src)}" alt="{escape(alt)}">{cap_html}</figure>'
                )
                i += 1
                continue

            # Blockquotes e GitHub Alerts (> [!TIP], > [!NOTE], > [!IMPORTANT]...)
            if stripped.startswith(">"):
                bq_lines: List[str] = []
                while i < n and lines[i].strip().startswith(">"):
                    content = re.sub(r"^>\s?", "", lines[i])
                    bq_lines.append(content)
                    i += 1
                out.append(self._render_blockquote(bq_lines, current_file))
                continue

            # Tabelas Markdown
            if stripped.startswith("|") and i + 1 < n and RE_TABLE_SEP.match(lines[i + 1].strip()):
                headers = _split_table_row(lines[i])
                aligns = _parse_alignments(lines[i + 1])
                i += 2
                rows: List[List[str]] = []
                while i < n and lines[i].strip().startswith("|"):
                    rows.append(_split_table_row(lines[i]))
                    i += 1
                out.append(self._render_table(headers, aligns, rows, current_file))
                continue

            # Listas (com suporte a subníveis aninhados)
            if RE_OL_ITEM.match(line) or RE_UL_ITEM.match(line):
                list_lines: List[str] = []
                while i < n:
                    cur = lines[i]
                    if RE_OL_ITEM.match(cur) or RE_UL_ITEM.match(cur):
                        list_lines.append(cur)
                        i += 1
                    elif cur.strip() == "" and i + 1 < n and (
                        RE_OL_ITEM.match(lines[i + 1]) or RE_UL_ITEM.match(lines[i + 1])
                    ):
                        i += 1
                    else:
                        break
                out.append(self._render_list(list_lines, current_file))
                continue

            # Parágrafo padrão
            para_lines: List[str] = []
            while i < n:
                cur = lines[i]
                cs = cur.strip()
                if (
                    not cs
                    or cs in ("---", "***", "___")
                    or cs.startswith(">")
                    or RE_FENCE.match(cur)
                    or RE_HEADING.match(cur)
                    or RE_IMAGE_LINE.match(cs)
                    or RE_OL_ITEM.match(cur)
                    or RE_UL_ITEM.match(cur)
                    or (cs.startswith("|") and i + 1 < n and RE_TABLE_SEP.match(lines[i + 1].strip()))
                ):
                    break
                para_lines.append(cur)
                i += 1

            joined_parts: List[str] = []
            for idx_p, pl in enumerate(para_lines):
                has_br = pl.endswith("  ")
                rendered_pl = self.render_inline(pl.strip(), current_file)
                if has_br and idx_p < len(para_lines) - 1:
                    joined_parts.append(f"{rendered_pl}<br>")
                elif idx_p < len(para_lines) - 1:
                    joined_parts.append(f"{rendered_pl} ")
                else:
                    joined_parts.append(rendered_pl)
            out.append(f"<p>{''.join(joined_parts)}</p>")

        return "\n".join(out)

    def _render_blockquote(self, bq_lines: List[str], current_file: Path) -> str:
        if not bq_lines:
            return ""
        first_m = RE_ALERT_TAG.match(bq_lines[0].strip())
        if first_m:
            kind = first_m.group(1)
            label, icon = ALERT_META.get(kind, (kind.title(), "ℹ️"))
            rest = [first_m.group(2)] if first_m.group(2).strip() else []
            rest.extend(bq_lines[1:])
            body_html = self._render_blockquote_body(rest, current_file)
            return (
                f'<div class="callout callout-{kind.lower()}">'
                f'<div class="callout-title">{icon} {escape(label)}</div>'
                f'<div class="callout-body">{body_html}</div>'
                f"</div>"
            )
        body_html = self._render_blockquote_body(bq_lines, current_file)
        return f"<blockquote>{body_html}</blockquote>"

    def _render_blockquote_body(self, lines: List[str], current_file: Path) -> str:
        items = [ln for ln in lines if ln.strip()]
        if not items:
            return ""
        if all(RE_UL_ITEM.match(ln) or RE_OL_ITEM.match(ln) for ln in items):
            return self._render_list(items, current_file)
        parts: List[str] = []
        for idx, ln in enumerate(items):
            br = "<br>" if (ln.endswith("  ") and idx < len(items) - 1) else (" " if idx < len(items) - 1 else "")
            parts.append(self.render_inline(ln.strip(), current_file) + br)
        return f"<p>{''.join(parts)}</p>"

    def _render_table(
        self,
        headers: List[str],
        aligns: List[str],
        rows: List[List[str]],
        current_file: Path,
    ) -> str:
        th_cells = []
        for idx, h in enumerate(headers):
            al = aligns[idx] if idx < len(aligns) else "left"
            th_cells.append(f'<th style="text-align:{al}">{self.render_inline(h, current_file)}</th>')

        body_rows = []
        for row in rows:
            tds = []
            for idx in range(len(headers)):
                val = row[idx] if idx < len(row) else ""
                al = aligns[idx] if idx < len(aligns) else "left"
                tds.append(f'<td style="text-align:{al}">{self.render_inline(val, current_file)}</td>')
            body_rows.append(f"<tr>{''.join(tds)}</tr>")

        return (
            '<div class="table-wrap"><table>'
            f"<thead><tr>{''.join(th_cells)}</tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody>"
            "</table></div>"
        )

    def _render_list(self, list_lines: List[str], current_file: Path) -> str:
        stack: List[Tuple[int, str, bool]] = []  # (indent, tag, has_open_li)
        html: List[str] = []

        for raw in list_lines:
            m_ol = RE_OL_ITEM.match(raw)
            m_ul = RE_UL_ITEM.match(raw)
            if m_ol:
                indent = len(m_ol.group(1).replace("\t", "    "))
                tag = "ol"
                content = m_ol.group(3).strip()
            elif m_ul:
                indent = len(m_ul.group(1).replace("\t", "    "))
                tag = "ul"
                content = m_ul.group(2).strip()
            else:
                continue

            if not stack:
                html.append(f"<{tag}>")
                stack.append((indent, tag, False))
            elif indent > stack[-1][0]:
                # Subnível aninhado dentro do último <li> aberto
                html.append(f"<{tag}>")
                stack.append((indent, tag, False))
            else:
                while stack and indent < stack[-1][0]:
                    _, prev_tag, has_li = stack.pop()
                    if has_li:
                        html.append("</li>")
                    html.append(f"</{prev_tag}>")

                if stack and stack[-1][1] != tag:
                    cur_indent, prev_tag, has_li = stack.pop()
                    if has_li:
                        html.append("</li>")
                    html.append(f"</{prev_tag}>")
                    html.append(f"<{tag}>")
                    stack.append((cur_indent, tag, False))
                elif stack and stack[-1][2]:
                    html.append("</li>")
                    stack[-1] = (stack[-1][0], stack[-1][1], False)
                elif not stack:
                    html.append(f"<{tag}>")
                    stack.append((indent, tag, False))

            html.append(f"<li>{self.render_inline(content, current_file)}")
            stack[-1] = (stack[-1][0], stack[-1][1], True)

        while stack:
            _, prev_tag, has_li = stack.pop()
            if has_li:
                html.append("</li>")
            html.append(f"</{prev_tag}>")

        return "".join(html)


CSS_STYLES = """
:root {
  --bg: #f6f8fa;
  --surface: #ffffff;
  --ink: #1f2328;
  --muted: #59636e;
  --border: #d0d7de;
  --accent: #0969da;
  --accent-soft: #ddf4ff;
  --code-bg: #f3f4f6;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  padding: 24px 16px 64px;
  font-family: "Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif;
  color: var(--ink);
  background: var(--bg);
  line-height: 1.62;
  font-size: 14.5px;
}
.page-shell {
  max-width: 980px;
  margin: 0 auto;
  background: var(--surface);
  padding: 40px 48px;
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0,0,0,.05);
}
.print-toolbar {
  position: sticky;
  top: 12px;
  z-index: 50;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  max-width: 980px;
  margin: 0 auto 14px;
  padding: 10px 16px;
  background: #0b2e59;
  color: #ffffff;
  border-radius: 8px;
  box-shadow: 0 4px 14px rgba(11,46,89,.22);
}
.print-toolbar span { font-size: 13px; }
.print-btn {
  background: #ffffff;
  color: #0b2e59;
  border: 0;
  border-radius: 6px;
  padding: 7px 14px;
  font-weight: 700;
  cursor: pointer;
}
.print-btn:hover { background: #e8f1fb; }
.chapter-block {
  margin-top: 40px;
  padding-top: 24px;
  border-top: 2px solid var(--border);
}
h1, h2, h3, h4 {
  color: #0b2e59;
  line-height: 1.28;
  break-after: avoid;
  page-break-after: avoid;
}
h1 { font-size: 1.85rem; margin-top: 0; border-bottom: 2px solid #dbe6f2; padding-bottom: 8px; }
h2 { font-size: 1.35rem; margin-top: 26px; border-bottom: 1px solid #eaeef2; padding-bottom: 5px; }
h3 { font-size: 1.12rem; margin-top: 18px; }
h4 { font-size: 1rem; margin-top: 14px; }
p { margin: 0 0 11px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code {
  font-family: Consolas, "Cascadia Mono", monospace;
  background: var(--code-bg);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.9em;
}
pre {
  background: #161b22;
  color: #e6edf3;
  padding: 12px 15px;
  border-radius: 6px;
  overflow-x: auto;
  break-inside: avoid;
}
pre code { background: transparent; color: inherit; padding: 0; font-size: 0.88em; }
.table-wrap { overflow-x: auto; margin: 14px 0; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
  margin: 4px 0 10px;
}
th, td {
  border: 1px solid var(--border);
  padding: 7px 10px;
  vertical-align: top;
}
th { background: #eef4fb; color: #0b2e59; font-weight: 600; }
tbody tr:nth-child(even) { background: #fafbfd; }
tr, blockquote, .callout, figure.screenshot {
  break-inside: avoid;
  page-break-inside: avoid;
}
figure.screenshot {
  margin: 16px auto;
  text-align: center;
  background: #fafbfd;
  border: 1px solid #e1e6eb;
  border-radius: 8px;
  padding: 10px;
}
figure.screenshot img {
  max-width: 100%;
  max-height: 540px;
  height: auto;
  border-radius: 4px;
}
figure.screenshot figcaption {
  margin-top: 6px;
  font-size: 0.84rem;
  color: var(--muted);
}
blockquote {
  margin: 14px 0;
  padding: 8px 14px;
  border-left: 4px solid var(--border);
  background: #f9fafb;
  color: #3b434b;
}
.callout {
  margin: 14px 0;
  padding: 10px 14px;
  border-left: 4px solid var(--accent);
  background: var(--accent-soft);
  border-radius: 0 6px 6px 0;
}
.callout-tip { border-left-color: #1a7f37; background: #dafbe1; }
.callout-important { border-left-color: #8250df; background: #fbefff; }
.callout-warning { border-left-color: #9a6700; background: #fff8c5; }
.callout-caution { border-left-color: #cf222e; background: #ffebe9; }
.callout-title { font-weight: 700; margin-bottom: 4px; }
.callout-body p:last-child { margin-bottom: 0; }
ul, ol { margin: 8px 0 12px 22px; padding: 0; }
li { margin-bottom: 4px; }
hr { border: 0; border-top: 1px solid var(--border); margin: 20px 0; }

@page {
  size: A4;
  margin: 15mm 14mm;
}
@media print {
  body { background: #ffffff; padding: 0; font-size: 11pt; }
  .print-toolbar { display: none !important; }
  .page-shell { max-width: none; border: 0; box-shadow: none; padding: 0; }
  .chapter-block {
    break-before: page;
    page-break-before: always;
    margin-top: 0;
    padding-top: 0;
    border-top: 0;
  }
  a { color: #0b2e59; text-decoration: none; }
  figure.screenshot img { max-height: 155mm; }
}
"""


def collect_sections() -> List[DocSection]:
    sections: List[DocSection] = [
        DocSection(
            anchor_id="indice",
            title="Índice Geral e Visão de Início",
            source_path=MANUAL_INDEX.resolve(),
            chapter_num=None,
        )
    ]
    for path in sorted(MANUAL_CHAPTERS_DIR.glob("[0-9][0-9]_*.md")):
        num = int(path.name[:2])
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        title = first_line.lstrip("# ").strip()
        sections.append(
            DocSection(
                anchor_id=f"cap-{num:02d}",
                title=title,
                source_path=path.resolve(),
                chapter_num=num,
            )
        )
    return sections


def build_manual_html(output_path: Path, embed_images: bool = False) -> Path:
    sections = collect_sections()
    chapter_map = {sec.source_path: sec.anchor_id for sec in sections}
    converter = ManualConverter(chapter_map=chapter_map, embed_images=embed_images)

    body_blocks: List[str] = []
    for idx, sec in enumerate(sections):
        md_text = sec.source_path.read_text(encoding="utf-8")
        rendered = converter.convert_markdown(md_text, sec)
        if idx == 0:
            body_blocks.append(f'<section id="{sec.anchor_id}" class="intro-block">\n{rendered}\n</section>')
        else:
            body_blocks.append(f'<section id="{sec.anchor_id}" class="chapter-block">\n{rendered}\n</section>')

    full_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Manual Completo do Usuário — Sistema de Refeitório (v1.3.0)</title>
  <style>{CSS_STYLES}</style>
</head>
<body>
  <div class="print-toolbar">
    <span><strong>Manual Completo (v1.3.0)</strong> — Para salvar em PDF, clique no botão ao lado ou use <code>Ctrl+P</code> (marque <em>Gráficos de segundo plano</em>).</span>
    <button class="print-btn" onclick="window.print()">🖨️ Salvar em PDF / Imprimir</button>
  </div>
  <main class="page-shell">
    {"".join(body_blocks)}
  </main>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_html, encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exporta o Manual do Usuário completo (Markdown) para um único HTML pronto para salvar em PDF."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Caminho do HTML de saída (padrão: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--embed-images",
        action="store_true",
        help="Embute as imagens PNG em Base64 dentro do próprio HTML (arquivo único portátil).",
    )
    args = parser.parse_args()
    out = build_manual_html(args.output, embed_images=args.embed_images)
    size_kb = out.stat().st_size / 1024
    print(f"Manual HTML gerado com sucesso: {out} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()

