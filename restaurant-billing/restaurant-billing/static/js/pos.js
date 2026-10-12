// Point-of-sale screens: the floor (tables), taking an order, discount, payment and receipt.
import { get, post, patch, del } from "./api.js";
import { state, fmt, loadMenu } from "./state.js";
import { esc, toPaise, toast, openModal, closeModal } from "./util.js";
import { receiptHTML, printReceipt } from "./receipt.js";

const goto = (hash) => { location.hash = hash; };
const reroute = () => window.dispatchEvent(new Event("hashchange"));

/* =============================================================== FLOOR */
export async function floorView(el) {
  async function draw() {
    const [tables, takeaways] = await Promise.all([
      get("/api/tables"), get("/api/orders?status=open&type=takeaway")]);
    el.innerHTML = `
      <div class="page-head"><h1>Floor</h1>
        <button class="btn primary" data-new-takeaway>New takeaway order</button></div>
      <div class="table-grid">${tables.map((t) => `
        <button class="table-tile ${t.order_id ? "busy" : "free"}" data-table="${t.id}" data-order="${t.order_id ?? ""}">
          <span class="t-name">${esc(t.name)}</span>
          <span class="t-meta">${t.order_id ? `${t.item_count} item${t.item_count === 1 ? "" : "s"} · since ${esc(t.order_since.slice(11, 16))}` : `${t.seats} seats`}</span>
          <span class="t-state">${t.order_id ? fmt(t.order_total) : "Free"}</span>
        </button>`).join("") || `<p class="empty">No tables yet. An admin can add tables in Setup.</p>`}</div>
      ${takeaways.length ? `<h2>Open takeaway orders</h2><div class="chips">${takeaways.map((o) =>
        `<button class="chip busy" data-order="${o.id}">#${o.id} ${esc(o.customer_name || "Takeaway")} · ${fmt(o.total)}</button>`).join("")}</div>` : ""}`;
  }
  await draw();
  const timer = setInterval(() => draw().catch(() => {}), 15000); // keep other devices in sync

  el.addEventListener("click", async (e) => {
    try {
      const order = e.target.closest("[data-order]");
      if (order && order.dataset.order) return goto(`#/order/${order.dataset.order}`);
      const table = e.target.closest("[data-table]");
      if (table) {
        const o = await post("/api/orders", { order_type: "dine_in", table_id: Number(table.dataset.table) });
        return goto(`#/order/${o.id}`);
      }
      if (e.target.closest("[data-new-takeaway]")) {
        const o = await post("/api/orders", { order_type: "takeaway" });
        goto(`#/order/${o.id}`);
      }
    } catch (err) { toast(err.message, "error"); draw().catch(() => {}); }
  });
  return () => clearInterval(timer);
}

