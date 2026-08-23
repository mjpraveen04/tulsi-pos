import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import PaymentModal from "../components/PaymentModal";
import ProductPhoto from "../components/ProductPhoto";
import { money, plural } from "../lib/format";

const GST_RATE = 0.05;

function stockBadge(product) {
  if (product.is_sold_out) return { className: " is-out", label: "SOLD OUT" };
  if (product.is_low_stock) return { className: " is-low", label: `${product.stock} left` };
  return { className: "", label: `${product.stock} in stock` };
}

export default function Register() {
  const { user } = useAuth();
  const [category, setCategory] = useState("All");
  const [cart, setCart] = useState([]); // [{ productId, qty }]
  const [payOpen, setPayOpen] = useState(false);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["menu"],
    queryFn: () => api("/register/menu"),
    // Stock moves under the cashier's feet; refetch when the tab regains focus.
    refetchOnWindowFocus: true,
  });

  const products = data?.products ?? [];
  const byId = useMemo(
    () => Object.fromEntries(products.map((product) => [product.id, product])),
    [products],
  );
  const categories = useMemo(
    () => ["All", ...new Set(products.map((product) => product.category))],
    [products],
  );
  const visible =
    category === "All" ? products : products.filter((p) => p.category === category);

  // Cart lines resolved against the live menu, so a stock change is reflected
  // immediately in the steppers.
  const lines = cart
    .map((line) => ({ ...line, product: byId[line.productId] }))
    .filter((line) => line.product);

  const subtotal = lines.reduce(
    (sum, line) => sum + Number(line.product.price) * line.qty,
    0,
  );
  const gst = Math.round(subtotal * GST_RATE * 100) / 100;
  const total = Math.round((subtotal + gst) * 100) / 100;
  const itemCount = lines.reduce((sum, line) => sum + line.qty, 0);

  function addToCart(product) {
    if (product.stock <= 0) return;
    setCart((current) => {
      const existing = current.find((line) => line.productId === product.id);
      if (!existing) return [...current, { productId: product.id, qty: 1 }];
      // FR-18: the stepper stops at what's actually on the shelf.
      if (existing.qty >= product.stock) return current;
      return current.map((line) =>
        line.productId === product.id ? { ...line, qty: line.qty + 1 } : line,
      );
    });
  }

  function decrement(productId) {
    setCart((current) =>
      current.flatMap((line) => {
        if (line.productId !== productId) return [line];
        return line.qty <= 1 ? [] : [{ ...line, qty: line.qty - 1 }];
      }),
    );
  }

  return (
    <div className="register">
      <section className="menu-pane">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {categories.map((name) => (
            <button
              key={name}
              type="button"
              className={`chip${category === name ? " is-active" : ""}`}
              onClick={() => setCategory(name)}
              aria-pressed={category === name}
            >
              {name}
            </button>
          ))}
        </div>

        {isLoading && <div className="empty">Loading the menu…</div>}
        {isError && <div className="empty">{error.detail}</div>}
        {!isLoading && !isError && visible.length === 0 && (
          <div className="empty">
            Nothing on the menu here yet. A manager can add items in Inventory.
          </div>
        )}

        <div className="menu-grid">
          {visible.map((product) => {
            const badge = stockBadge(product);
            const inCart =
              cart.find((line) => line.productId === product.id)?.qty ?? 0;
            return (
              <div
                key={product.id}
                className={`product-card${product.is_sold_out ? " is-sold-out" : ""}`}
              >
                <div className="product-photo">
                  <ProductPhoto product={product} />
                  <span className={`stock-badge${badge.className}`}>{badge.label}</span>
                </div>
                <button
                  type="button"
                  className="product-add"
                  disabled={product.is_sold_out || inCart >= product.stock}
                  onClick={() => addToCart(product)}
                >
                  <span className="product-cat">{product.category}</span>
                  <span className="product-name">{product.name}</span>
                  <span className="product-price">{money(product.price)}</span>
                </button>
              </div>
            );
          })}
        </div>
      </section>

      <aside className="cart" aria-label="Current order">
        <div className="cart-head">
          <div
            style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}
          >
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 800, letterSpacing: "-.3px" }}>
              Current Order
            </h2>
            <button
              type="button"
              onClick={() => setCart([])}
              disabled={lines.length === 0}
              style={{
                border: "none",
                background: "none",
                color: "var(--ink-soft)",
                fontSize: 12,
                fontWeight: 600,
                padding: 2,
                opacity: lines.length ? 1 : 0.4,
              }}
            >
              Clear
            </button>
          </div>
          <div
            style={{
              fontSize: 12,
              color: "var(--ink-soft)",
              fontWeight: 500,
              marginTop: 2,
            }}
          >
            {/* The bill number is allocated by the server when the sale commits,
                so the cart shows who is ringing up rather than a guessed number. */}
            {itemCount ? plural(itemCount, "item") : "No items yet"} · {user?.name}
          </div>
        </div>

        <div className="cart-lines">
          {lines.length === 0 && (
            <div style={{ textAlign: "center", padding: "48px 20px" }} className="empty">
              Tap items to start an order
            </div>
          )}
          {lines.map((line) => (
            <div key={line.productId} className="cart-line pop">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="truncate" style={{ fontWeight: 700, fontSize: 13.5 }}>
                  {line.product.name}
                </div>
                <div
                  style={{ fontSize: 11.5, color: "var(--ink-soft)", fontWeight: 600 }}
                >
                  {money(line.product.price)} each
                </div>
              </div>
              <div className="stepper">
                <button
                  type="button"
                  onClick={() => decrement(line.productId)}
                  aria-label={`Remove one ${line.product.name}`}
                >
                  −
                </button>
                <span className="qty">{line.qty}</span>
                <button
                  type="button"
                  onClick={() => addToCart(line.product)}
                  disabled={line.qty >= line.product.stock}
                  aria-label={`Add one ${line.product.name}`}
                >
                  +
                </button>
              </div>
              <div
                style={{ width: 66, textAlign: "right", fontWeight: 800, fontSize: 13.5 }}
              >
                {money(Number(line.product.price) * line.qty)}
              </div>
            </div>
          ))}
        </div>

        <div className="cart-totals">
          <div className="total-row">
            <span>Subtotal</span>
            <span>{money(subtotal)}</span>
          </div>
          <div className="total-row" style={{ marginBottom: 10 }}>
            <span>GST (5%)</span>
            <span>{money(gst)}</span>
          </div>
          <div className="grand-total">
            <span>Total</span>
            <span>{money(total)}</span>
          </div>
          <button
            type="button"
            className="charge-btn"
            disabled={lines.length === 0}
            onClick={() => setPayOpen(true)}
          >
            Charge {money(total)}
          </button>
        </div>
      </aside>

      {payOpen && (
        <PaymentModal
          lines={lines}
          subtotal={subtotal}
          gst={gst}
          total={total}
          itemCount={itemCount}
          onClose={() => setPayOpen(false)}
          onCompleted={() => setCart([])}
        />
      )}
    </div>
  );
}
