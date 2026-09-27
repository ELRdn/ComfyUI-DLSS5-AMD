#!/usr/bin/env python3
"""Optional offline documentation renderer (requires mistune 3, not node runtime)."""
from __future__ import annotations
import html
import json
from pathlib import Path
import mistune

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    render = mistune.create_markdown(escape=True, plugins=['table'])
    tests = json.loads((ROOT / 'evidence/test-summary.json').read_text())
    sections = [('report', '調査・実装レポート', 'REPORT_ja.md'),
                ('roadmap', '完了条件つきロードマップ', 'ROADMAP.md'),
                ('sources', '一次資料・出所', 'docs/SOURCES.md')]
    articles = []
    for ident, title, file in sections:
        body = render((ROOT / file).read_text())
        articles.append(f'<section class="chapter" id="{ident}"><div class="kicker">{html.escape(title)}</div>{body}</section>')
    page = '''<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'">
<title>ComfyUI × AMD Neural Rendering — 調査・実装報告</title>
<style>
:root{color-scheme:light;--ink:#182238;--muted:#536179;--paper:#f3f5fa;--line:#dbe1ef;--accent:#5745ca}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:system-ui,-apple-system,"Noto Sans CJK JP","Yu Gothic",sans-serif;line-height:1.85;font-size:16px}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px}header{background:#151c30;color:#fff;padding:60px max(24px,calc((100vw - 1120px)/2)) 42px}
header .eyebrow{color:#c5b9ff;font-weight:700;letter-spacing:.15em;font-size:12px}header h1{font-size:clamp(26px,4.4vw,48px);line-height:1.35;letter-spacing:-.03em;margin:16px 0}header p{max-width:800px;color:#d5dbec}
nav{display:flex;gap:24px;flex-wrap:wrap;margin-top:28px}nav a{color:#e3ddff;font-size:14px}.wrap{max-width:1120px;margin:auto;padding:0 24px 80px}
.status{background:#fff6dc;border:1px solid #eacb72;border-radius:12px;padding:20px 24px;margin:30px 0;color:#503c11}.stats{display:flex;flex-wrap:wrap;gap:12px;margin:24px 0}.stat{flex:1;min-width:170px;background:#fff;border:1px solid var(--line);padding:18px 22px;border-radius:12px}.stat strong{display:block;font-size:30px;line-height:1.25}.stat span{font-size:13px;color:var(--muted)}
.chapter{background:#fff;border:1px solid var(--line);border-radius:16px;margin-top:28px;padding:clamp(22px,4vw,52px);overflow-wrap:anywhere}.kicker{color:var(--accent);font-size:12px;font-weight:700;letter-spacing:.06em;margin-bottom:24px}
h1,h2,h3{line-height:1.5;letter-spacing:-.02em;scroll-margin-top:24px}h1{font-size:30px;margin-top:0}h2{font-size:24px;margin-top:48px;padding-top:20px;border-top:1px solid var(--line)}h3{font-size:19px;margin-top:28px}p{margin:16px 0}li{margin:6px 0}pre{background:#f2f4fa;border:1px solid var(--line);border-radius:8px;padding:20px;overflow:auto;line-height:1.6;font-size:13px}code{font-family:ui-monospace,Consolas,monospace;font-size:.9em}p code,td code{background:#f1f2f9;padding:2px 5px;border-radius:3px}
table{display:block;width:100%;overflow-x:auto;border-collapse:collapse;margin:22px 0;font-size:14px}th,td{border:1px solid var(--line);padding:12px 14px;vertical-align:top;min-width:140px}th{background:#edeafa;color:#302864;text-align:left}hr{border:0;border-top:1px solid var(--line);margin:32px 0}blockquote{border-left:4px solid var(--accent);margin-left:0;padding:0 20px;color:var(--muted)}footer{color:var(--muted);font-size:13px;padding:30px 0}
@media(max-width:600px){body{font-size:15px}header{padding:36px 24px}h1{font-size:25px}h2{font-size:21px}.wrap{padding:0 14px 40px}.chapter{padding:22px 18px}.stat{min-width:130px}.status{padding:18px}nav{gap:14px}}
@media print{body{background:#fff}header{padding:20px;color:#111;background:#fff}header p,header .eyebrow,nav a{color:#333}.wrap{padding:0}.chapter{border:0;padding:0;break-before:page}a{color:#222}pre,table{overflow:visible}h2,h3{break-after:avoid}.stats,.status{break-inside:avoid}}
</style></head><body><header><div class="eyebrow">RESEARCH + IMPLEMENTATION / 2026.09.25</div>
<h1>ComfyUI × AMD<br>Neural Rendering</h1><p>RX 9070 XT 向けの接続基盤、調査結果、実装証拠、そして実機検証に進むためのロードマップ。</p>
<nav><a href="#report">調査・実装</a><a href="#roadmap">ロードマップ</a><a href="#sources">一次資料</a></nav></header><main class="wrap">
<div class="status"><strong>初回スナップショット：2026-09-25 / 開発用ブリッジ 0.1.0a1</strong><br>以下の CPU テスト件数と未検証項目は初回納品時点の記録です。後日の RX 9070 XT 実機結果と現在の導入手順は README.md / README.jp.md と docs/TESTING.md を参照してください。外部 DLL・モデルは同梱していません。</div>
'''
    page += f'<div class="stats"><div class="stat"><strong>{tests["tests"]}</strong><span>初回自動テスト / failure {tests["failures"]} / skip {tests["skipped"]}</span></div><div class="stat"><strong>7</strong><span>初回の ComfyUI ノード</span></div><div class="stat"><strong>3</strong><span>初回のサンプル workflow ＋ API 形式</span></div><div class="stat"><strong>当時未検証</strong><span>実 GPU 推論・品質</span></div></div>'
    page += ''.join(articles)
    page += '<footer>オフライン閲覧用。外部フォント・画像・解析スクリプトは読み込みません。コードと実行証拠は同じ ZIP 内にあります。</footer></main></body></html>'
    (ROOT / 'REPORT.html').write_bytes(page.encode('utf-8'))


if __name__ == '__main__':
    main()
