#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全量涨停筛查引擎 (screen.py)
============================
建立于 2026-08-05，用于修复每日复盘流程的两个结构性缺陷：

缺陷1 · 数据源缺口
    旧流程只取 4 个榜单（连板天数40 / 封单量40 / 主力净流入30 / 连跌20），
    对「首板 + 封单不大 + 中大市值」的标的存在三重盲区。
    → 新流程直接用 westock-tool filter 扫全市场封板涨停股，无遗漏。

缺陷2 · 板块矩阵靠预设
    旧流程人工列举 7 个板块打分，当日真实活跃主线（如玻纤电子布）不在矩阵里，
    「板块<70不选股」这道闸门直接扼杀了打分机会。
    → 新流程由当日涨停分布 + sector ranking 反推板块，矩阵是数据驱动的。

硬性条件（机械可判，逐条记录剔除原因，便于复盘审计）
    A. 当日封板涨停      ClosePrice >= PriceCeiling
    B. 站上10日线        ClosePrice >  MA_10        <- 2026-08-05 用户新增
    C. 股价 < 150
    D. 剔除 ST / *ST / 退市
    E. 剔除 科创板 688xxx / 北交所 8xxxxx,4xxxxx
    F. 剔除 次新股（上市 < 60 天）
    G. 剔除 连续涨停 >= 4 板
    H. 剔除 亏损（PE_TTM <= 0）/ 单年归母净利同比 < -50%

输出
    web/data/candidates.json   结构化候选池 + 剔除明细
    web/screen_report.md       人读版筛查报告（供每日复盘引用）
