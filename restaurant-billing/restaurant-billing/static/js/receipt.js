// Builds the customer bill (screen preview and print) from an order object.
import { state, fmt } from "./state.js";
import { esc } from "./util.js";

const rate = (bp) => `${+(bp / 100).toFixed(2)}%`;
const METHOD = { cash: "Cash", card: "Card", upi: "UPI" };

export function receiptHTML(o) {
  const s = state.settings;
  const lines = o.items.map((i) => `
    <span>${esc(i.name)}</span><span>${i.qty}</span><span class="right">${fmt(i.unit_price)}</span><span class="right">${fmt(i.unit_price * i.qty)}</span>
    ${i.notes ? `<span class="n">${esc(i.notes)}</span>` : ""}`).join("");
  const row = (label, value, cls = "") => `<div class="r-row ${cls}"><span>${label}</span><span>${value}</span></div>`;
  return `<div class="receipt">
    <div class="r-center"><strong>${esc(s.restaurant_name)}</strong><br>${esc(s.address)}${s.gstin ? `<br>GSTIN: ${esc(s.gstin)}` : ""}</div>
    <hr>
    ${row(o.bill_no ? `Bill ${esc(o.bill_no)}` : `Order #${o.id}`, esc((o.paid_at || o.created_at).slice(0, 16)))}
    ${row(o.order_type === "dine_in" ? `Table ${esc(o.table_name)}` : "Takeaway", esc(o.cashier || ""))}
    ${o.customer_name ? row("Customer", esc(o.customer_name)) : ""}
    <hr>
    <div class="r-items"><span class="h">Item</span><span class="h">Qty</span><span class="h right">Rate</span><span class="h right">Amount</span>${lines}</div>
    <hr>
    ${row("Subtotal", fmt(o.subtotal))}
    ${o.discount_amount ? row(`Discount${o.discount_type === "percent" ? ` (${rate(o.discount_value)})` : ""}`, "-" + fmt(o.discount_amount)) : ""}
    ${o.tax_bp ? row(`Tax (${rate(o.tax_bp)})`, fmt(o.tax_amount)) : ""}
    ${o.service_bp ? row(`Service (${rate(o.service_bp)})`, fmt(o.service_amount)) : ""}
    ${o.round_off ? row("Round off", fmt(o.round_off)) : ""}
    <hr>
    ${row("TOTAL", fmt(o.total), "r-total")}
    ${o.status === "paid" ? `<hr>${row("Paid by", METHOD[o.payment_method])}
      ${o.payment_method === "cash" ? row("Cash received", fmt(o.amount_paid)) + row("Change", fmt(o.change_due)) : ""}
      <div class="r-center" style="margin-top:8px">Thank you! Please visit again.</div>`
    : o.status === "cancelled" ? `<hr><div class="r-center"><strong>CANCELLED</strong><br>${esc(o.cancel_reason || "")}</div>`
    : `<hr><div class="r-center">Not yet paid</div>`}
  </div>`;
}

export function printReceipt(order) {
  const area = document.getElementById("print-area");
  area.innerHTML = receiptHTML(order);
  window.print();
}
