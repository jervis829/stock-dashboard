// 自选股监控网页 - 主 JS

// 加载 watchlist.json
async function loadWatchlist() {
  try {
    const response = await fetch('data/watchlist.json');
    const data = await response.json();
    return data;
  } catch (e) {
    console.error('加载 watchlist 失败：', e);
    return [];
  }
}

// 渲染主页 stock 卡片
function renderStockCard(stock) {
  const changeColor = stock.change_pct > 0 ? 'text-red' : (stock.change_pct < 0 ? 'text-green' : 'text-gray');
  const arrow = stock.change_pct > 0 ? '▲' : (stock.change_pct < 0 ? '▼' : '—');
  const changeText = `${arrow} ${Math.abs(stock.change_pct).toFixed(2)}%`;

  const healthClass = stock.health || 'healthy';
  const actionClass = stock.action || 'hold';
  const actionText = {
    buy_zone: '🟦 可买',
    hold: '🟩 持有',
    danger_zone: '🟥 风险',
    observe: '🟨 观察'
  }[actionClass] || '🟩 持有';

  const entryType = stock.entry_type || 'wait';
  const entryLabel = {
    wait: '⚪ 维持买点',
    reprice: '🔄 重定价',
    missed: '🚫 踏空放弃',
    review_downbreak: '🔻 破位'
  }[entryType] || '⚪ 维持买点';
  const gapTxt = stock.gap_pct != null ? (stock.gap_pct > 0 ? '+' : '') + stock.gap_pct.toFixed(1) + '%' : '—';

  return `
    <a href="stock_${stock.code}.html" class="stock-card ${healthClass}">
      <div class="stock-header">
        <div>
          <div class="stock-name">${stock.name}</div>
          <div class="stock-code">${stock.full_code} · ${stock.sector}</div>
        </div>
        <div class="stock-price">
          <div class="price">${stock.price.toFixed(2)}</div>
          <div class="change-pct ${changeColor}">${changeText}</div>
        </div>
      </div>
      <div class="stock-meta">
        ${stock.tags.map(t => `<span class="tag">${t}</span>`).join('')}
        <span class="tag">7日涨停${stock.limit_up_count_7d}次</span>
        <span class="tag ${stock.score >= 75 ? 'success' : (stock.score >= 60 ? 'warning' : 'danger')}">${stock.score}分</span>
      </div>
      <div class="stock-zones">
        <div class="zone buy">
          <div class="zone-label">买入下沿</div>
          <div class="zone-value">${stock.buy_low.toFixed(2)}</div>
        </div>
        <div class="zone sell">
          <div class="zone-label">卖出上沿</div>
          <div class="zone-value">${stock.sell_high.toFixed(2)}</div>
        </div>
        <div class="zone stop">
          <div class="zone-label">止损</div>
          <div class="zone-value">${stock.stop_loss.toFixed(2)}</div>
        </div>
      </div>
      <div class="stock-reprice">
        <span class="tag ${entryType === 'reprice' ? 'warning' : (entryType === 'missed' || entryType === 'review_downbreak') ? 'danger' : 'success'}">${entryLabel}</span>
        <span class="text-gray" style="font-size:12px;margin-left:6px">涨离买点 ${gapTxt}</span>
        ${stock.trailing_stop_suggestion ? `<span class="text-green" style="font-size:12px;margin-left:8px">🎯 移动止盈 ${stock.trailing_stop_suggestion}</span>` : ''}
      </div>
      <div class="stock-footer">
        <span>${actionText}</span>
        <div class="score-bar">
          <span>${stock.rating}</span>
          <div class="score-bar-bg">
            <div class="score-bar-fill" style="width: ${stock.score}%"></div>
          </div>
        </div>
      </div>
    </a>
  `;
}

