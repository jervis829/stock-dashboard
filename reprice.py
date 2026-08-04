#!/usr/bin/env python3
"""
动态买点重估引擎 (Dynamic Buy-point Re-estimation)

设计原则（见每日复盘「动态买点重估」方案）：
- 买点重估由「价格位置 + 逻辑状态」共同决定，而非现价单独决定
- 阈值驱动（event-driven）：仅跨过 15% / 30% / -15% 才改变状态，平时不动
- 向上踏空（涨离买点）与向下破位（跌离买点）分开处理
- 已接近卖出上沿的，生成移动止盈（trailing stop）建议
- 脚本只建议、不改价：绝不修改 buy_low / sell_high / stop_loss 原值

写入 watchlist.json 的字段：
  gap_pct                   涨离买点百分比（正=涨离/踏空，负=跌离/破位）
  entry_type               wait / reprice / missed / review_downbreak
  price_status             文本状态描述
  buy_low_base             原始买点锚（首次录入值，重定价时保留作参考）
  reprice_date             最近一次状态变更日期（wait 状态保留历史）
  reprice_reason           状态判定理由
  trailing_stop_suggestion 移动止盈建议价（接近卖点时非空，否则 null）
"""
import json
from datetime import date
from pathlib import Path

WEB_DIR = Path(__file__).parent
DATA_FILE = WEB_DIR / "data" / "watchlist.json"

THRESH_WATCH = 15.0        # 轻微踏空上限（维持买点）
THRESH_DEEP = 30.0         # 深度踏空上限
THRESH_BREAK = -15.0       # 向下破位下限
TRAIL_TRIGGER = 0.85       # 距卖出上沿 ≤15% 触发移动止盈
TRAIL_BUFFER = 0.92        # 移动止盈价 = 现价 * 0.92（回撤 8% 离场）


def compute_entry(stock):
    """根据涨离幅度与逻辑健康度判定 entry_type。"""
    price = float(stock["price"])
    buy_low = float(stock["buy_low"])
    health = stock.get("health", "healthy")
    gap = (price - buy_low) / buy_low * 100

    # 向下破位：跌离买点 >15%
    if gap < THRESH_BREAK:
        return {
            "entry_type": "review_downbreak",
            "price_status": "破位（跌离买点>15%）",
            "reprice_reason": "现价已大幅跌离买点下方，原买点或逻辑失效，触发剔除评审（确认是否破位深跌）",
        }

    # 低于或等于买点：原买点有效
    if gap <= 0:
        return {
            "entry_type": "wait",
            "price_status": "低于买点，维持等回踩",
            "reprice_reason": "现价在买点下方或附近，原买点有效，维持等待回踩",
        }

    # 0 < gap <= 15：轻微踏空，纪律优先不追
    if gap <= THRESH_WATCH:
        return {
            "entry_type": "wait",
            "price_status": f"轻微踏空（+{gap:.1f}%）",
            "reprice_reason": "涨离买点未超15%，维持原买点观察，不重估（纪律优先，不追高）",
        }

    # gap > 15：明显/深度踏空
    # 板块或逻辑偏弱（health=warning）→ 不追，移出待买队列
    if health == "warning":
        return {
            "entry_type": "missed",
            "price_status": f"踏空放弃（+{gap:.1f}%，板块偏弱）",
            "reprice_reason": "明显踏空且板块/逻辑偏弱（health=warning），不追高，移出待买队列（逻辑未坏仅价位不合适）",
        }

    # healthy + gap > 15：触发重新定价评审
    if gap <= THRESH_DEEP:
        return {
            "entry_type": "reprice",
            "price_status": f"明显踏空（+{gap:.1f}%）",
            "reprice_reason": "明显踏空，触发重新定价评审：基于技术支撑位设新买点，止损同步上移，仓位下调；估值锚型须谨慎",
        }
    return {
        "entry_type": "reprice",
        "price_status": f"深度踏空（+{gap:.1f}%）",
        "reprice_reason": "深度踏空，原买点逻辑失效；若板块仍强则重定价（新支撑位+止损上移+仓位下调），否则标 missed",
    }


def compute_trailing(stock):
    """接近卖出上沿时给出移动止盈建议价。"""
    price = float(stock["price"])
    sell_high = float(stock["sell_high"])
    if price >= sell_high * TRAIL_TRIGGER:
        return round(price * TRAIL_BUFFER, 2)
    return None


