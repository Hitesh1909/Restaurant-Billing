// Admin screens: menu & categories, restaurant settings and dining tables.
import { get, post, put, del } from "./api.js";
import { state, fmt, loadMenu } from "./state.js";
import { esc, toPaise, toast, openModal, closeModal, confirmBox } from "./util.js";

/** Open a modal form; `onSave(formData)` should throw an Error with a message to show inline. */
function formModal(title, fieldsHTML, submitLabel, onSave) {
  const d = openModal(`<form><h3>${esc(title)}</h3><div id="form-error"></div>${fieldsHTML}
    <div class="modal-actions"><button type="button" class="btn" data-close>Cancel</button>
    <button class="btn primary">${esc(submitLabel)}</button></div></form>`);
  d.querySelector("[data-close]").onclick = closeModal;
  d.querySelector("input, select")?.focus();
  d.querySelector("form").onsubmit = async (e) => {
    e.preventDefault();
    const button = e.target.querySelector(".btn.primary");
    button.disabled = true;
    try { await onSave(e.target); closeModal(); }
    catch (err) { d.querySelector("#form-error").innerHTML = `<div class="error-box">${esc(err.message)}</div>`; button.disabled = false; }
  };
}

/* ================================================================= MENU */
export async function menuView(el) {
  let activeCat = 0;
  const refresh = async () => { await loadMenu(); draw(); };

  function draw() {
    const items = state.menu.filter((i) => !activeCat || i.category_id === activeCat);
    const count = (id) => state.menu.filter((i) => i.category_id === id).length;
    el.innerHTML = `<div class="page-head"><h1>Menu</h1><button class="btn primary" data-act="new-item">Add item</button></div>
      <div class="two-col">
        <aside class="card"><h3>Categories</h3>
          <ul class="list">
            <li data-cat="0" class="${activeCat === 0 ? "active" : ""}"><span>All items</span><span class="muted">${state.menu.length}</span></li>
            ${state.categories.map((c) => `<li data-cat="${c.id}" class="${activeCat === c.id ? "active" : ""}">
              <span>${esc(c.name)} <span class="muted">${count(c.id)}</span></span>
              <span class="row"><button class="btn small" data-act="rename-cat" data-id="${c.id}">Rename</button>
              <button class="btn small danger" data-act="del-cat" data-id="${c.id}" aria-label="Delete ${esc(c.name)}">✕</button></span></li>`).join("")}
          </ul>
          <form id="cat-form" class="row"><input class="grow" type="text" name="name" maxlength="40" placeholder="New category" required>
          <button class="btn">Add</button></form></aside>
        <div class="scroll-x">${items.length ? `<table class="data"><thead><tr><th>Item</th><th>Category</th><th class="right">Price</th><th>Status</th><th></th></tr></thead><tbody>
          ${items.map((i) => `<tr><td><span class="dot ${i.is_veg ? "" : "nonveg"}"></span>${esc(i.name)}</td>
            <td class="muted">${esc(i.category_name || "-")}</td><td class="right money">${fmt(i.price)}</td>
            <td><span class="badge ${i.is_available ? "paid" : "off"}">${i.is_available ? "Available" : "Sold out"}</span></td>
            <td class="right"><div class="row" style="justify-content:flex-end">
              <button class="btn small" data-act="toggle" data-id="${i.id}">${i.is_available ? "Mark sold out" : "Mark available"}</button>
              <button class="btn small" data-act="edit-item" data-id="${i.id}">Edit</button>
              <button class="btn small danger" data-act="del-item" data-id="${i.id}" aria-label="Delete ${esc(i.name)}">✕</button></div></td></tr>`).join("")}
          </tbody></table>` : `<p class="card empty">No items here yet. Add one with "Add item".</p>`}</div></div>`;
  }

  function itemForm(item) {
    if (!state.categories.length) return toast("Add a category first.", "error");
    const options = state.categories.map((c) =>
      `<option value="${c.id}" ${(item?.category_id ?? activeCat) === c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("");
    formModal(item ? "Edit item" : "Add item", `
      <label class="field">Name<input type="text" name="name" maxlength="80" required value="${esc(item?.name || "")}"></label>
      <label class="field">Category<select name="category_id">${options}</select></label>
      <label class="field">Price (${esc(state.settings.currency)})<input type="number" name="price" min="0" step="0.01" required value="${item ? (item.price / 100).toFixed(2) : ""}"></label>
      <label class="row"><input type="checkbox" name="is_veg" ${item?.is_veg ?? 1 ? "checked" : ""}> Vegetarian</label>
      <label class="row" style="margin-top:.4rem"><input type="checkbox" name="is_available" ${item?.is_available ?? 1 ? "checked" : ""}> Available today</label>`,
      item ? "Save changes" : "Add item", async (f) => {
        const price = toPaise(f.price.value);
        if (price === null) throw new Error("Enter a price of 0 or more.");
        const body = { name: f.name.value, category_id: Number(f.category_id.value), price,
          is_veg: f.is_veg.checked, is_available: f.is_available.checked };
        await (item ? put(`/api/menu-items/${item.id}`, body) : post("/api/menu-items", body));
        toast(item ? "Item saved" : "Item added"); await refresh();
      });
  }

  el.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]");
    try {
      if (!btn) {
        const li = e.target.closest("[data-cat]");
        if (li) { activeCat = Number(li.dataset.cat); draw(); }
        return;
      }
      const id = Number(btn.dataset.id);
      const item = state.menu.find((i) => i.id === id);
      const cat = state.categories.find((c) => c.id === id);
      switch (btn.dataset.act) {
        case "new-item": itemForm(null); break;
        case "edit-item": itemForm(item); break;
        case "toggle":
          await put(`/api/menu-items/${id}`, { is_available: !item.is_available });
          toast(item.is_available ? `${item.name} marked sold out` : `${item.name} is available`); await refresh(); break;
        case "del-item":
          if (await confirmBox(`Delete "${item.name}" from the menu? Past bills keep it.`, "Delete", true)) {
            await del(`/api/menu-items/${id}`); toast("Item deleted"); await refresh();
          } break;
        case "rename-cat":
          formModal("Rename category", `<label class="field">Name<input type="text" name="name" maxlength="40" required value="${esc(cat.name)}"></label>`,
            "Save", async (f) => { await put(`/api/categories/${id}`, { name: f.name.value }); toast("Category renamed"); await refresh(); }); break;
        case "del-cat":
          if (await confirmBox(`Delete the category "${cat.name}"?`, "Delete", true)) {
            await del(`/api/categories/${id}`); if (activeCat === id) activeCat = 0; toast("Category deleted"); await refresh();
          } break;
      }
    } catch (err) { toast(err.message, "error"); }
  });
  el.addEventListener("submit", async (e) => {
    if (e.target.id !== "cat-form") return;
    e.preventDefault();
    try { await post("/api/categories", { name: e.target.name.value }); toast("Category added"); await refresh(); }
    catch (err) { toast(err.message, "error"); }
  });
  draw();
}

/* ================================================================ SETUP */
export async function setupView(el) {
  async function draw() {
    const s = state.settings, tables = await get("/api/tables");
    el.innerHTML = `<div class="page-head"><h1>Setup</h1></div>
      <div class="two-eq">
        <form class="card" id="settings-form"><h3>Restaurant and billing</h3><div id="settings-error"></div>
          <label class="field">Restaurant name<input type="text" name="restaurant_name" maxlength="80" required value="${esc(s.restaurant_name)}"></label>
          <label class="field">Address (printed on bills)<input type="text" name="address" maxlength="200" value="${esc(s.address)}"></label>
          <label class="field">GSTIN (optional)<input type="text" name="gstin" maxlength="20" value="${esc(s.gstin)}"></label>
          <div class="row">
            <label class="field grow">Currency symbol<input type="text" name="currency" maxlength="3" required value="${esc(s.currency)}"></label>
            <label class="field grow">Bill prefix<input type="text" name="bill_prefix" maxlength="8" required value="${esc(s.bill_prefix)}"></label></div>
          <div class="row">
            <label class="field grow">Tax / GST (%)<input type="number" name="tax_percent" min="0" max="100" step="0.01" required value="${esc(s.tax_percent)}"></label>
            <label class="field grow">Service charge (%)<input type="number" name="service_percent" min="0" max="100" step="0.01" required value="${esc(s.service_percent)}"></label></div>
          <p class="muted">Rate changes apply to open orders the next time they are edited or billed. Paid bills never change.</p>
          <button class="btn primary">Save settings</button></form>
        <div class="card"><h3>Tables</h3>
          <ul class="list">${tables.map((t) => `<li style="cursor:default"><span><b>${esc(t.name)}</b> <span class="muted">${t.seats} seats</span></span>
            <span class="row"><button class="btn small" data-act="edit-table" data-id="${t.id}">Edit</button>
            <button class="btn small danger" data-act="del-table" data-id="${t.id}" aria-label="Remove ${esc(t.name)}">✕</button></span></li>`).join("")
            || `<li class="muted" style="cursor:default">No tables yet.</li>`}</ul>
          <button class="btn" data-act="new-table">Add table</button></div></div>`;
    el._tables = tables;
  }

  function tableForm(t) {
    formModal(t ? "Edit table" : "Add table", `
      <label class="field">Table name<input type="text" name="name" maxlength="20" required value="${esc(t?.name || "")}"></label>
      <label class="field">Seats<input type="number" name="seats" min="1" max="50" required value="${t?.seats ?? 4}"></label>`,
      t ? "Save" : "Add table", async (f) => {
        const body = { name: f.name.value, seats: Number(f.seats.value) };
        await (t ? put(`/api/tables/${t.id}`, body) : post("/api/tables", body));
        toast(t ? "Table saved" : "Table added"); await draw();
      });
  }

  el.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const t = el._tables.find((x) => x.id === Number(btn.dataset.id));
    try {
      if (btn.dataset.act === "new-table") tableForm(null);
      else if (btn.dataset.act === "edit-table") tableForm(t);
      else if (btn.dataset.act === "del-table" && await confirmBox(`Remove table ${t.name}?`, "Remove", true)) {
        await del(`/api/tables/${t.id}`); toast("Table removed"); await draw();
      }
    } catch (err) { toast(err.message, "error"); }
  });
  el.addEventListener("submit", async (e) => {
    if (e.target.id !== "settings-form") return;
    e.preventDefault();
    const f = e.target, box = el.querySelector("#settings-error");
    try {
      const saved = await put("/api/settings", Object.fromEntries(
        ["restaurant_name", "address", "gstin", "currency", "bill_prefix", "tax_percent", "service_percent"].map((k) => [k, f[k].value])));
      Object.assign(state.settings, saved);
      document.querySelector(".brand").textContent = saved.restaurant_name;
      box.innerHTML = ""; toast("Settings saved"); await draw();
    } catch (err) { box.innerHTML = `<div class="error-box">${esc(err.message)}</div>`; }
  });
  await draw();
}