// 渲染概览统计
function renderOverview(stocks) {
  const total = stocks.length;
  const healthy = stocks.filter(s => s.health === 'healthy').length;
  const warning = stocks.filter(s => s.health === 'warning').length;
  const danger = stocks.filter(s => s.health === 'danger').length;
  const buyZone = stocks.filter(s => s.action === 'buy_zone').length;
  const limitUpCount = stocks.reduce((sum, s) => sum + s.limit_up_count_7d, 0);
  const avgScore = (stocks.reduce((sum, s) => sum + s.score, 0) / total).toFixed(1);

  return `
    <div class="overview-card">
      <div class="label">监控标的</div>
      <div class="value">${total}</div>
      <div class="change text-gray">只</div>
    </div>
    <div class="overview-card">
      <div class="label">健康</div>
      <div class="value text-green">${healthy}</div>
      <div class="change text-gray">只</div>
    </div>
    <div class="overview-card">
      <div class="label">警示</div>
      <div class="value text-yellow">${warning}</div>
      <div class="change text-gray">只</div>
    </div>
    <div class="overview-card">
      <div class="label">危险</div>
      <div class="value text-red">${danger}</div>
      <div class="change text-gray">只</div>
    </div>
    <div class="overview-card">
      <div class="label">可买</div>
      <div class="value text-blue">${buyZone}</div>
      <div class="change text-gray">只</div>
    </div>
    <div class="overview-card">
      <div class="label">7日涨停累计</div>
      <div class="value text-red">${limitUpCount}</div>
      <div class="change text-gray">次</div>
    </div>
    <div class="overview-card">
      <div class="label">平均分</div>
      <div class="value">${avgScore}</div>
      <div class="change text-gray">/100</div>
    </div>
  `;
}

// 渲染板块分布
function renderSectorSummary(stocks) {
  const sectorMap = {};
  stocks.forEach(s => {
    if (!sectorMap[s.sector]) sectorMap[s.sector] = 0;
    sectorMap[s.sector]++;
  });

  const colors = ['#00d4ff', '#5b86e5', '#2ed573', '#ffa502', '#ff4757', '#a55eea', '#ff6b9d'];
  return Object.entries(sectorMap).map(([sector, count], i) => `
    <div class="sector-pill" style="--accent: ${colors[i % colors.length]}">
      <span class="sector-name">${sector}</span>
      <span class="sector-count">${count} 只</span>
    </div>
  `).join('');
}

