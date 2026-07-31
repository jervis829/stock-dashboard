#!/usr/bin/env python3
"""
为每只股票生成详情页
"""
import json
import os
from datetime import date
from pathlib import Path

WEB_DIR = Path(__file__).parent
DATA_FILE = WEB_DIR / "data" / "watchlist.json"
DATA_DATE = date.today().isoformat()

def render_stock_detail(stock):
    """渲染单只股票的详情页 HTML"""
    change_color = "text-red" if stock["change_pct"] > 0 else ("text-green" if stock["change_pct"] < 0 else "text-gray")
    arrow = "▲" if stock["change_pct"] > 0 else ("▼" if stock["change_pct"] < 0 else "—")
    change_text = f"{arrow} {abs(stock['change_pct']):.2f}%"

    action_class = stock.get("action", "hold")
    action_text = {
        "buy_zone": "🟦 可买 - 当前价格已接近或进入买入区间",
        "hold": "🟩 持有 - 价格在合理区间内，继续观察",
        "danger_zone": "🟥 风险 - 价格已接近或跌破止损价，建议关注/剔除",
        "observe": "🟨 观察 - 暂不操作，等待更多信号"
    }.get(action_class, "🟩 持有")

    health_label = {"healthy": "健康", "warning": "警示", "danger": "危险"}.get(stock["health"], "健康")
    health_color = {"healthy": "text-green", "warning": "text-yellow", "danger": "text-red"}.get(stock["health"], "text-green")

    # 计算距各价格距离
    dist_to_buy = ((stock["price"] - stock["buy_low"]) / stock["price"] * 100)
    dist_to_sell = ((stock["sell_high"] - stock["price"]) / stock["price"] * 100)
    dist_to_stop = ((stock["price"] - stock["stop_loss"]) / stock["price"] * 100)

    pe_text = '<span class="text-red">亏损</span>' if stock["pe_ttm"] < 0 else f'{stock["pe_ttm"]:.2f}'

    # 概念标签
    concept_html = " ".join(f'<span class="tag">{c}</span>' for c in stock["concept"])

    # 风险列表
    risk_html = "\n".join(f'<li>{r}</li>' for r in stock["risks"])

    # 标签
    tags_html = "\n          ".join(f'<span class="tag">{t}</span>' for t in stock["tags"])

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{stock['name']} ({stock['full_code']}) - 自选股详情</title>
  <link rel="stylesheet" href="css/style.css">
