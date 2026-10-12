// App-wide state shared between views.
import { get } from "./api.js";
import { money } from "./util.js";

export const state = { user: null, settings: {}, categories: [], menu: [] };

export async function loadSettings() { state.settings = await get("/api/settings"); }
export async function loadMenu() {
  const data = await get("/api/menu");
  state.categories = data.categories;
  state.menu = data.items;
}
/** Format paise using the restaurant's currency symbol. */
export const fmt = (paise) => money(paise, state.settings.currency || "₹");
export const isAdmin = () => state.user?.role === "admin";
