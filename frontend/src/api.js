const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  const body = await res.json();
  if (!res.ok) {
    throw new Error(body.message ?? body.detail ?? "request failed");
  }
  return body;
}

export const api = {
  listProducts: () => request("/products"),
  createCart: () => request("/carts", { method: "POST" }),
  getCart: (cartId) => request(`/carts/${cartId}`),
  addItem: (cartId, productId, quantity) =>
    request(`/carts/${cartId}/items`, {
      method: "POST",
      body: JSON.stringify({ product_id: productId, quantity }),
    }),
  updateItem: (cartId, productId, quantity) =>
    request(`/carts/${cartId}/items/${productId}`, {
      method: "PATCH",
      body: JSON.stringify({ quantity }),
    }),
  removeItem: (cartId, productId) =>
    request(`/carts/${cartId}/items/${productId}`, { method: "DELETE" }),
  checkout: (cartId, couponCode) =>
    request(`/carts/${cartId}/checkout`, {
      method: "POST",
      body: JSON.stringify({ coupon_code: couponCode || null }),
    }),
  generateCoupon: () => request("/admin/coupons/generate", { method: "POST" }),
  getReport: () => request("/admin/report"),
};
