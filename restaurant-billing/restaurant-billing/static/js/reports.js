// Sales report for a date range (admin only).
import { get } from "./api.js";
import { fmt } from "./state.js";
import { esc, todayISO } from "./util.js";

const METHOD = { cash: "Cash", card: "Card", upi: "UPI" };
const daysAgo = (n) => { const d = new Date(); d.setDate(d.getDate() - n); return d.toLocaleDateString("en-CA"); };

export async function reportsView(el) {
  el.innerHTML = `<div class="page-head"><h1>Reports</h1></div>
    <div class="row card" style="margin-bottom:1rem">
      <label class="field" style="margin:0">From<input type="date" id="from" value="${todayISO()}"></label>
      <label class="field" style="margin:0">To<input type="date" id="to" value="${todayISO()}"></label>
      <button class="btn" data-range="0">Today</button><button class="btn" data-range="6">Last 7 days</button>
      <button class="btn" data-range="29">Last 30 days</button></div>
    <div id="report"></div>`;
  const $ = (s) => el.querySelector(s);

  async function load() {
    const out = $("#report");
    try {
      const r = await get(`/api/reports/summary?from=${$("#from").value}&to=${$("#to").value}`);
      const t = r.totals, maxMethod = Math.max(1, ...r.by_method.map((m) => m.amount));
      const stat = (label, value) => `<div class="card stat"><b>${value}</b><span>${label}</span></div>`;
      out.innerHTML = `<div class="stats">
          ${stat("Net sales", fmt(t.net_sales))}${stat("Paid bills", t.orders)}${stat("Average bill", fmt(t.average_bill))}
          ${stat("Tax collected", fmt(t.tax))}${stat("Discounts given", fmt(t.discounts))}</div>
        <p class="muted">${r.cancelled} cancelled in this period · ${r.open_orders} order(s) open right now (not counted until paid).</p>
        <div class="two-eq">
          <div class="card"><h3>Payment methods</h3>${r.by_method.map((m) => `
            <div class="bar-row"><span>${METHOD[m.method]}</span><div><div class="bar" style="width:${(m.amount / maxMethod) * 100}%"></div></div>
            <span class="right money">${fmt(m.amount)}</span></div>`).join("") || '<p class="empty">No paid bills in this range.</p>'}</div>
          <div class="card scroll-x"><h3>Top items</h3>${r.top_items.length ? `<table class="data"><thead><tr><th>Item</th><th class="right">Qty</th><th class="right">Sales</th></tr></thead><tbody>
            ${r.top_items.map((i) => `<tr><td>${esc(i.name)}</td><td class="right">${i.qty}</td><td class="right money">${fmt(i.amount)}</td></tr>`).join("")}</tbody></table>`
            : '<p class="empty">Nothing sold in this range.</p>'}</div></div>
        <h2>Sales by day</h2>${r.daily.length ? `<div class="scroll-x"><table class="data"><thead><tr><th>Date</th><th class="right">Bills</th><th class="right">Net sales</th></tr></thead><tbody>
          ${r.daily.map((d) => `<tr><td>${esc(d.day)}</td><td class="right">${d.orders}</td><td class="right money">${fmt(d.amount)}</td></tr>`).join("")}</tbody></table></div>`
          : '<p class="empty card">No sales yet.</p>'}`;
    } catch (err) { out.innerHTML = `<div class="error-box">${esc(err.message)}</div>`; }
  }
  el.addEventListener("change", (e) => { if (e.target.id === "from" || e.target.id === "to") load(); });
  el.addEventListener("click", (e) => {
    const b = e.target.closest("[data-range]");
    if (!b) return;
    $("#from").value = daysAgo(Number(b.dataset.range)); $("#to").value = todayISO(); load();
  });
  await load();
}
