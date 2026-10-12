// Order history: search and filter past and open orders.
import { get } from "./api.js";
import { fmt } from "./state.js";
import { esc, debounce, todayISO } from "./util.js";

const METHOD = { cash: "Cash", card: "Card", upi: "UPI" };

export async function historyView(el) {
  el.innerHTML = `<div class="page-head"><h1>Orders</h1></div>
    <div class="row card" style="margin-bottom:1rem">
      <label class="field grow" style="margin:0">Search<input type="search" id="f-q" placeholder="Bill no, order #, table or customer"></label>
      <label class="field" style="margin:0">Status<select id="f-status">
        <option value="">All</option><option value="open">Open</option><option value="paid">Paid</option><option value="cancelled">Cancelled</option></select></label>
      <label class="field" style="margin:0">Date<input type="date" id="f-date"></label>
      <button class="btn" id="f-today">Today</button><button class="btn" id="f-clear">Clear</button></div>
    <div class="scroll-x" id="results"></div>`;
  const $ = (s) => el.querySelector(s);

  async function load() {
    const p = new URLSearchParams();
    if ($("#f-q").value.trim()) p.set("q", $("#f-q").value.trim());
    if ($("#f-status").value) p.set("status", $("#f-status").value);
    if ($("#f-date").value) p.set("date", $("#f-date").value);
    try {
      const rows = await get(`/api/orders?${p}`);
      $("#results").innerHTML = rows.length ? `<table class="data clickable"><thead><tr>
        <th>Order</th><th>Table / type</th><th>Customer</th><th class="right">Items</th><th class="right">Total</th><th>Payment</th><th>Status</th><th>Time</th></tr></thead><tbody>
        ${rows.map((o) => `<tr data-id="${o.id}" tabindex="0">
          <td><b>${o.bill_no ? esc(o.bill_no) : "#" + o.id}</b></td>
          <td>${o.order_type === "dine_in" ? esc(o.table_name) : "Takeaway"}</td>
          <td>${esc(o.customer_name) || '<span class="muted">-</span>'}</td>
          <td class="right">${o.item_count}</td><td class="right money">${fmt(o.total)}</td>
          <td>${o.payment_method ? METHOD[o.payment_method] : '<span class="muted">-</span>'}</td>
          <td><span class="badge ${o.status}">${o.status}</span></td>
          <td class="muted">${esc((o.paid_at || o.created_at).slice(5, 16))}</td></tr>`).join("")}</tbody></table>`
        : `<p class="empty card">No orders match these filters.</p>`;
    } catch (err) { $("#results").innerHTML = `<div class="error-box">${esc(err.message)}</div>`; }
  }
  const open = (tr) => tr && (location.hash = `#/order/${tr.dataset.id}`);
  el.addEventListener("click", (e) => open(e.target.closest("tr[data-id]")));
  el.addEventListener("keydown", (e) => { if (e.key === "Enter") open(e.target.closest("tr[data-id]")); });
  $("#f-q").addEventListener("input", debounce(load));
  $("#f-status").addEventListener("change", load);
  $("#f-date").addEventListener("change", load);
  $("#f-today").onclick = () => { $("#f-date").value = todayISO(); load(); };
  $("#f-clear").onclick = () => { $("#f-q").value = ""; $("#f-status").value = ""; $("#f-date").value = ""; load(); };
  await load();
}
