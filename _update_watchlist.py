#!/usr/bin/env python3
"""One-off watchlist refresh for 2026-10-20 run (data snapshot = 2026-10-19 close)."""
import json
from pathlib import Path

DATA = Path("/Users/apple/WorkBuddy/automation-2026-07-14-01-18-22/web/data/watchlist.json")

with open(DATA, encoding="utf-8") as f:
    stocks = json.load(f)

# Authoritative 2026-10-19 close (westock quote --date 2026-10-19); 5d/20d from kline anchored 10-19
updates = {
    "sz002080": {"price": 41.75, "prev_close": 42.66, "change_pct": -2.13, "change_5d": -15.6, "change_20d": -19.6},
    "sh600601": {"price": 11.05, "prev_close": 11.52, "change_pct": -4.08, "change_5d": -21.4, "change_20d": -5.2},
    "sh600468": {"price": 5.6, "prev_close": 5.59, "change_pct": 0.18, "change_5d": -10.5, "change_20d": -5.6},
    "sh600267": {"price": 12.06, "prev_close": 10.96, "change_pct": 10.04, "change_5d": 6.0, "change_20d": 1.2},
    "sz000739": {"price": 21.62, "prev_close": 23.42, "change_pct": -7.69, "change_5d": 5.5, "change_20d": -8.7},
    "sh600593": {"price": 43.17, "prev_close": 47.97, "change_pct": -10.01, "change_5d": 21.3, "change_20d": -2.1},
    "sh600391": {"price": 43.18, "prev_close": 42.62, "change_pct": 1.31, "change_5d": 0.6, "change_20d": 14.1},
    "sz000823": {"price": 24.71, "prev_close": 25.26, "change_pct": -2.18, "change_5d": 33.0, "change_20d": 21.2},
}
for s in stocks:
    if s["code"] in updates:
        s.update(updates[s["code"]])

# Health / analysis adjustments for kept stocks
for s in stocks:
    if s["code"] == "sz002080":  # 中材科技 临界止损
        s["health"] = "warning"
        s["analysis"]["technical"] = "10-19收41.75（-2.13%），已逼近止损线41.5（仅高0.6%），临界状态；2连板后持续回落，短线获利盘抛压明显。"
        s["risks"] = ["2连板后回落，逼近止损41.5（临界）", "风电叶片装机节奏", "锂电隔膜价格竞争", "玻纤电子布景气波动"]
        if "临界止损41.5" not in s["tags"]:
            s["tags"].append("临界止损41.5")
    if s["code"] == "sh600593":  # 大连圣亚 跌停反转
        s["health"] = "warning"
        s["analysis"]["technical"] = "10-19放量大跌-10.01%跌停，跌破买点45.3（现价43.17），短线由强转弱；20日虽+21.3%但近5日已转弱。"
        s["analysis"]["sector"] = "旅游及景区板块中期偏弱，个股由涨停转为跌停，情绪逆转。"
        s["risks"] = ["10-19跌停-10.01%", "跌破买点45.3", "旅游板块中期偏弱", "PE 109偏高"]
        if not any("跌停" in t for t in s["tags"]):
            s["tags"].append("10-19跌停")

# 剔除：收盘<止损价 / 破位>15%
remove = {"sh603556", "sh601231", "sh603087", "sh601138"}
removed = [s["name"] for s in stocks if s["code"] in remove]
stocks = [s for s in stocks if s["code"] not in remove]

# 新增：保隆科技（回踩候选，不追高）
baolong = {
    "code": "sh603197", "name": "保隆科技", "full_code": "603197.SH", "market": "沪主板",
    "sector": "汽车零部件/智能底盘", "concept": ["智能驾驶", "汽车零部件", "胎压监测", "空气悬架", "传感器"],
    "price": 32.33, "prev_close": 29.39, "change_pct": 10.0, "change_5d": 13.4, "change_20d": 13.5,
    "volume": 39519, "turnover_pct": 1.87,
    "pe_ttm": 21.36, "pb": 1.67, "market_cap": 25.74,
    "ma10": 29.5, "above_ma10": True,
    "limit_up_count_7d": 2, "limit_up_dates": ["2026-10-16", "2026-10-19"],
    "buy_low": 27.5, "sell_high": 42.0, "stop_loss": 25.0,
    "score": 78, "rating": "推荐", "health": "healthy",
    "analysis": {
        "fundamental": "汽车智能底盘龙头（TPMS胎压监测全球领先，空气悬架/传感器放量）。2026H1归母净利+95.8%，Q2同比+386%，受益智能驾驶渗透与出口。PE 21.4倍，估值合理。",
        "technical": "10-16、10-19连续两涨停（2连板）收32.33，短线极强但已追高；买点设于27.5（前平台回踩），纪律上不追高。",
        "sector": "汽车零部件75分（中强）：保隆/万丰奥威/文灿等多股涨停，板块效应明确；以旧换新+出海政策支撑。",
        "valuation": "PE 21.4倍（零部件中低位），PB 1.67倍。+95.8%增速对应PEG<0.3，估值安全边际较高。"
    },
    "action": "watch", "tags": ["智能底盘", "TPMS龙头", "2连板", "业绩高增+95.8%", "回踩买点27.5"],
    "risks": ["2连板后追高风险", "汽车零部件价格竞争", "出口贸易摩擦", "回踩不到位则放弃"],
    "buy_low_base": 27.5,
}
stocks.append(baolong)

with open(DATA, "w", encoding="utf-8") as f:
    json.dump(stocks, f, ensure_ascii=False, indent=2)

print(f"✓ 更新完成：保留 {len(stocks)} 只 | 剔除 {removed} | 新增 保隆科技")
for s in stocks:
    print(f"  {s['name']}({s['code']}) price={s['price']} health={s['health']}")
