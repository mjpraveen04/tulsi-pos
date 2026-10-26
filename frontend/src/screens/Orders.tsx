import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError } from "../api/client";
import Modal from "../components/Modal";
import { money, plural, timeOfDay } from "../lib/format";
import type { BillSummary, DailyTotal, IsoDate, Receipt } from "../types";

function today(): IsoDate {
  return new Date().toISOString().slice(0, 10);
}

export default function Orders() {
  const [date, setDate] = useState<IsoDate>(today());
  const [billNo, setBillNo] = useState("");
  const [openBillNo, setOpenBillNo] = useState<number | null>(null);

  const { data: report } = useQuery<DailyTotal, ApiError>({
    queryKey: ["daily-total", date],
    queryFn: () => api<DailyTotal>(`/reports/daily-total?date=${date}`),
  });

  const query = billNo.trim() ? `bill_no=${billNo.trim()}` : `date=${date}`;
  const { data: bills = [], isLoading } = useQuery<BillSummary[], ApiError>({
    queryKey: ["bills", query],
    queryFn: () => api<BillSummary[]>(`/bills?${query}`),
  });

  const { data: receipt } = useQuery<Receipt, ApiError>({
    queryKey: ["bill", openBillNo],
    queryFn: () => api<Receipt>(`/bills/${openBillNo}`),
    enabled: openBillNo !== null,
  });

  return (
    <div className="centered-page">
      <div className="centered-col">
        <div className="summary-row">
          <div className="summary-card">
            <div className="summary-label">Orders</div>
            <div className="summary-value">{report?.bill_count ?? "—"}</div>
          </div>
          <div className="summary-card">
            <div className="summary-label">Items sold</div>
            <div className="summary-value">{report?.item_count ?? "—"}</div>
          </div>
          <div className="summary-card accent">
            <div className="summary-label">Sales total</div>
            <div className="summary-value">
              {report ? money(report.total) : "—"}
            </div>
          </div>
        </div>

        <div className="card" style={{ padding: "14px 18px" }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
            <label className="field" style={{ flex: "1 1 160px" }}>
              <span className="field-label">Date</span>
              <input
                className="input"
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value)}
                disabled={Boolean(billNo.trim())}
              />
            </label>
            <label className="field" style={{ flex: "1 1 160px" }}>
              <span className="field-label">Bill number</span>
              <input
                className="input"
                inputMode="numeric"
                placeholder="e.g. 1042"
                value={billNo}
                onChange={(event) => setBillNo(event.target.value.replace(/\D/g, ""))}
              />
            </label>
            {billNo.trim() && (
              <button type="button" className="mini-btn" onClick={() => setBillNo("")}>
                Clear search
              </button>
            )}
          </div>
        </div>

        <div className="card" style={{ overflow: "hidden" }}>
          <div
            className="card-title"
            style={{ padding: "14px 18px", borderBottom: "1px solid var(--hairline)" }}
          >
            Order history
          </div>

          {isLoading && <div className="empty">Loading orders…</div>}
          {!isLoading && bills.length === 0 && (
            <div className="empty">
              {billNo.trim()
                ? `No bill #${billNo.trim()} was found.`
                : "No orders on this date. Completed sales from the register appear here."}
            </div>
          )}

          {bills.map((bill) => (
            <button
              key={bill.bill_no}
              type="button"
              className="order-row"
              onClick={() => setOpenBillNo(bill.bill_no)}
            >
              <div
                style={{
                  flex: "0 0 auto",
                  fontWeight: 800,
                  fontSize: 14,
                  color: "var(--accent-deep)",
                  minWidth: 56,
                }}
              >
                #{bill.bill_no}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="truncate" style={{ fontWeight: 700, fontSize: 13.5 }}>
                  {bill.summary}
                </div>
                <div
                  style={{
                    fontSize: 11.5,
                    fontWeight: 600,
                    color: "rgba(0,0,0,.42)",
                    marginTop: 1,
                  }}
                >
                  {timeOfDay(bill.created_at)} · {bill.cashier_name} ·{" "}
                  {plural(bill.item_count, "item")} · {bill.method === "CASH" ? "Cash" : "UPI"}
                </div>
              </div>
              <div style={{ fontWeight: 800, fontSize: 14.5 }}>{money(bill.total)}</div>
            </button>
          ))}
        </div>
      </div>

      {openBillNo !== null && (
        <Modal onClose={() => setOpenBillNo(null)} labelledBy="past-receipt">
          <div id="receipt-print">
            <div
              style={{
                padding: "22px 24px 16px",
                textAlign: "center",
                borderBottom: "1px dashed rgba(0,0,0,.15)",
              }}
            >
              <div id="past-receipt" style={{ fontWeight: 800, fontSize: 18 }}>
                Tulsi Tiffins
              </div>
              <div
                style={{ fontSize: 12, color: "rgba(0,0,0,.5)", fontWeight: 600, marginTop: 2 }}
              >
                {receipt
                  ? `Order #${receipt.bill_no} · ${timeOfDay(receipt.created_at)} · ${receipt.cashier_name}`
                  : "Loading…"}
              </div>
            </div>

            {receipt && (
              <div style={{ padding: "16px 24px" }}>
                {receipt.lines.map((line) => (
                  <div
                    key={line.product_id}
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: 10,
                      padding: "5px 0",
                      fontSize: 13.5,
                    }}
                  >
                    <span
                      style={{ fontWeight: 700, color: "rgba(0,0,0,.5)", minWidth: 30 }}
                    >
                      × {line.qty}
                    </span>
                    <span style={{ flex: 1, fontWeight: 600 }}>{line.name}</span>
                    {/* Price at the time of sale — a later price edit never
                        rewrites this receipt (FR-25). */}
                    <span style={{ fontWeight: 700 }}>{money(line.line_total)}</span>
                  </div>
                ))}
                <div
                  style={{
                    marginTop: 12,
                    paddingTop: 12,
                    borderTop: "1px dashed rgba(0,0,0,.15)",
                  }}
                >
                  <div className="total-row" style={{ marginBottom: 2 }}>
                    <span>Subtotal</span>
                    <span>{money(receipt.subtotal)}</span>
                  </div>
                  <div className="total-row" style={{ marginBottom: 2 }}>
                    <span>GST (5%)</span>
                    <span>{money(receipt.gst)}</span>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 19,
                      fontWeight: 800,
                      marginTop: 6,
                    }}
                  >
                    <span>Total</span>
                    <span>{money(receipt.total)}</span>
                  </div>
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    marginTop: 14,
                    padding: 9,
                    background: "var(--accent-tint)",
                    borderRadius: 10,
                    color: "var(--accent-ink)",
                    fontWeight: 800,
                    fontSize: 13,
                  }}
                >
                  ✓ Paid by {receipt.method === "CASH" ? "cash" : "UPI"}
                </div>
              </div>
            )}

            <div
              className="no-print"
              style={{ display: "flex", gap: 10, padding: "6px 24px 22px" }}
            >
              <button
                type="button"
                className="btn-ghost"
                style={{ flex: 1 }}
                onClick={() => window.print()}
              >
                Print receipt
              </button>
              <button type="button" className="confirm-btn" onClick={() => setOpenBillNo(null)}>
                Done
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