/* =============================================================== ORDER */
export async function orderView(el, id) {
  let order = await get(`/api/orders/${id}`);
  const title = () => (order.order_type === "dine_in" ? `Table ${esc(order.table_name)}` : "Takeaway");

  if (order.status !== "open") { // finished orders are read-only
    el.innerHTML = `<div class="page-head"><h1>${title()} · Order #${order.id}
        <span class="badge ${order.status}">${order.status}</span></h1>
      <div class="row"><a class="btn" href="#/orders">Back to orders</a>
      <button class="btn primary" data-print>Print bill</button></div></div>
      <div class="receipt-sheet">${receiptHTML(order)}</div>`;
    el.querySelector("[data-print]").onclick = () => printReceipt(order);
    return;
  }

  await loadMenu().catch(() => {}); // pick up price / availability changes made elsewhere
  let activeCat = 0, query = "";
  el.innerHTML = `<div class="pos">
    <div class="menu-pane">
      <input type="search" id="q" placeholder="Search menu (Enter adds the first match)" autocomplete="off" autofocus>
      <div class="chips" id="cats"></div>
      <div class="item-grid" id="items"></div>
    </div>
    <aside class="card ticket" id="ticket"></aside></div>`;
  const $ = (s) => el.querySelector(s);

  const visibleItems = () => state.menu.filter((i) =>
    (!activeCat || i.category_id === activeCat) && (!query || i.name.toLowerCase().includes(query.toLowerCase())));

  function drawMenu() {
    $("#cats").innerHTML = [{ id: 0, name: "All" }, ...state.categories].map((c) =>
      `<button class="chip ${c.id === activeCat ? "active" : ""}" data-cat="${c.id}">${esc(c.name)}</button>`).join("");
    const items = visibleItems();
    $("#items").innerHTML = items.map((i) => `
      <button class="menu-item" data-add="${i.id}" ${i.is_available ? "" : "disabled"}>
        <span class="name"><span class="dot ${i.is_veg ? "" : "nonveg"}" title="${i.is_veg ? "Veg" : "Non-veg"}"></span>${esc(i.name)}</span>
        <span class="price">${i.is_available ? fmt(i.price) : "Sold out"}</span></button>`).join("")
      || `<p class="empty">No menu items match.</p>`;
  }

  function drawTicket() {
    const row = (label, value, cls = "") => `<div class="r ${cls}"><span>${label}</span><span class="money">${value}</span></div>`;
    const pctText = (bp) => `${+(bp / 100).toFixed(2)}%`;
    const d = order;
    $("#ticket").innerHTML = `
      <div class="ticket-head"><h2>${title()}</h2><span class="muted">Order #${d.id}</span></div>
      <input type="text" id="cust" maxlength="60" placeholder="Customer name (optional)" value="${esc(d.customer_name)}">
      <ul class="lines">${d.items.map((i) => `
        <li class="line" data-line="${i.id}">
          <div class="line-top"><span>${esc(i.name)}</span><span class="money">${fmt(i.unit_price * i.qty)}</span></div>
          <div class="line-ctl">
            <button class="qbtn" data-act="dec" aria-label="One less ${esc(i.name)}">−</button>
            <span class="qty">${i.qty}</span>
            <button class="qbtn" data-act="inc" aria-label="One more ${esc(i.name)}">+</button>
            <span class="muted money">× ${fmt(i.unit_price)}</span>
            <span style="flex:1"></span>
            <button class="qbtn" data-act="remove" aria-label="Remove ${esc(i.name)}">✕</button></div>
          <input class="note" type="text" maxlength="200" data-act="note" placeholder="Note for kitchen (e.g. less spicy)" value="${esc(i.notes)}">
        </li>`).join("") || `<li class="empty">Tap menu items to add them.</li>`}</ul>
      <div class="disc">
        <select id="disc-type" aria-label="Discount type">
          <option value="none" ${d.discount_type === "none" ? "selected" : ""}>No discount</option>
          <option value="percent" ${d.discount_type === "percent" ? "selected" : ""}>Percent</option>
          <option value="flat" ${d.discount_type === "flat" ? "selected" : ""}>Flat amount</option></select>
        <input type="number" id="disc-val" min="0" step="0.01" aria-label="Discount value" ${d.discount_type === "none" ? "disabled" : ""}
          value="${d.discount_type === "none" ? "" : d.discount_value / 100}">
        <button class="btn small" data-act="apply-discount">Apply</button></div>
      <div>
        <div class="totals">
          ${row("Subtotal", fmt(d.subtotal))}
          ${d.discount_amount ? row("Discount", "-" + fmt(d.discount_amount)) : ""}
          ${d.tax_bp ? row(`Tax (${pctText(d.tax_bp)})`, fmt(d.tax_amount)) : ""}
          ${d.service_bp ? row(`Service (${pctText(d.service_bp)})`, fmt(d.service_amount)) : ""}
          ${d.round_off ? row("Round off", fmt(d.round_off)) : ""}
          ${row("Total", fmt(d.total), "grand")}</div>
        <div class="row" style="margin-top:.7rem">
          <button class="btn danger small" data-act="cancel">Cancel order</button>
          <button class="btn small" data-act="print" ${d.items.length ? "" : "disabled"}>Print bill</button></div>
        <button class="btn primary block" data-act="pay" style="margin-top:.6rem" ${d.items.length ? "" : "disabled"}>
          Take payment · ${fmt(d.total)}</button></div>`;
  }

  /** Run one change; on failure show why and re-sync with the server. */
  async function mutate(fn) {
    try { order = await fn(); drawTicket(); }
    catch (e) {
      toast(e.message, "error");
      try { order = await get(`/api/orders/${id}`); } catch { /* keep old copy */ }
      if (order.status !== "open") return reroute();
      await loadMenu().catch(() => {});
      drawMenu(); drawTicket();
    }
  }
  const lineUrl = (lineId) => `/api/orders/${id}/items/${lineId}`;

  el.addEventListener("click", (e) => {
    const cat = e.target.closest("[data-cat]");
    if (cat) { activeCat = Number(cat.dataset.cat); return drawMenu(); }
    const add = e.target.closest("[data-add]");
    if (add) return mutate(() => post(`/api/orders/${id}/items`, { menu_item_id: Number(add.dataset.add), qty: 1 }));

    const act = e.target.closest("[data-act]")?.dataset.act;
    const line = e.target.closest("[data-line]");
    const found = line && order.items.find((i) => i.id === Number(line.dataset.line));
    if (act === "inc") mutate(() => patch(lineUrl(found.id), { qty: found.qty + 1 }));
    else if (act === "dec") mutate(() => found.qty > 1 ? patch(lineUrl(found.id), { qty: found.qty - 1 }) : del(lineUrl(found.id)));
    else if (act === "remove") mutate(() => del(lineUrl(found.id)));
    else if (act === "apply-discount") applyDiscount();
    else if (act === "cancel") openCancel();
    else if (act === "print") printReceipt(order);
    else if (act === "pay") openPayment();
  });

  el.addEventListener("change", (e) => {
    if (e.target.id === "disc-type") {
      const none = e.target.value === "none";
      $("#disc-val").disabled = none;
      if (none) $("#disc-val").value = "";
    } else if (e.target.id === "cust") {
      mutate(() => patch(`/api/orders/${id}`, { customer_name: e.target.value }));
    } else if (e.target.dataset.act === "note") {
      const lineId = e.target.closest("[data-line]").dataset.line;
      mutate(() => patch(lineUrl(lineId), { notes: e.target.value }));
    }
  });

  el.addEventListener("input", (e) => {
    if (e.target.id === "q") { query = e.target.value.trim(); drawMenu(); }
  });
  el.addEventListener("keydown", (e) => {
    if (e.target.id === "q" && e.key === "Enter") {
      const first = visibleItems().find((i) => i.is_available);
      if (first) { mutate(() => post(`/api/orders/${id}/items`, { menu_item_id: first.id, qty: 1 })); e.target.select(); }
    }
    if (e.target.id === "disc-val" && e.key === "Enter") applyDiscount();
  });

  function applyDiscount() {
    const type = $("#disc-type").value;
    if (type === "none") return mutate(() => patch(`/api/orders/${id}`, { discount_type: "none" }));
    const value = toPaise($("#disc-val").value); // percent -> basis points, rupees -> paise (both x100)
    if (value === null) return toast("Enter a discount amount of 0 or more.", "error");
    if (type === "percent" && value > 10000) return toast("A percent discount can't be more than 100.", "error");
    mutate(() => patch(`/api/orders/${id}`, { discount_type: type, discount_value: value }));
  }

  function openCancel() {
    const d = openModal(`<form id="cancel-form"><h3>Cancel this order?</h3>
      <p class="muted">Nothing on it will be billed. This can't be undone.</p>
      <label class="field">Reason (optional)<input type="text" name="reason" maxlength="200" autofocus></label>
      <div class="modal-actions"><button type="button" class="btn" data-close>Keep order</button>
      <button class="btn danger">Cancel order</button></div></form>`);
    d.querySelector("[data-close]").onclick = closeModal;
    d.querySelector("form").onsubmit = async (ev) => {
      ev.preventDefault();
      try {
        await post(`/api/orders/${id}/cancel`, { reason: new FormData(ev.target).get("reason") });
        closeModal(); toast("Order cancelled"); goto("#/floor");
      } catch (err) { toast(err.message, "error"); }
    };
  }

  function openPayment() {
    if (!order.items.length) return toast("Add at least one item first.", "error");
    const total = order.total;
    const quick = [...new Set([total, ...[10000, 50000, 100000].map((s) => Math.ceil(total / s) * s)])].filter((v) => v >= total);
    const d = openModal(`<form id="pay-form"><h3>Take payment</h3>
      <div class="muted">${title()} · Order #${order.id}</div>
      <div class="pay-total">${fmt(total)}</div>
      <div class="seg" role="radiogroup" aria-label="Payment method">
        <label><input type="radio" name="method" value="cash" checked>Cash</label>
        <label><input type="radio" name="method" value="card">Card</label>
        <label><input type="radio" name="method" value="upi">UPI</label></div>
      <div id="cash-box">
        <label class="field">Cash received<input type="number" name="tendered" min="0" step="0.01" inputmode="decimal" value="${(total / 100).toFixed(2)}"></label>
        <div class="chips">${quick.map((v) => `<button type="button" class="chip" data-quick="${v}">${v === total ? "Exact" : fmt(v)}</button>`).join("")}</div>
        <div class="change-box" id="change"></div></div>
      <div class="modal-actions"><button type="button" class="btn" data-close>Back</button>
        <button class="btn primary" id="confirm-pay">Confirm payment</button></div></form>`);
    const form = d.querySelector("form"), confirm = d.querySelector("#confirm-pay");
    const cash = () => form.method.value === "cash";
    const refresh = () => {
      d.querySelector("#cash-box").hidden = !cash();
      const got = toPaise(form.tendered.value), box = d.querySelector("#change");
      const ok = !cash() || (got !== null && got >= total);
      box.classList.toggle("short", !ok);
      box.textContent = got === null ? "Enter the cash received." : got >= total ? `Change to return: ${fmt(got - total)}` : `Short by ${fmt(total - got)}`;
      confirm.disabled = !ok;
    };
    form.addEventListener("input", refresh); form.addEventListener("change", refresh);
    d.querySelectorAll("[data-quick]").forEach((b) => b.onclick = () => { form.tendered.value = (b.dataset.quick / 100).toFixed(2); refresh(); });
    d.querySelector("[data-close]").onclick = closeModal;
    refresh(); form.tendered.select();
    form.onsubmit = async (ev) => {
      ev.preventDefault();
      confirm.disabled = true; // stop double-taps from submitting twice
      try {
        order = await post(`/api/orders/${id}/pay`, { method: form.method.value, amount_paid: toPaise(form.tendered.value) ?? 0 });
        closeModal(); toast(`Paid · ${order.bill_no}`); showReceipt(order);
      } catch (err) { toast(err.message, "error"); confirm.disabled = false; }
    };
  }

  function showReceipt(o) {
    const d = openModal(`${receiptHTML(o)}<div class="modal-actions">
      <button class="btn" data-print>Print bill</button><button class="btn primary" data-done>Done</button></div>`);
    d.querySelector("[data-print]").onclick = () => printReceipt(o);
    d.querySelector("[data-done]").onclick = closeModal;
    // A dialog's "close" event is queued, so ignore stale ones fired while it is open again.
    const onClose = () => { if (d.open) return; d.removeEventListener("close", onClose); goto("#/floor"); };
    d.addEventListener("close", onClose);
  }

  drawMenu(); drawTicket();
  if (matchMedia("(min-width: 900px)").matches) $("#q").focus();
}