"""

import json
import subprocess
import sys
import os
import time
from datetime import datetime, date

TOOL = "/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources/builtin-skills/westock-tool"
DATA = "/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources/builtin-skills/westock-data"
NODE = "/Users/apple/.workbuddy/binaries/node/versions/22.22.2/bin/node"

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(BASE, "data", "candidates.json")
OUT_MD = os.path.join(BASE, "screen_report.md")

MAX_PRICE = 150.0
MIN_LISTED_DAYS = 60
MAX_LIMITUP_DAYS = 4          # >=4 板剔除
MIN_NP_YOY = -50.0            # 单年归母净利同比下限
STRONG_SECTOR_MIN_LIMITUPS = 3  # 池内涨停家数达此值即视为当日活跃板块


def run(cwd, args, timeout=180):
    """执行 skill CLI，返回 stdout 文本；失败返回 None。"""
    try:
        r = subprocess.run(
            [NODE, "scripts/index.js"] + args,
            cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        if r.returncode != 0:
            print(f"[WARN] 命令失败 {args}: {r.stderr[:200]}", file=sys.stderr)
            return None
        return r.stdout
    except subprocess.TimeoutExpired:
        print(f"[WARN] 命令超时 {args}", file=sys.stderr)
        return None


def run_json(cwd, args, timeout=180):
    out = run(cwd, args, timeout)
    if not out:
        return None
    txt = out.strip()
    start = min([i for i in (txt.find("["), txt.find("{")) if i >= 0], default=-1)
    if start < 0:
        return None
    try:
        return json.loads(txt[start:])
    except json.JSONDecodeError:
        print(f"[WARN] JSON 解析失败 {args}", file=sys.stderr)
        return None


def num(v):
    """安全转 float；'-' / None / '' 返回 None（标记 [MISSING]）。"""
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "--", "None", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------- 1. 全量涨停池
def fetch_limitup_pool():
    """A+B：当日封板涨停 且 站上10日线。这是唯一的入池口径。"""
    expr = "intersect([ClosePrice >= PriceCeiling, ClosePrice > MA_10])"
    rows = run_json(TOOL, ["filter", expr, "--limit", "400", "--raw"]) or []
    pool = {}
    for r in rows:
        code = r.get("code")
        if not code:
            continue
        pool[code] = {
            "code": code,
            "name": r.get("name", ""),
            "close": num(r.get("ClosePrice")),
            "ma10": num(r.get("MA_10")),
            "change_pct": num(r.get("ChangePCT")),
        }
    return pool


CORE = "ClosePrice >= PriceCeiling, ClosePrice > MA_10"


def _enrich_query(extra_conds, field_map):
    """
    单字段组富集查询。
    ⚠️ 关键教训（2026-08-05）：把多个财报字段塞进同一个 intersect 会**静默丢行**
    （实测 103 → 42），导致有数据的股票被误判为「字段缺失」进而误杀。
    因此每组字段单独查询，再对主池做左连接。
    """
    expr = f"intersect([{CORE}, {extra_conds}])"
    rows = run_json(TOOL, ["filter", expr, "--limit", "400", "--raw"]) or []
    out = {}
    for r in rows:
        code = r.get("code")
        if not code:
            continue
        out[code] = {k: num(r.get(src)) for k, src in field_map.items()}
    return out


def fetch_enriched():
    """
    分组查询 → 左连接。返回 (字段字典, 确认亏损代码集合)。
    区分「亏损」与「数据缺失」：前者是硬性剔除，后者只能标记待核验，不得自动剔除。
    """
    merged = {}

    # 组1：估值 + 市值 + 资金（盈利股）
    for c, v in _enrich_query(
            "TotalMV > 0, PE_TTM > 0, PB > 0, MainNetFlow > -1000000000000",
            {"pe_ttm": "PE_TTM", "pb": "PB", "total_mv": "TotalMV",
             "main_net": "MainNetFlow"}).items():
        merged.setdefault(c, {}).update(v)

    # 组2：确认亏损（PE_TTM < 0）——与「查不到」严格区分
    loss = set()
    for c, v in _enrich_query("PE_TTM < 0", {"pe_ttm": "PE_TTM"}).items():
        loss.add(c)
        merged.setdefault(c, {}).update(v)

    # 组3：归母净利同比（单独查，避免丢行）
    for c, v in _enrich_query("NPParentCompanyYOY > -100000",
                              {"np_yoy": "NPParentCompanyYOY"}).items():
        merged.setdefault(c, {}).update(v)

    # 组4：市值兜底（部分股票组1未覆盖）
    for c, v in _enrich_query("TotalMV > 0", {"total_mv": "TotalMV"}).items():
        merged.setdefault(c, {}).setdefault("total_mv", v.get("total_mv"))

    return merged, loss


def fetch_limitup_days():
    rows = run_json(TOOL, ["ranking", "limitup_days", "--limit", "80", "--raw"]) or []
    return {r.get("代码"): r.get("LimitUpDays") for r in rows if r.get("代码")}


def _profile_chunk(chunk, prof):
    res = run_json(DATA, ["profile", ",".join(chunk), "--raw"])
    if not res:
        return
    items = res.get("data", []) if isinstance(res, dict) else res
    for it in items:
        d = it.get("data", it) if isinstance(it, dict) else {}
        c = d.get("code")
        if c:
            prof[c] = {
                "industry": d.get("industry") or d.get("sector") or "",
                "listed_date": d.get("listedDate") or "",
                "business": (d.get("business") or "")[:80],
            }


def fetch_profiles(codes):
    """
    批量公司档案 → 行业 + 上市日期。
    ⚠️ 关键教训（2026-08-05）：单个 chunk 整体超时会静默丢失 20 只股票的行业，
    导致它们无法归入板块。必须补漏重试。
    """
    prof = {}
    for i in range(0, len(codes), 10):
        _profile_chunk(codes[i:i + 10], prof)

    # 补漏重试：先小批，再逐只；带退避，避免连续请求被限流
    for size, backoff in ((5, 0.5), (1, 1.0), (1, 2.0)):
        missing = [c for c in codes if c not in prof]
        if not missing:
            break
        print(f"      档案补漏重试（批量{size}）：{len(missing)} 只", file=sys.stderr)
        for i in range(0, len(missing), size):
            _profile_chunk(missing[i:i + size], prof)
            time.sleep(backoff)

    still = [c for c in codes if c not in prof]
    if still:
        print(f"[WARN] 行业仍缺失 {len(still)} 只：{','.join(still)}", file=sys.stderr)
    return prof


def fetch_sector_ranking():
    """当日板块榜：行业涨幅 / 概念涨幅 / 行业资金流入。"""
    res = run_json(DATA, ["sector", "ranking", "--raw"]) or {}
    secs = res.get("sections", []) if isinstance(res, dict) else []
    out = {"industry_gain": [], "concept_gain": [], "capital_in": []}
    keys = ["industry_gain", "concept_gain", "capital_in"]
    for i, k in enumerate(keys):
        if i < len(secs):
            out[k] = secs[i]
    return out


# ---------------------------------------------------------------- 2. 硬性剔除
def listed_days(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return (date.today() - datetime.strptime(s[:10], fmt).date()).days
        except ValueError:
            continue
    return None


def hard_filter(stk, loss_codes):
    """
    返回 (剔除原因, 待核验原因)。
    ⚠️ 核心原则（2026-08-05 修正）：**数据缺失 ≠ 剔除**。
    旧版把「查不到 PE」当作「疑似亏损」直接剔除，一次误杀 45 只，
    其中不乏永新光学、东材科技、星网锐捷等明确盈利的公司。
    现在缺失一律进「待核验」，由人工用 neodata 补数后再定生死。
    """
    reject, review = [], []
    code, name = stk["code"], stk["name"]
    bare = code[2:] if len(code) > 2 else code

    # --- 机械可判，证据充分 → 直接剔除 ---
    if any(t in name.upper() for t in ("ST", "退")):
        reject.append("ST/退市")
    if bare.startswith("688") or code.startswith("bj") or bare[0] in ("8", "4"):
        reject.append("科创板/北交所")
    if stk["close"] is not None and stk["close"] > MAX_PRICE:
        reject.append(f"股价>{MAX_PRICE:.0f}({stk['close']:.2f})")

    ld = listed_days(stk.get("listed_date"))
    if ld is not None and ld < MIN_LISTED_DAYS:
        reject.append(f"次新股(上市{ld}天)")

    lud = stk.get("limitup_days")
    if lud is not None and lud >= MAX_LIMITUP_DAYS:
        reject.append(f"连板{lud}板≥{MAX_LIMITUP_DAYS}")

    pe = stk.get("pe_ttm")
    if code in loss_codes or (pe is not None and pe <= 0):
        reject.append(f"亏损(PE={pe:.1f})" if pe is not None else "亏损(PE<0)")

    yoy = stk.get("np_yoy")
    if yoy is not None and yoy < MIN_NP_YOY:
        reject.append(f"净利同比{yoy:.1f}%<{MIN_NP_YOY:.0f}%")

    # --- 数据缺失 → 待核验，不剔除 ---
    if pe is None and code not in loss_codes:
        review.append("PE_TTM[MISSING]")
    if yoy is None:
        review.append("净利同比[MISSING]")
    if not stk.get("industry"):
        review.append("行业[MISSING]")
    if ld is None:
        review.append("上市日期[MISSING]")

    return reject, review


# ---------------------------------------------------------------- 3. 主流程
def main():
    print("[1/5] 扫描全市场封板涨停 + 站上10日线 ...")
    pool = fetch_limitup_pool()
    if not pool:
        print("[ERROR] 涨停池为空，可能非交易日或数据源异常", file=sys.stderr)
        sys.exit(1)
    print(f"      入池 {len(pool)} 只")

    print("[2/5] 补充估值/成长/资金字段（分组查询，防丢行）...")
    enriched, loss_codes = fetch_enriched()
    for code, ext in enriched.items():
        if code in pool:
            pool[code].update({k: v for k, v in ext.items() if v is not None})
    print(f"      估值覆盖 {len(enriched)} 只，其中确认亏损 {len(loss_codes)} 只")

    print("[3/5] 补充连板天数 / 行业 / 上市日期 ...")
    for code, d in fetch_limitup_days().items():
        if code in pool:
            pool[code]["limitup_days"] = d
    for code, p in fetch_profiles(list(pool.keys())).items():
        if code in pool:
            pool[code].update(p)

    print("[4/5] 执行硬性剔除（缺失项进待核验，不误杀）...")
    passed, rejected, review = [], [], []
    for stk in pool.values():
        stk.setdefault("limitup_days", 1)
        rj, rv = hard_filter(stk, loss_codes)
        stk["review_flags"] = rv
        if rj:
            stk["reject_reasons"] = rj
            rejected.append(stk)
        elif rv:
            review.append(stk)
        else:
            passed.append(stk)
    print(f"      直接通过 {len(passed)} 只 / 待核验 {len(review)} 只 / 剔除 {len(rejected)} 只")

    print("[5/5] 反推当日活跃板块 ...")
    sector_rank = fetch_sector_ranking()
    hot_names = set()
    for k in ("industry_gain", "concept_gain", "capital_in"):
        for it in sector_rank.get(k, []):
            if it.get("name"):
                hot_names.add(it["name"])

    # 板块归集用「通过 + 待核验」，缺失字段不应影响板块热度判断
    by_ind = {}
    for stk in passed + review:
        by_ind.setdefault(stk.get("industry") or "未分类", []).append(stk)

    sectors = []
    for ind, lst in sorted(by_ind.items(), key=lambda x: -len(x[1])):
        on_board = any(ind in h or h in ind for h in hot_names)
        sectors.append({
            "industry": ind,
            "limitup_count": len(lst),
            "on_hot_board": on_board,
            "active": on_board or len(lst) >= STRONG_SECTOR_MIN_LIMITUPS,
            "stocks": [s["name"] for s in lst],
        })

    trade_date = datetime.now().strftime("%Y-%m-%d")
    result = {
        "trade_date": trade_date,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rule_version": "2026-08-05 全量涨停扫描 + 站上10日线",
        "pool_size": len(pool),
        "passed_count": len(passed),
        "review_count": len(review),
        "rejected_count": len(rejected),
        "sector_ranking": sector_rank,
        "sectors": sectors,
        "candidates": sorted(passed, key=lambda s: -(s.get("total_mv") or 0)),
        "need_review": sorted(review, key=lambda s: -(s.get("total_mv") or 0)),
        "rejected": sorted(rejected, key=lambda s: -(s.get("total_mv") or 0)),
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    write_report(result)
    print(f"\n完成：{OUT_JSON}\n     {OUT_MD}")


def fmt_mv(v):
    return f"{v / 1e8:.0f}亿" if v else "[MISSING]"


def fmt(v, suf="", nd=2):
    return f"{v:.{nd}f}{suf}" if v is not None else "[MISSING]"


def write_report(r):
    L = []
    L.append(f"# 全量涨停筛查报告 · {r['trade_date']}\n")
    L.append(f"> 规则版本：{r['rule_version']}　生成于 {r['generated_at']}")
    L.append("> 数据来源：westock-tool filter（全市场封板涨停）/ westock-data profile（行业·上市日）/ westock-data sector ranking（板块榜）\n")

    L.append("## 一、筛查漏斗\n")
    L.append("| 环节 | 数量 | 说明 |")
    L.append("| --- | --- | --- |")
    L.append(f"| 全市场封板涨停 且 站上10日线 | {r['pool_size']} | 入池口径，无榜单盲区 |")
    L.append(f"| 硬性条件剔除 | {r['rejected_count']} | ST/科创北交/次新/高价/≥4板/确认亏损 |")
    L.append(f"| 数据缺失·待核验 | {r['review_count']} | **不自动剔除**，需补数后定生死 |")
    L.append(f"| **直接进入打分环节** | **{r['passed_count']}** | 字段完备，逐只四维打分 |\n")

    L.append("## 二、当日活跃板块（数据反推，非预设）\n")
    L.append("| 行业 | 池内涨停家数 | 上榜板块行情榜 | 判定 | 个股 |")
    L.append("| --- | --- | --- | --- | --- |")
    for s in r["sectors"]:
        if s["limitup_count"] >= 1:
            L.append(f"| {s['industry']} | {s['limitup_count']} | "
                     f"{'是' if s['on_hot_board'] else '否'} | "
                     f"{'**活跃**' if s['active'] else '一般'} | "
                     f"{'、'.join(s['stocks'][:8])} |")
    L.append("")

    sr = r.get("sector_ranking", {})
    for key, title in (("industry_gain", "行业涨幅榜"),
                       ("concept_gain", "概念涨幅榜"),
                       ("capital_in", "行业资金流入榜")):
        items = sr.get(key, [])
        if not items:
            continue
        L.append(f"**{title}**：" + "、".join(
            f"{i.get('name')}({i.get('changePct')}%)" for i in items) + "\n")

    L.append("## 三、通过硬性筛查的候选池\n")
    L.append("| 代码 | 名称 | 行业 | 收盘 | 涨幅% | 距10日线% | 连板 | PE-TTM | PB | 总市值 | 净利同比% | 主力净流入 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for s in r["candidates"]:
        gap = ((s["close"] / s["ma10"] - 1) * 100) if s.get("close") and s.get("ma10") else None
        mn = s.get("main_net")
        L.append(f"| {s['code']} | {s['name']} | {s.get('industry') or '[MISSING]'} | "
                 f"{fmt(s.get('close'))} | {fmt(s.get('change_pct'))} | {fmt(gap, nd=1)} | "
                 f"{s.get('limitup_days', 1)} | {fmt(s.get('pe_ttm'), nd=1)} | {fmt(s.get('pb'))} | "
                 f"{fmt_mv(s.get('total_mv'))} | {fmt(s.get('np_yoy'), nd=1)} | "
                 f"{(str(round(mn / 1e8, 2)) + '亿') if mn is not None else '[MISSING]'} |")
    L.append("")

    L.append("## 四、待核验（数据缺失，未剔除）\n")
    L.append("> 这些标的通过了全部可判定的硬性条件，仅因数据源字段缺失无法完成打分。")
    L.append("> **不得默认剔除**——需用 neodata 补齐后回到打分流程。\n")
    L.append("| 代码 | 名称 | 行业 | 收盘 | 涨幅% | 连板 | 总市值 | 缺失字段 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for s in r.get("need_review", []):
        L.append(f"| {s['code']} | {s['name']} | {s.get('industry') or '[MISSING]'} | "
                 f"{fmt(s.get('close'))} | {fmt(s.get('change_pct'))} | "
                 f"{s.get('limitup_days', 1)} | {fmt_mv(s.get('total_mv'))} | "
                 f"{'、'.join(s.get('review_flags', []))} |")
    L.append("")

    L.append("## 五、剔除明细（可审计）\n")
    L.append("| 代码 | 名称 | 行业 | 收盘 | 剔除原因 |")
    L.append("| --- | --- | --- | --- | --- |")
    for s in r["rejected"]:
        L.append(f"| {s['code']} | {s['name']} | {s.get('industry') or '[MISSING]'} | "
                 f"{fmt(s.get('close'))} | {'；'.join(s['reject_reasons'])} |")
    L.append("")
    L.append("---")
    L.append("*本报告仅供参考，不构成个人投资建议。*")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
