// Entry point: sign-in screen, app shell and hash-based routing.
import { get, post } from "./api.js";
import { state, loadMenu, loadSettings, isAdmin } from "./state.js";
import { esc, toast, closeModal } from "./util.js";
import { floorView, orderView } from "./pos.js";
import { historyView } from "./history.js";
import { menuView, setupView } from "./admin.js";
import { reportsView } from "./reports.js";

const app = document.getElementById("app");
const ROUTES = {
  floor:   { title: "Floor",   view: floorView },
  order:   { title: "Order",   view: orderView, hidden: true },
  orders:  { title: "Orders",  view: historyView },
  menu:    { title: "Menu",    view: menuView,    admin: true },
  reports: { title: "Reports", view: reportsView, admin: true },
  setup:   { title: "Setup",   view: setupView,   admin: true },
};
let cleanup = null;

function renderLogin(message = "") {
  cleanup?.(); cleanup = null; closeModal();
  app.innerHTML = `<div class="login-wrap"><form class="card login-card" id="login-form">
    <h1>Restaurant Billing</h1><p class="muted">Sign in to start taking orders.</p>
    ${message ? `<div class="error-box">${esc(message)}</div>` : ""}
    <label class="field">Username<input type="text" name="username" autocomplete="username" required autofocus></label>
    <label class="field">Password<input type="password" name="password" autocomplete="current-password" required></label>
    <button class="btn primary block">Sign in</button>
    <p class="demo-hint">Demo logins: <b>admin</b> / admin123 · <b>cashier</b> / cashier123</p></form></div>`;
  document.getElementById("login-form").onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    try {
      const { user } = await post("/api/auth/login", { username: f.get("username"), password: f.get("password") });
      state.user = user;
      await Promise.all([loadSettings(), loadMenu()]);
      location.hash = "#/floor";
      renderShell(); route();
    } catch (err) { renderLogin(err.message); }
  };
}

function renderShell() {
  const links = Object.entries(ROUTES).filter(([, r]) => !r.hidden && (!r.admin || isAdmin()))
    .map(([key, r]) => `<a href="#/${key}" data-nav="${key}">${r.title}</a>`).join("");
  app.innerHTML = `<header class="topbar"><div class="brand">${esc(state.settings.restaurant_name)}</div>
    <nav>${links}</nav>
    <div class="who"><span>${esc(state.user.name)}</span><button class="btn small" id="logout">Sign out</button></div></header>
    <main id="view"></main>`;
  document.getElementById("logout").onclick = async () => {
    await post("/api/auth/logout").catch(() => {});
    state.user = null; renderLogin();
  };
}

async function route() {
  if (!state.user) return;
  cleanup?.(); cleanup = null; closeModal();
  const [name = "floor", ...args] = location.hash.replace(/^#\/?/, "").split("/");
  let def = ROUTES[name] || ROUTES.floor;
  if (def.admin && !isAdmin()) def = ROUTES.floor;
  const key = Object.keys(ROUTES).find((k) => ROUTES[k] === def);
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === (key === "order" ? "floor" : key)));
  const section = document.createElement("section");
  document.getElementById("view").replaceChildren(section);
  try {
    cleanup = (await def.view(section, ...args)) || null;
  } catch (err) {
    section.innerHTML = `<div class="error-box">${esc(err.message)}</div><a class="btn" href="#/floor">Back to floor</a>`;
  }
}

window.addEventListener("hashchange", route);
window.addEventListener("session-expired", () => { state.user = null; renderLogin("Your session ended. Please sign in again."); });

(async function boot() {
  try {
    const { user } = await get("/api/auth/me");
    state.user = user;
    await Promise.all([loadSettings(), loadMenu()]);
    renderShell(); route();
  } catch (err) {
    if (err.status === 401) renderLogin();
    else app.innerHTML = `<div class="login-wrap"><div class="error-box">Can't reach the server: ${esc(err.message)}</div></div>`;
  }
})();
