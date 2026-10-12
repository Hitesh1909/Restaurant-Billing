// Small DOM / formatting helpers shared by every view.

/** Escape text before putting it into an HTML string (prevents XSS from names and notes). */
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export const money = (paise, symbol = "₹") =>
  (paise < 0 ? "-" : "") + symbol +
  (Math.abs(paise) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** "120" or "120.50" typed by a person -> integer paise (or null if invalid). */
export function toPaise(text) {
  const n = Number(String(text).trim());
  return Number.isFinite(n) && n >= 0 && String(text).trim() !== "" ? Math.round(n * 100) : null;
}

export const todayISO = () => new Date().toLocaleDateString("en-CA"); // local YYYY-MM-DD

export const debounce = (fn, ms = 250) => {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
};

export function toast(message, type = "info") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), type === "error" ? 5000 : 2500);
}

const dialog = () => document.getElementById("modal");
export function openModal(html) {
  const d = dialog();
  d.innerHTML = `<div class="modal-body">${html}</div>`;
  if (!d.open) d.showModal();
  return d;
}
export function closeModal() {
  const d = dialog();
  if (d.open) d.close();
}
document.addEventListener("click", (e) => {
  if (e.target === dialog()) closeModal(); // click on the dim backdrop
});

/** Ask a yes/no question in a modal. Resolves true / false. */
export function confirmBox(message, confirmLabel = "Confirm", danger = false) {
  return new Promise((resolve) => {
    const d = openModal(`<h3>${esc(message)}</h3>
      <div class="modal-actions"><button class="btn" data-no>Keep it</button>
      <button class="btn ${danger ? "danger" : "primary"}" data-yes>${esc(confirmLabel)}</button></div>`);
    const finish = (v) => { d.removeEventListener("close", onClose); closeModal(); resolve(v); };
    const onClose = () => { if (!d.open) finish(false); }; // Esc / backdrop; ignore stale close events
    d.addEventListener("close", onClose);
    d.querySelector("[data-yes]").onclick = () => finish(true);
    d.querySelector("[data-no]").onclick = () => finish(false);
  });
}