</head>
<body>
  <header class="header">
    <h1>📈 {stock['name']}</h1>
    <div class="header-info">
      <span>{stock['full_code']}</span>
      <span>数据日期: {DATA_DATE}</span>
    </div>
  </header>

  <nav class="nav">
    <a href="index.html">总览</a>
    <a href="dashboard.html">监控仪表盘</a>
  </nav>

  <div class="container" id="content">
    <a href="index.html" class="back-link">← 返回自选股总览</a>
    <div class="detail-header">
      <div class="left">
        <h1>{stock['name']}</h1>
        <div class="meta">
          <span>{stock['full_code']}</span>
          <span>·</span>
          <span>{stock['market']}</span>
          <span>·</span>
          <span>{stock['sector']}</span>
        </div>
        <div style="margin-top:12px">
          {tags_html}
        </div>
      </div>
      <div class="right">
        <div class="price">{stock['price']:.2f}</div>
        <div class="change-pct {change_color}">{change_text}</div>
        <div style="margin-top:8px; font-size:13px; color:#888">
          昨收 {stock['prev_close']:.2f} · 5日 {stock['change_5d']:+.2f}% · 20日 {stock['change_20d']:+.2f}%
        </div>
      </div>
    </div>

    <div class="action-banner {action_class}">
      <span>{action_text}</span>
    </div>

    <div class="section">
      <h2>💰 交易区间</h2>
      <div class="detail-grid">
        <div class="detail-item">
          <div class="label">买入下沿</div>
          <div class="value text-blue">{stock['buy_low']:.2f}</div>
          <div class="text-gray" style="font-size:12px; margin-top:4px">距现价 {dist_to_buy:+.1f}%</div>
        </div>
        <div class="detail-item">
          <div class="label">当前价格</div>
          <div class="value">{stock['price']:.2f}</div>
        </div>
        <div class="detail-item">
          <div class="label">卖出上沿</div>
          <div class="value text-green">{stock['sell_high']:.2f}</div>
          <div class="text-gray" style="font-size:12px; margin-top:4px">距现价 {dist_to_sell:+.1f}%</div>
        </div>
        <div class="detail-item">
          <div class="label">止损价</div>
          <div class="value text-red">{stock['stop_loss']:.2f}</div>
          <div class="text-gray" style="font-size:12px; margin-top:4px">距现价 {dist_to_stop:+.1f}%</div>
        </div>
      </div>
    </div>

    <div class="section">
      <h2>📊 关键指标</h2>
      <div class="detail-grid">
        <div class="detail-item">
          <div class="label">综合评分</div>
          <div class="value text-blue">{stock['score']}/100</div>
        </div>
        <div class="detail-item">
          <div class="label">7日涨停</div>
          <div class="value text-red">{stock['limit_up_count_7d']} 次</div>
          <div class="text-gray" style="font-size:12px; margin-top:4px">{', '.join(stock['limit_up_dates'])}</div>
        </div>
        <div class="detail-item">
          <div class="label">PE(TTM)</div>
          <div class="value">{pe_text}</div>
        </div>
        <div class="detail-item">
          <div class="label">PB</div>
          <div class="value">{stock['pb']:.2f}</div>
        </div>
        <div class="detail-item">
          <div class="label">总市值</div>
          <div class="value">{stock['market_cap']:.0f} 亿</div>
        </div>
        <div class="detail-item">
          <div class="label">换手率</div>
          <div class="value">{stock['turnover_pct']:.2f}%</div>
        </div>
      </div>
    </div>

    <div class="section">
      <h2>💎 基本面分析</h2>
      <p>{stock['analysis']['fundamental']}</p>
      <h3>板块效应</h3>
      <p>{stock['analysis']['sector']}</p>
      <h3>估值水平</h3>
      <p>{stock['analysis']['valuation']}</p>
    </div>

    <div class="section">
      <h2>📈 技术面分析</h2>
      <p>{stock['analysis']['technical']}</p>
    </div>

    <div class="section">
      <h2>🏷️ 概念标签</h2>
      <p>{concept_html}</p>
    </div>

    <div class="section">
      <h2>⚠️ 风险提示</h2>
      <ul class="risk-list">
        {risk_html}
      </ul>
    </div>

    <div class="section">
      <h2>🎯 操作建议</h2>
      <div class="detail-grid">
        <div class="detail-item">
          <div class="label">评级</div>
          <div class="value {('text-green' if stock['score'] >= 75 else ('text-yellow' if stock['score'] >= 60 else 'text-red'))}">{stock['rating']}</div>
        </div>
        <div class="detail-item">
          <div class="label">健康度</div>
          <div class="value {health_color}">{health_label}</div>
        </div>
        <div class="detail-item">
          <div class="label">操作</div>
          <div class="value text-blue">{{'可买' if action_class == 'buy_zone' else ('持有' if action_class == 'hold' else ('关注/剔除' if action_class == 'danger_zone' else '观察'))}}</div>
        </div>
      </div>
      <p style="margin-top:16px">{action_text}</p>
    </div>
  </div>

  <footer>
    <p>详情页 · {stock['name']} ({stock['full_code']}) · 数据日期 {DATA_DATE}</p>
    <p style="margin-top:8px; color:#ff4757">⚠️ 本监控仅供参考，不构成个人投资建议</p>
  </footer>
</body>
</html>
"""
    return html


# 详情页改为轻量 stub：运行时由 js/main.js 的 initStockDetail() 从 watchlist.json 渲染，避免重复内容、减小体积
STUB_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>股票详情 - 自选股监控</title>
  <link rel="stylesheet" href="css/style.css">
</head>
<body>
  <header class="header">
    <h1>📈 股票详情</h1>
    <div class="header-info"><span>数据日期: {date}</span></div>
  </header>
  <nav class="nav">
    <a href="index.html">总览</a>
    <a href="dashboard.html">监控仪表盘</a>
  </nav>
  <div class="container" id="content"></div>
  <script src="js/main.js"></script>
  <script>initStockDetail('{code}');</script>
</body>
</html>
"""

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>自选股监控 - 每日复盘 ({date})</title>
  <link rel="stylesheet" href="css/style.css">