def update_watchlist(data_file=DATA_FILE, today=None):
    """重估并写回 watchlist.json（不改 buy_low/sell_high/stop_loss）。"""
    today = today or date.today().isoformat()
    with open(data_file, "r", encoding="utf-8") as f:
        stocks = json.load(f)

    for s in stocks:
        res = compute_entry(s)
        if "buy_low_base" not in s:
            s["buy_low_base"] = float(s["buy_low"])
        s["gap_pct"] = round(
            (float(s["price"]) - float(s["buy_low"])) / float(s["buy_low"]) * 100, 2
        )
        s["entry_type"] = res["entry_type"]
        s["price_status"] = res["price_status"]
        s["reprice_reason"] = res["reprice_reason"]
        s["trailing_stop_suggestion"] = compute_trailing(s)
        # 仅状态变更（非 wait）时刷新 reprice_date；wait 保留历史日期
        if res["entry_type"] != "wait":
            s["reprice_date"] = today

    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    return stocks


def build_report(stocks, today=None):
    """生成「自选股体检（踏空/破位/止盈）」Markdown 章节。"""
    today = today or date.today().isoformat()
    groups = {"reprice": [], "missed": [], "break": [], "trailing": [], "watch_up": []}
    for s in stocks:
        et = s.get("entry_type", "wait")
        if et == "reprice":
            groups["reprice"].append(s)
        elif et == "missed":
            groups["missed"].append(s)
        elif et == "review_downbreak":
            groups["break"].append(s)
        if s.get("trailing_stop_suggestion"):
            groups["trailing"].append(s)
        if et == "wait" and s.get("gap_pct", 0) > 0:
            groups["watch_up"].append(s)

    def row(s):
        ts = s.get("trailing_stop_suggestion")
        ts_txt = f"｜移动止盈建议 {ts}" if ts else ""
        return (
            f"| {s['name']}({s['full_code']}) | {s.get('gap_pct', 0):+.1f}% | "
            f"{s.get('price_status', '')} | {s['buy_low']} | {s['price']} | "
            f"{s.get('reprice_reason', '')}{ts_txt} |"
        )

    L = [f"## 自选股体检（动态买点重估 · {today}）", ""]
    L.append("> 阈值驱动重估：涨离≤15%维持买点；15~30%重新定价评审；>30%深度踏空；跌离>15%破位评审。脚本只建议，不改 buy_low。")
    L.append("")
    L.append("### 🔄 重新定价候选（entry_type=reprice）")
    if groups["reprice"]:
        L.append("| 标的 | 涨离买点 | 状态 | 原买点 | 现价 | 建议 |")
        L.append("|---|---|---|---|---|---|")
        L += [row(s) for s in groups["reprice"]]
    else:
        L.append("无")
    L.append("")
    L.append("### 🚫 踏空放弃（entry_type=missed，板块偏弱不追）")
    if groups["missed"]:
        L.append("| 标的 | 涨离买点 | 状态 | 原买点 | 现价 | 建议 |")
        L.append("|---|---|---|---|---|---|")
        L += [row(s) for s in groups["missed"]]
    else:
        L.append("无")
    L.append("")
    L.append("### 🔻 破位评审（entry_type=review_downbreak）")
    if groups["break"]:
        L.append("| 标的 | 涨离买点 | 状态 | 原买点 | 现价 | 建议 |")
        L.append("|---|---|---|---|---|---|")
        L += [row(s) for s in groups["break"]]
    else:
        L.append("无")
    L.append("")
    L.append("### 🎯 移动止盈提醒（接近卖出上沿）")
    if groups["trailing"]:
        L.append("| 标的 | 现价 | 卖出上沿 | 移动止盈建议 |")
        L.append("|---|---|---|---|")
        for s in groups["trailing"]:
            L.append(f"| {s['name']}({s['full_code']}) | {s['price']} | {s['sell_high']} | {s['trailing_stop_suggestion']} |")
    else:
        L.append("无")
    L.append("")
    L.append("### 👀 维持观察（轻微踏空≤15%）")
    L.append(
        "、".join(f"{s['name']}({s.get('gap_pct', 0):+.1f}%)" for s in groups["watch_up"])
        if groups["watch_up"] else "无"
    )
    L.append("")
    L.append("---")
    L.append("")
    return "\n".join(L)


def main():
    stocks = update_watchlist()
    report = build_report(stocks)
    out = WEB_DIR / "reprice_report.md"
    out.write_text(report, encoding="utf-8")
    print(f"✓ reprice 完成：{len(stocks)} 只，报告 -> {out.name}")
    for s in stocks:
        print(f"  {s['name']:6s} gap={s.get('gap_pct', 0):+6.1f}%  {s.get('entry_type'):16s} {s.get('price_status')}")


if __name__ == "__main__":
    main()
