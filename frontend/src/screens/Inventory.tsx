import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";

import { api, ApiError, apiUpload } from "../api/client";
import PhotoPicker from "../components/PhotoPicker";
import { money, timeOfDay } from "../lib/format";
import { moveColor } from "../theme";
import type { Product, ProductCreate, StockMove, StockMoveReason } from "../types";

const CATEGORIES = ["Tiffin", "Snacks", "Beverages", "Meals"];

const MOVE_TEXT: Record<StockMoveReason, (move: StockMove) => string> = {
  OPENING: (move) => `Opening stock · ${move.delta} × ${move.product_name}`,
  RECEIVE: (move) => `Received ${move.delta} × ${move.product_name}`,
  REMOVE: (move) => `Removed ${Math.abs(move.delta)} × ${move.product_name}`,
  SALE: (move) => `Sold ${Math.abs(move.delta)} × ${move.product_name}`,
};

interface ProductForm {
  name: string;
  category: string;
  price: string;
  stock: string;
}

interface AdjustVars {
  id: number;
  delta: number;
  reason: StockMoveReason;
}

export default function Inventory() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ProductForm>({
    name: "",
    category: "Tiffin",
    price: "",
    stock: "",
  });
  const [amounts, setAmounts] = useState<Record<number, string>>({});
  const [error, setError] = useState("");

  const { data: products = [], isLoading } = useQuery<Product[], ApiError>({
    queryKey: ["products"],
    queryFn: () => api<Product[]>("/products"),
  });

  const { data: moves = [] } = useQuery<StockMove[], ApiError>({
    queryKey: ["stock-moves"],
    queryFn: () => api<StockMove[]>("/products/stock-moves?limit=40"),
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["products"] });
    queryClient.invalidateQueries({ queryKey: ["stock-moves"] });
    queryClient.invalidateQueries({ queryKey: ["menu"] });
  }

  const addProduct = useMutation<Product, ApiError, ProductCreate>({
    mutationFn: (body) => api<Product>("/products", { method: "POST", body }),
    onSuccess: () => {
      setForm({ name: "", category: form.category, price: "", stock: "" });
      setError("");
      refresh();
    },
    onError: (err) => setError(err.detail),
  });

  const adjustStock = useMutation<Product, ApiError, AdjustVars>({
    mutationFn: ({ id, delta, reason }) =>
      api<Product>(`/products/${id}/stock`, { method: "POST", body: { delta, reason } }),
    onSuccess: () => {
      setError("");
      refresh();
    },
    onError: (err) => setError(err.detail),
  });

  const uploadPhoto = useMutation<Product, ApiError, { id: number; file: File }>({
    mutationFn: ({ id, file }) => apiUpload<Product>(`/products/${id}/photo`, file),
    onSuccess: () => {
      setError("");
      refresh();
    },
    onError: (err) => setError(err.detail),
  });

  const removePhoto = useMutation<Product, ApiError, number>({
    mutationFn: (id) => api<Product>(`/products/${id}/photo`, { method: "DELETE" }),
    onSuccess: () => {
      setError("");
      refresh();
    },
    onError: (err) => setError(err.detail),
  });

  const archive = useMutation<Product, ApiError, number>({
    mutationFn: (id) => api<Product>(`/products/${id}/archive`, { method: "PATCH" }),
    onSuccess: () => {
      setError("");
      refresh();
    },
    onError: (err) => setError(err.detail),
  });

  const lowCount = products.filter((product) => product.is_low_stock || product.is_sold_out).length;

  function amountFor(id: number): number {
    const raw = amounts[id];
    const parsed = Number.parseInt(raw ?? "1", 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  }

  function submitProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.name.trim()) {
      setError("Give the item a name.");
      return;
    }
    addProduct.mutate({
      name: form.name.trim(),
      category: form.category,
      price: Number(form.price || 0).toFixed(2),
      opening_stock: Number.parseInt(form.stock || "0", 10),
      reorder_level: 6,
    });
  }

  return (
    <div className="inventory">
      <section className="inventory-main">
        <form className="card" style={{ padding: "16px 18px" }} onSubmit={submitProduct}>
          <div className="card-title" style={{ marginBottom: 12 }}>
            Add a menu item
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "flex-end" }}>
            <label className="field" style={{ flex: "2 1 180px" }}>
              <span className="field-label">Name</span>
              <input
                className="input"
                placeholder="e.g. Rava Dosa"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </label>
            <label className="field" style={{ flex: "1 1 120px" }}>
              <span className="field-label">Category</span>
              <select
                className="select"
                value={form.category}
                onChange={(event) => setForm({ ...form, category: event.target.value })}
              >
                {CATEGORIES.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </label>
            <label className="field" style={{ flex: "0 1 96px" }}>
              <span className="field-label">Price ₹</span>
              <input
                className="input"
                type="number"
                min="0"
                step="0.01"
                placeholder="0"
                value={form.price}
                onChange={(event) => setForm({ ...form, price: event.target.value })}
              />
            </label>
            <label className="field" style={{ flex: "0 1 96px" }}>
              <span className="field-label">Stock</span>
              <input
                className="input"
                type="number"
                min="0"
                placeholder="0"
                value={form.stock}
                onChange={(event) => setForm({ ...form, stock: event.target.value })}
              />
            </label>
            <button type="submit" className="btn-primary" disabled={addProduct.isPending}>
              {addProduct.isPending ? "Adding…" : "Add item"}
            </button>
          </div>
          <div className="error-text" role="alert" style={{ marginTop: 8 }}>
            {error}
          </div>
        </form>

        <div className="card" style={{ overflow: "hidden" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "14px 18px",
              borderBottom: "1px solid var(--hairline)",
            }}
          >
            <div className="card-title">Stock levels</div>
            <div
              style={{ fontSize: 12, fontWeight: 600, color: "oklch(0.55 0.15 30)" }}
            >
              {lowCount ? `${lowCount} to restock` : "All stocked"}
            </div>
          </div>

          <div className="stock-grid head">
            <span />
            <span>Item</span>
            <span style={{ textAlign: "right" }}>Price</span>
            <span style={{ textAlign: "center" }}>In stock</span>
            <span style={{ textAlign: "center" }}>Receive / Remove</span>
            <span />
          </div>

          {isLoading && <div className="empty">Loading stock…</div>}
          {!isLoading && products.length === 0 && (
            <div className="empty">No menu items yet. Add the first one above.</div>
          )}

          {products.map((product) => (
            <div key={product.id} className="stock-grid">
              <div className="cell-photo">
                <PhotoPicker
                  product={product}
                  busy={
                    (uploadPhoto.isPending && uploadPhoto.variables?.id === product.id) ||
                    (removePhoto.isPending && removePhoto.variables === product.id)
                  }
                  onUpload={(file) => uploadPhoto.mutate({ id: product.id, file })}
                  onRemove={() => removePhoto.mutate(product.id)}
                />
              </div>
              <div className="cell-name" style={{ minWidth: 0 }}>
                <div className="truncate" style={{ fontWeight: 700, fontSize: 13.5 }}>
                  {product.name}
                </div>
                <div
                  style={{ fontSize: 11, fontWeight: 600, color: "rgba(0,0,0,.42)" }}
                >
                  {product.category}
                </div>
              </div>
              <div
                className="cell-price"
                style={{ textAlign: "right", fontWeight: 700, fontSize: 13.5 }}
              >
                {money(product.price)}
              </div>
              <div className="cell-stock" style={{ textAlign: "center" }}>
                <span
                  className={`stock-pill${
                    product.is_low_stock || product.is_sold_out ? " is-low" : ""
                  }`}
                >
                  {product.stock}
                </span>
              </div>
              <div
                className="cell-adjust"
                style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "flex-end" }}
              >
                <input
                  className="input"
                  type="number"
                  min="1"
                  aria-label={`Quantity to move for ${product.name}`}
                  value={amounts[product.id] ?? 1}
                  onChange={(event) =>
                    setAmounts({ ...amounts, [product.id]: event.target.value })
                  }
                  style={{ width: 48, padding: 6, fontSize: 12.5, textAlign: "center" }}
                />
                <button
                  type="button"
                  className="mini-btn accent"
                  onClick={() =>
                    adjustStock.mutate({
                      id: product.id,
                      delta: amountFor(product.id),
                      reason: "RECEIVE",
                    })
                  }
                >
                  + In
                </button>
                <button
                  type="button"
                  className="mini-btn"
                  onClick={() =>
                    adjustStock.mutate({
                      id: product.id,
                      delta: amountFor(product.id),
                      reason: "REMOVE",
                    })
                  }
                >
                  − Out
                </button>
              </div>
              <button
                type="button"
                className="icon-btn cell-remove"
                title={`Take ${product.name} off the menu`}
                aria-label={`Take ${product.name} off the menu`}
                onClick={() => archive.mutate(product.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </section>

      <aside className="activity" aria-label="Recent stock activity">
        <div className="card-title" style={{ marginBottom: 14 }}>
          Activity
        </div>
        {moves.length === 0 && (
          <div style={{ color: "var(--ink-faint)", fontSize: 13, fontWeight: 500 }}>
            No stock has moved yet today.
          </div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {moves.map((move) => (
            <div key={move.id} className="activity-row">
              <div
                className="activity-dot"
                style={{ background: moveColor[move.reason] }}
                aria-hidden="true"
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.3 }}>
                  {MOVE_TEXT[move.reason](move)}
                  {move.bill_no ? ` · order #${move.bill_no}` : ""}
                </div>
                <div
                  style={{
                    fontSize: 10.5,
                    color: "rgba(0,0,0,.4)",
                    fontWeight: 600,
                    marginTop: 1,
                  }}
                >
                  {timeOfDay(move.created_at)} · {move.user_name}
                </div>
              </div>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