</head>
<body>
  <header class="header">
    <h1>📈 自选股监控</h1>
    <div class="header-info">
      <span>数据日期: {date}</span>
      <span id="update-time">--:--:--</span>
      <span>持仓 <span id="stock-count">{count}</span> 只</span>
    </div>
  </header>

  <nav class="nav">
    <a href="index.html" class="active">总览</a>
    <a href="dashboard.html">监控仪表盘</a>
    <a href="data/watchlist.json" target="_blank">数据源</a>
    <a href="https://github.com" target="_blank">每日复盘脚本</a>
  </nav>

  <div class="container">
    <!-- 概览统计 -->
    <div class="overview-grid" id="overview"></div>

    <!-- 板块分布 -->
    <div class="section">
      <h2>📊 板块分布</h2>
      <div class="sector-summary" id="sector-summary"></div>
    </div>

    <!-- 今日触发信号 -->
    <div id="trigger-list"></div>

    <!-- 自选股列表 -->
    <div class="section">
      <h2>💼 自选股列表 ({count} 只)</h2>
      <p class="text-gray" style="margin-bottom:16px; font-size:13px">
        点击任意卡片进入详情页。每只股票包含：交易区间、关键技术面、基本面、风险提示
      </p>
      <div class="stock-grid" id="stock-grid"></div>
    </div>

    <footer>
      <p>本监控网页由每日复盘脚本自动生成 · 数据来源: <a href="data/watchlist.json" style="color:#00d4ff">watchlist.json</a></p>
      <p style="margin-top:8px">监控规则：跌破止损 / 连续 2 日跌停 / 业绩雷 / 7 日无涨停 → 触发剔除</p>
      <p style="margin-top:8px; color:#ff4757">⚠️ 本报告仅供参考，不构成个人投资建议</p>
    </footer>
  </div>

  <script src="js/main.js"></script>
  <script>initIndex();</script>
</body>
</html>
"""


def write_index_html(data_date, count):
    """根地址 index.html 直接跳转到监控仪表盘 dashboard.html（保持链接稳定）。

    这样 GitHub Pages 的根 URL 始终打开应用，而不是总览页；
    且每次重新生成也不会把根地址覆盖回总览。
    """
    html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-CN">\n'
        '<head>\n'
        '  <meta charset="UTF-8">\n'
        '  <meta http-equiv="refresh" content="0; url=dashboard.html">\n'
        '  <link rel="canonical" href="dashboard.html">\n'
        '  <title>正在跳转至自选股监控仪表盘…</title>\n'
        '</head>\n'
        '<body>\n'
        '  <p>正在跳转至 <a href="dashboard.html">自选股监控仪表盘</a> …</p>\n'
        '</body>\n'
        '</html>\n'
    )
    (WEB_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"✓ index.html -> dashboard.html (redirect)")


def patch_dashboard_date(data_date):
    """修正 dashboard.html 中写死的数据日期。"""
    dash = WEB_DIR / "dashboard.html"
    if not dash.exists():
        return
    text = dash.read_text(encoding="utf-8")
    new_text = __import__("re").sub(
        r'(id="data-date">)[^<]*(</strong>)',
        lambda m: f"{m.group(1)}{data_date}{m.group(2)}",
        text,
    )
    if new_text != text:
        dash.write_text(new_text, encoding="utf-8")
        print(f"✓ dashboard.html 日期修正为 {data_date}")


def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        stocks = json.load(f)

    for stock in stocks:
        out_path = WEB_DIR / f"stock_{stock['code']}.html"
        out_path.write_text(STUB_TEMPLATE.format(code=stock["code"], date=DATA_DATE), encoding="utf-8")
        print(f"✓ {out_path.name}")

    # 同步生成 index.html（修复写死的日期/数量）
    write_index_html(DATA_DATE, len(stocks))
    # 修正 dashboard.html 中的数据日期
    patch_dashboard_date(DATA_DATE)

    print(f"\n生成完成：{len(stocks)} 个详情页 + index.html")


if __name__ == "__main__":
    main()