// 渲染今日触发列表
function renderTriggerList(stocks) {
  const triggers = [];

  stocks.forEach(s => {
    if (s.action === 'buy_zone' && s.price <= s.buy_low) {
      triggers.push({ type: 'buy', stock: s, msg: `现价 ${s.price} ≤ 买入下沿 ${s.buy_low}，建议买入` });
    } else if (s.action === 'buy_zone' && s.price <= s.buy_low * 1.05) {
      triggers.push({ type: 'buy_near', stock: s, msg: `现价 ${s.price} 接近买入下沿 ${s.buy_low}（5%以内）` });
    } else if (s.action === 'danger_zone') {
      triggers.push({ type: 'danger', stock: s, msg: `${s.change_pct < 0 ? '跌停' : '风险'} - 建议关注或剔除` });
    } else if (s.price <= s.stop_loss) {
      triggers.push({ type: 'stop', stock: s, msg: `现价 ${s.price} ≤ 止损价 ${s.stop_loss}，**触发止损需剔除**` });
    } else if (s.price >= s.sell_high * 0.95) {
      triggers.push({ type: 'sell', stock: s, msg: `现价 ${s.price} 接近卖出上沿 ${s.sell_high}，可考虑减仓` });
    }
  });

  if (triggers.length === 0) {
    return '<div class="section"><p class="text-gray">今日无触发信号</p></div>';
  }

  return `
    <div class="section">
      <h2>⚡ 今日触发信号 (${triggers.length})</h2>
      <table>
        <thead>
          <tr>
            <th>类型</th>
            <th>股票</th>
            <th>现价</th>
            <th>触发详情</th>
          </tr>
        </thead>
        <tbody>
          ${triggers.map(t => `
            <tr>
              <td>${t.type === 'buy' ? '🟦 买入' : t.type === 'buy_near' ? '🟦 接近买点' : t.type === 'stop' ? '🔴 止损' : t.type === 'sell' ? '🟢 卖出' : t.type === 'danger' ? '⚠️ 风险' : ''}</td>
              <td><a href="stock_${t.stock.code}.html" style="color:#00d4ff">${t.stock.name}</a></td>
              <td>${t.stock.price.toFixed(2)}</td>
              <td>${t.msg}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// 主页初始化
async function initIndex() {
  const stocks = await loadWatchlist();
  document.getElementById('overview').innerHTML = renderOverview(stocks);
  document.getElementById('sector-summary').innerHTML = renderSectorSummary(stocks);
  document.getElementById('stock-grid').innerHTML = stocks.map(renderStockCard).join('');
  document.getElementById('trigger-list').innerHTML = renderTriggerList(stocks);

  // 更新统计时间
  const updateTime = new Date().toLocaleString('zh-CN', { hour12: false });
  document.getElementById('update-time').textContent = updateTime;
}

// 仪表盘初始化
async function initDashboard() {
  const stocks = await loadWatchlist();

  // 板块分布
  document.getElementById('sector-summary').innerHTML = renderSectorSummary(stocks);

  // 健康度分布
  const healthGroups = { healthy: [], warning: [], danger: [] };
  stocks.forEach(s => healthGroups[s.health]?.push(s));

  document.getElementById('healthy-list').innerHTML = healthGroups.healthy.map(s =>
    `<li><a href="stock_${s.code}.html" style="color:#2ed573">${s.name}</a> - ${s.price.toFixed(2)} (${s.change_pct > 0 ? '+' : ''}${s.change_pct}%)</li>`
  ).join('') || '<li class="text-gray">无</li>';

  document.getElementById('warning-list').innerHTML = healthGroups.warning.map(s =>
    `<li><a href="stock_${s.code}.html" style="color:#ffa502">${s.name}</a> - ${s.price.toFixed(2)} (${s.change_pct > 0 ? '+' : ''}${s.change_pct}%)</li>`
  ).join('') || '<li class="text-gray">无</li>';

  document.getElementById('danger-list').innerHTML = healthGroups.danger.map(s =>
    `<li><a href="stock_${s.code}.html" style="color:#ff4757">${s.name}</a> - ${s.price.toFixed(2)} (${s.change_pct > 0 ? '+' : ''}${s.change_pct}%)</li>`
  ).join('') || '<li class="text-gray">无</li>';

  // 监控规则
  const rulesHTML = `
    <div class="section">
      <h2>📋 监控规则（每日复盘执行）</h2>
      <ul class="risk-list">
        <li>收盘价 &lt; 止损价 → 立即剔除自选股</li>
        <li>连续 2 日跌停 → 次日开盘若不能反包则剔除</li>
        <li>7 日内无涨停且未触发买点 → 剔除</li>
        <li>中报/季报业绩雷区（连续 2 年亏损 / 单年净利同比 &lt; -50%）→ 次日剔除</li>
        <li>现价 &gt; 卖出上沿的 95% → 提示减仓</li>
        <li>现价 &lt; 买入下沿 → 提示买入</li>
      </ul>
    </div>
  `;
  document.getElementById('rules').innerHTML = rulesHTML;
}

// 详情页初始化
async function initStockDetail(code) {
  const stocks = await loadWatchlist();
  const stock = stocks.find(s => s.code === code);
  if (!stock) {
    document.getElementById('content').innerHTML = '<p>未找到该股票</p>';
    return;
  }

  const changeColor = stock.change_pct > 0 ? 'text-red' : (stock.change_pct < 0 ? 'text-green' : 'text-gray');
  const arrow = stock.change_pct > 0 ? '▲' : (stock.change_pct < 0 ? '▼' : '—');
  const changeText = `${arrow} ${Math.abs(stock.change_pct).toFixed(2)}%`;

  const actionClass = stock.action || 'hold';
  const actionText = {
    buy_zone: '🟦 可买 - 当前价格已接近或进入买入区间',
    hold: '🟩 持有 - 价格在合理区间内，继续观察',
    danger_zone: '🟥 风险 - 价格已接近或跌破止损价，建议关注/剔除',
    observe: '🟨 观察 - 暂不操作，等待更多信号'
  }[actionClass] || '🟩 持有';

  const html = `
    <a href="index.html" class="back-link">← 返回自选股总览</a>
    <div class="detail-header">
      <div class="left">
        <h1>${stock.name}</h1>
        <div class="meta">
          <span>${stock.full_code}</span>
          <span>·</span>
          <span>${stock.market}</span>
          <span>·</span>
          <span>${stock.sector}</span>
        </div>
        <div style="margin-top:12px">
          ${stock.tags.map(t => `<span class="tag">${t}</span>`).join('')}
        </div>
      </div>
      <div class="right">
        <div class="price">${stock.price.toFixed(2)}</div>
        <div class="change-pct ${changeColor}">${changeText}</div>
        <div style="margin-top:8px; font-size:13px; color:#888">
          昨收 ${stock.prev_close.toFixed(2)} · 5日 ${stock.change_5d > 0 ? '+' : ''}${stock.change_5d}% · 20日 ${stock.change_20d > 0 ? '+' : ''}${stock.change_20d}%
        </div>
      </div>
    </div>

    <div class="action-banner ${actionClass}">
      <span>${actionText}</span>
    </div>

    <div class="section">
      <h2>💰 交易区间</h2>
      <div class="detail-grid">
        <div class="detail-item">
          <div class="label">买入下沿</div>
          <div class="value text-blue">${stock.buy_low.toFixed(2)}</div>
          <div class="text-gray" style="font-size:12px; margin-top:4px">距现价 ${((stock.price - stock.buy_low) / stock.price * 100).toFixed(1)}%</div>
        </div>
        <div class="detail-item">
          <div class="label">当前价格</div>
          <div class="value">${stock.price.toFixed(2)}</div>
        </div>
        <div class="detail-item">
          <div class="label">卖出上沿</div>
          <div class="value text-green">${stock.sell_high.toFixed(2)}</div>
          <div class="text-gray" style="font-size:12px; margin-top:4px">距现价 ${((stock.sell_high - stock.price) / stock.price * 100).toFixed(1)}%</div>
        </div>
        <div class="detail-item">
          <div class="label">止损价</div>
          <div class="value text-red">${stock.stop_loss.toFixed(2)}</div>
          <div class="text-gray" style="font-size:12px; margin-top:4px">距现价 ${((stock.price - stock.stop_loss) / stock.price * 100).toFixed(1)}%</div>
        </div>
        <div class="detail-item">
          <div class="label">涨离买点</div>
          <div class="value">${stock.gap_pct != null ? (stock.gap_pct > 0 ? '+' : '') + stock.gap_pct.toFixed(1) + '%' : '—'}</div>
          <div class="text-gray" style="font-size:12px; margin-top:4px">${stock.price_status || ''}</div>
        </div>
        ${stock.trailing_stop_suggestion ? `<div class="detail-item"><div class="label">移动止盈建议</div><div class="value text-green">${stock.trailing_stop_suggestion}</div><div class="text-gray" style="font-size:12px;margin-top:4px">接近卖出上沿，建议移动止盈</div></div>` : ''}
      </div>
    </div>

    <div class="section">
      <h2>📊 关键指标</h2>
      <div class="detail-grid">
        <div class="detail-item">
          <div class="label">综合评分</div>
          <div class="value text-blue">${stock.score}/100</div>
        </div>
        <div class="detail-item">
          <div class="label">7日涨停</div>
          <div class="value text-red">${stock.limit_up_count_7d} 次</div>
          <div class="text-gray" style="font-size:12px; margin-top:4px">${stock.limit_up_dates.join(', ')}</div>
        </div>
        <div class="detail-item">
          <div class="label">PE(TTM)</div>
          <div class="value">${stock.pe_ttm < 0 ? '<span class="text-red">亏损</span>' : stock.pe_ttm.toFixed(2)}</div>
        </div>
        <div class="detail-item">
          <div class="label">PB</div>
          <div class="value">${stock.pb.toFixed(2)}</div>
        </div>
        <div class="detail-item">
          <div class="label">总市值</div>
          <div class="value">${stock.market_cap.toFixed(0)} 亿</div>
        </div>
        <div class="detail-item">
          <div class="label">换手率</div>
          <div class="value">${stock.turnover_pct.toFixed(2)}%</div>
        </div>
      </div>
    </div>

    <div class="section">
      <h2>💎 基本面分析</h2>
      <p>${stock.analysis.fundamental}</p>
      <h3>板块效应</h3>
      <p>${stock.analysis.sector}</p>
      <h3>估值水平</h3>
      <p>${stock.analysis.valuation}</p>
    </div>

    <div class="section">
      <h2>📈 技术面分析</h2>
      <p>${stock.analysis.technical}</p>
    </div>

    <div class="section">
      <h2>🏷️ 概念标签</h2>
      <p>${stock.concept.map(c => `<span class="tag">${c}</span>`).join(' ')}</p>
    </div>

    <div class="section">
      <h2>⚠️ 风险提示</h2>
      <ul class="risk-list">
        ${stock.risks.map(r => `<li>${r}</li>`).join('')}
      </ul>
    </div>

    <div class="section">
      <h2>🎯 操作建议</h2>
      <div class="detail-grid">
        <div class="detail-item">
          <div class="label">评级</div>
          <div class="value ${stock.score >= 75 ? 'text-green' : (stock.score >= 60 ? 'text-yellow' : 'text-red')}">${stock.rating}</div>
        </div>
        <div class="detail-item">
          <div class="label">健康度</div>
          <div class="value ${stock.health === 'healthy' ? 'text-green' : (stock.health === 'warning' ? 'text-yellow' : 'text-red')}">${stock.health === 'healthy' ? '健康' : (stock.health === 'warning' ? '警示' : '危险')}</div>
        </div>
        <div class="detail-item">
          <div class="label">操作</div>
          <div class="value text-blue">${actionClass === 'buy_zone' ? '可买' : actionClass === 'hold' ? '持有' : actionClass === 'danger_zone' ? '关注/剔除' : '观察'}</div>
        </div>
      </div>
      <p style="margin-top:16px">${actionText}</p>
    </div>
  `;

  document.getElementById('content').innerHTML = html;
}

// ==================== 股票一览表格 ====================

let _tableStocks = [];

// 状态 / 操作 徽章
const HEALTH_BADGE = {
  healthy: '<span class="badge badge-healthy">🟢 健康</span>',
  warning: '<span class="badge badge-warning">🟡 警示</span>',
  danger:  '<span class="badge badge-danger">🔴 危险</span>'
};

const ACTION_LABEL = {
  buy_zone:    { text: '可买入', cls: 'action-buy' },
  hold:        { text: '持有',   cls: 'action-hold' },
  observe:     { text: '观察',   cls: 'action-observe' },
  danger_zone: { text: '剔除预警', cls: 'action-danger' }
};

// 根据现价自动判断操作建议
function inferAction(s) {
  const a = s.action;
  if (a === 'danger_zone') return '剔除预警';
  if (s.price <= s.stop_loss) return '🔴 触发止损';
  if (s.price >= s.sell_high) return '🟢 触发卖出';
  if (s.price <= s.buy_low)   return '🔵 触发买入';
  if (s.price <= s.buy_low * 1.05) return '🔵 接近买点';
  if (a === 'buy_zone') return '可买入';
  if (a === 'observe')  return '观察';
  return '持有';
}

// 距买点/止损百分比
function distToBuy(s) {
  if (!s.buy_low) return 999;
  return ((s.price - s.buy_low) / s.buy_low) * 100;
}
function distToStop(s) {
  if (!s.stop_loss) return 999;
  return ((s.price - s.stop_loss) / s.stop_loss) * 100;
}

// 渲染一行
function renderStockRow(s) {
  const changeCls = s.change_pct > 0 ? 'cell-up' : (s.change_pct < 0 ? 'cell-down' : 'cell-flat');
  const arrow = s.change_pct > 0 ? '▲' : (s.change_pct < 0 ? '▼' : '—');
  const changeText = `${arrow} ${Math.abs(s.change_pct).toFixed(2)}%`;
  const scoreCls = s.score >= 80 ? 'score-hi' : (s.score >= 70 ? 'score-mid' : 'score-lo');

  // 涨停次数染色
  const limitUpBadge = s.limit_up_count_7d >= 2
    ? `<span class="lu-badge lu-2">${s.limit_up_count_7d}连</span>`
    : `<span class="lu-badge lu-1">${s.limit_up_count_7d}</span>`;

  const actionText = inferAction(s);
  const actionCls = actionText.includes('止损') ? 'action-stop'
    : actionText.includes('卖出') ? 'action-sell'
    : actionText.includes('买点') || actionText.includes('买入') ? 'action-buy'
    : actionText.includes('剔除') ? 'action-danger'
    : actionText.includes('观察') ? 'action-observe'
    : 'action-hold';

  return `
    <tr class="row-${s.health || 'healthy'}">
      <td class="cell-code"><a href="stock_${s.code}.html" class="link-stock">${s.full_code}</a></td>
      <td class="cell-name"><a href="stock_${s.code}.html" class="link-stock"><strong>${s.name}</strong></a></td>
      <td class="cell-sector" title="${s.sector}">${s.sector}</td>
      <td class="num">${s.price.toFixed(2)}</td>
      <td class="num ${changeCls}">${changeText}</td>
      <td class="num">${limitUpBadge}</td>
      <td class="num"><span class="${scoreCls}"><strong>${s.score}</strong></span></td>
      <td class="num cell-buy">${s.buy_low.toFixed(2)}</td>
      <td class="num cell-sell">${s.sell_high.toFixed(2)}</td>
      <td class="num cell-stop">${s.stop_loss.toFixed(2)}</td>
      <td class="num" style="color:${s.gap_pct > 30 ? '#ff4757' : s.gap_pct > 15 ? '#ffa502' : '#888'}">${s.gap_pct != null ? (s.gap_pct > 0 ? '+' : '') + s.gap_pct.toFixed(1) + '%' : '—'}</td>
      <td>${HEALTH_BADGE[s.health] || HEALTH_BADGE.healthy}</td>
      <td><span class="action-tag ${actionCls}">${actionText}</span></td>
    </tr>
  `;
}

// 排序 + 过滤
function filterSort(stocks) {
  const kw = (document.getElementById('search-input')?.value || '').trim().toLowerCase();
  const healthFilter = document.getElementById('filter-health')?.value || 'all';
  const sectorFilter = document.getElementById('filter-sector')?.value || 'all';
  const sortKey = document.getElementById('sort-select')?.value || 'score-desc';

  let arr = stocks.filter(s => {
    if (healthFilter !== 'all' && s.health !== healthFilter) return false;
    if (sectorFilter !== 'all' && s.sector !== sectorFilter) return false;
    if (kw) {
      const blob = `${s.name} ${s.code} ${s.full_code} ${s.sector} ${(s.concept||[]).join(' ')}`.toLowerCase();
      if (!blob.includes(kw)) return false;
    }
    return true;
  });

  const cmp = {
    'score-desc':  (a, b) => b.score - a.score,
    'score-asc':   (a, b) => a.score - b.score,
    'change-desc': (a, b) => b.change_pct - a.change_pct,
    'change-asc':  (a, b) => a.change_pct - b.change_pct,
    'price-desc':  (a, b) => b.price - a.price,
    'price-asc':   (a, b) => a.price - b.price,
    'ratio-buy':   (a, b) => distToBuy(a) - distToBuy(b),
    'ratio-stop':  (a, b) => distToStop(a) - distToStop(b)
  }[sortKey] || ((a, b) => b.score - a.score);

  return arr.sort(cmp);
}

function renderTable() {
  const stocks = _tableStocks;
  const filtered = filterSort(stocks);
  const tbody = document.getElementById('stock-tbody');
  tbody.innerHTML = filtered.length
    ? filtered.map(renderStockRow).join('')
    : '<tr><td colspan="13" style="text-align:center; padding:40px; color:#888;">没有匹配的股票</td></tr>';
  document.getElementById('total-count').textContent = filtered.length;
}

// 初始化
async function initStockTable() {
  const stocks = await loadWatchlist();
  _tableStocks = stocks;

  // 概览卡片
  const healthy = stocks.filter(s => s.health === 'healthy').length;
  const warning = stocks.filter(s => s.health === 'warning').length;
  const danger  = stocks.filter(s => s.health === 'danger').length;
  const trigger = stocks.filter(s => {
    if (s.price <= s.stop_loss) return true;
    if (s.price <= s.buy_low) return true;
    if (s.price >= s.sell_high * 0.95) return true;
    return false;
  }).length;

  document.getElementById('cnt-healthy').textContent = healthy;
  document.getElementById('cnt-warning').textContent = warning;
  document.getElementById('cnt-danger').textContent = danger;
  document.getElementById('cnt-trigger').textContent = trigger;
  document.getElementById('stock-count').textContent = stocks.length;

  // 板块下拉
  const sectors = [...new Set(stocks.map(s => s.sector))].sort();
  const sectorSel = document.getElementById('filter-sector');
  sectors.forEach(sec => {
    const opt = document.createElement('option');
    opt.value = sec;
    opt.textContent = sec;
    sectorSel.appendChild(opt);
  });

  // 事件监听
  ['search-input', 'filter-health', 'filter-sector', 'sort-select'].forEach(id => {
    document.getElementById(id).addEventListener('input', renderTable);
    document.getElementById(id).addEventListener('change', renderTable);
  });

  // 监控规则
  document.getElementById('rules').innerHTML = `
    <div class="section">
      <h2>📋 监控规则（每日复盘执行）</h2>
      <ul class="risk-list">
        <li>收盘价 &lt; 止损价 → 立即剔除自选股</li>
        <li>连续 2 日跌停 → 次日开盘若不能反包则剔除</li>
        <li>7 日内无涨停且未触发买点 → 剔除</li>
        <li>中报/季报业绩雷区（连续 2 年亏损 / 单年净利同比 &lt; -50%）→ 次日剔除</li>
        <li>现价 &gt; 卖出上沿的 95% → 提示减仓</li>
        <li>现价 &lt; 买入下沿 → 提示买入</li>
      </ul>
    </div>
  `;

  renderTable();
}
