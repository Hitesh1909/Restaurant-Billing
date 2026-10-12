// Thin fetch wrapper: JSON in / JSON out, and errors carry the server's message.
export async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const err = new Error(data?.error || `Request failed (${res.status})`);
    err.status = res.status;
    if (res.status === 401 && !url.includes("/auth/")) window.dispatchEvent(new Event("session-expired"));
    throw err;
  }
  return data;
}
export const get = (url) => api("GET", url);
export const post = (url, body = {}) => api("POST", url, body);
export const put = (url, body = {}) => api("PUT", url, body);
export const patch = (url, body = {}) => api("PATCH", url, body);
export const del = (url) => api("DELETE", url);
