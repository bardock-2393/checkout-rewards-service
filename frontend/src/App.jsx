import { useEffect, useState } from "react";
import { api } from "./api";
import "./App.css";

function money(paise) {
  return `₹${(paise / 100).toFixed(2)}`;
}

export default function App() {
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState(null);
  const [qtyByProduct, setQtyByProduct] = useState({});
  const [couponCode, setCouponCode] = useState("");
  const [order, setOrder] = useState(null);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);
  const [adminMessage, setAdminMessage] = useState("");

  async function refreshProducts() {
    setProducts(await api.listProducts());
  }

  async function startNewCart() {
    const { cart_id } = await api.createCart();
    setCart(await api.getCart(cart_id));
    setOrder(null);
    setError("");
    setCouponCode("");
  }

  useEffect(() => {
    refreshProducts();
    startNewCart();
  }, []);

  async function handleAddItem(productId) {
    setError("");
    const quantity = qtyByProduct[productId] || 1;
    try {
      const updated = await api.addItem(cart.cart_id, productId, quantity);
      setCart(updated);
      await refreshProducts();
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleUpdateQty(productId, quantity) {
    setError("");
    try {
      setCart(await api.updateItem(cart.cart_id, productId, quantity));
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleRemoveItem(productId) {
    setError("");
    try {
      setCart(await api.removeItem(cart.cart_id, productId));
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleCheckout() {
    setError("");
    try {
      const result = await api.checkout(cart.cart_id, couponCode);
      setOrder(result);
      setCart(await api.getCart(cart.cart_id));
      await refreshProducts();
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleGenerateCoupon() {
    setAdminMessage("");
    try {
      const coupon = await api.generateCoupon();
      setAdminMessage(`Coupon issued: ${coupon.code} (${coupon.percent_off}% off)`);
    } catch (e) {
      setAdminMessage(e.message);
    }
  }

  async function handleRefreshReport() {
    setReport(await api.getReport());
  }

  if (!cart) return <p className="page">Loading...</p>;

  return (
    <div className="page">
      <h1>Checkout &amp; Rewards</h1>

      <section>
        <h2>Products</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Price</th>
              <th>Stock</th>
              <th>Qty</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{money(p.price_paise)}</td>
                <td>{p.stock}</td>
                <td>
                  <input
                    type="number"
                    min="1"
                    value={qtyByProduct[p.id] || 1}
                    onChange={(e) =>
                      setQtyByProduct({ ...qtyByProduct, [p.id]: Number(e.target.value) })
                    }
                  />
                </td>
                <td>
                  <button disabled={cart.status !== "open"} onClick={() => handleAddItem(p.id)}>
                    Add to cart
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Cart ({cart.status})</h2>
        {cart.items.length === 0 ? (
          <p>Empty.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Unit price</th>
                <th>Qty</th>
                <th>Subtotal</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {cart.items.map((item) => (
                <tr key={item.product_id}>
                  <td>{item.name}</td>
                  <td>{money(item.unit_price_paise)}</td>
                  <td>
                    <input
                      type="number"
                      min="1"
                      value={item.quantity}
                      disabled={cart.status !== "open"}
                      onChange={(e) => handleUpdateQty(item.product_id, Number(e.target.value))}
                    />
                  </td>
                  <td>{money(item.subtotal_paise)}</td>
                  <td>
                    <button
                      disabled={cart.status !== "open"}
                      onClick={() => handleRemoveItem(item.product_id)}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p>
          <strong>Subtotal: {money(cart.subtotal_paise)}</strong>
        </p>

        <input
          placeholder="Coupon code (optional)"
          value={couponCode}
          onChange={(e) => setCouponCode(e.target.value)}
          disabled={cart.status !== "open"}
        />
        <button disabled={cart.status !== "open"} onClick={handleCheckout}>
          Checkout
        </button>
        <button onClick={startNewCart}>Start new cart</button>

        {error && <p className="error">{error}</p>}

        {order && (
          <div className="order">
            <h3>Order {order.order_id}</h3>
            <p>Subtotal: {money(order.subtotal_paise)}</p>
            <p>Discount: {money(order.discount_paise)}</p>
            <p>
              <strong>Total: {money(order.total_paise)}</strong>
            </p>
            {order.coupon_code && <p>Coupon applied: {order.coupon_code}</p>}
          </div>
        )}
      </section>

      <section>
        <h2>Admin</h2>
        <button onClick={handleGenerateCoupon}>Generate coupon</button>
        <button onClick={handleRefreshReport}>Refresh report</button>
        {adminMessage && <p>{adminMessage}</p>}
        {report && (
          <table>
            <tbody>
              <tr>
                <td>Total orders</td>
                <td>{report.total_orders}</td>
              </tr>
              <tr>
                <td>Gross revenue</td>
                <td>{money(report.gross_revenue_paise)}</td>
              </tr>
              <tr>
                <td>Total discounts</td>
                <td>{money(report.total_discounts_paise)}</td>
              </tr>
              <tr>
                <td>Net revenue</td>
                <td>{money(report.net_revenue_paise)}</td>
              </tr>
              <tr>
                <td>Coupons generated / available / redeemed</td>
                <td>
                  {report.coupons_generated} / {report.coupons_available} /{" "}
                  {report.coupons_redeemed}
                </td>
              </tr>
              <tr>
                <td>Purchased qty by product</td>
                <td>{JSON.stringify(report.purchased_quantity_by_product)}</td>
              </tr>
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
