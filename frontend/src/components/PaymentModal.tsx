import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError } from "../api/client";
import { money, plural, timeOfDay } from "../lib/format";
import type { PaymentIn, PaymentMethod, Receipt, ResolvedCartLine, UpiQr } from "../types";
import Modal from "./Modal";

type Stage = "method" | "CASH" | "UPI" | "receipt";

export interface PaymentModalProps {
  lines: ResolvedCartLine[];
  total: number;
  itemCount: number;
  onClose: () => void;
  onCompleted: () => void;
}

/**
 * Choose method → cash/UPI → receipt.
 *
 * The sale is posted to the API exactly once, on "Payment received" — that call
 * is what deducts stock and records the bill. Nothing is written when the modal
 * merely opens.
 */
export default function PaymentModal({
  lines,
  total,
  itemCount,
  onClose,
  onCompleted,
}: PaymentModalProps) {
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<Stage>("method");
  const [received, setReceived] = useState("");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState("");

  const { data: upi } = useQuery<UpiQr, ApiError>({
    queryKey: ["upi-qr", total],
    queryFn: () => api<UpiQr>(`/register/upi-qr?amount=${total.toFixed(2)}`),
    enabled: stage === "UPI",
  });

  const sale = useMutation<Receipt, ApiError, PaymentIn>({
    mutationFn: (payment) =>
      api<Receipt>("/bills", {
        method: "POST",
        body: {
          lines: lines.map((line) => ({ product_id: line.productId, qty: line.qty })),
          payment,
        },
      }),
    onSuccess: (created) => {
      setReceipt(created);
      setStage("receipt");
      onCompleted();
      // Stock and history both moved — refresh whatever is on screen.
      queryClient.invalidateQueries({ queryKey: ["menu"] });
      queryClient.invalidateQueries({ queryKey: ["bills"] });
      queryClient.invalidateQueries({ queryKey: ["daily-total"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["stock-moves"] });
    },
    onError: (err) => setError(err.detail),
  });

  const tendered = Number(received || 0);
  const change = tendered - total;
  const cashIsEnough = received !== "" && tendered >= total - 0.001;

  function confirm(method: PaymentMethod) {
    setError("");
    sale.mutate(
      method === "CASH"
        ? { method: "CASH", tendered: tendered.toFixed(2) }
        : { method: "UPI" },
    );
  }

  // ---- receipt -----------------------------------------------------------
  if (stage === "receipt" && receipt) {
    return (
      <Modal key={stage} onClose={onClose} labelledBy="receipt-heading">
        <div id="receipt-print">
          <div
            style={{
              padding: "22px 24px 16px",
              textAlign: "center",
              borderBottom: "1px dashed rgba(0,0,0,.15)",
            }}
          >
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: "var(--accent)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                fontWeight: 800,
                fontSize: 19,
                margin: "0 auto 10px",
              }}
              aria-hidden="true"
            >
              तु
            </div>
            <div id="receipt-heading" style={{ fontWeight: 800, fontSize: 18 }}>
              Tulsi Tiffins
            </div>
            <div
              style={{
                fontSize: 12,
                color: "rgba(0,0,0,.5)",
                fontWeight: 600,
                marginTop: 2,
              }}
            >
              Order #{receipt.bill_no} · {timeOfDay(receipt.created_at)} ·{" "}
              {receipt.cashier_name}
            </div>
          </div>

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
                <span style={{ fontWeight: 700, color: "rgba(0,0,0,.5)", minWidth: 30 }}>
                  × {line.qty}
                </span>
                <span style={{ flex: 1, fontWeight: 600 }}>{line.name}</span>
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
              {receipt.method === "CASH" && (
                <>
                  <div className="total-row" style={{ marginTop: 8, marginBottom: 2 }}>
                    <span>Cash received</span>
                    <span>{money(receipt.tendered)}</span>
                  </div>
                  <div className="total-row" style={{ marginBottom: 0 }}>
                    <span>Change returned</span>
                    <span>{money(receipt.change_due)}</span>
                  </div>
                </>
              )}
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
            <div
              style={{
                textAlign: "center",
                fontSize: 11.5,
                fontWeight: 600,
                color: "rgba(0,0,0,.4)",
                marginTop: 12,
              }}
            >
              Thank you · Visit again!
            </div>
          </div>

          <div className="no-print" style={{ display: "flex", gap: 10, padding: "6px 24px 22px" }}>
            <button type="button" className="btn-ghost" style={{ flex: 1 }} onClick={() => window.print()}>
              Print receipt
            </button>
            <button type="button" className="confirm-btn" onClick={onClose}>
              Done
            </button>
          </div>
        </div>
      </Modal>
    );
  }

  // ---- choose method -----------------------------------------------------
  if (stage === "method") {
    return (
      <Modal key={stage} onClose={onClose} labelledBy="pay-heading">
        <div className="modal-body">
          <div style={{ textAlign: "center", marginBottom: 6 }}>
            <div className="modal-eyebrow" id="pay-heading">
              {plural(itemCount, "item")}
            </div>
            <div style={{ fontSize: 34, fontWeight: 800, letterSpacing: "-.8px", marginTop: 4 }}>
              {money(total)}
            </div>
          </div>
          <div
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: "rgba(0,0,0,.5)",
              textAlign: "center",
              margin: "14px 0 12px",
            }}
          >
            How is the customer paying?
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <button type="button" className="method-btn" onClick={() => setStage("CASH")}>
              <span style={{ fontSize: 30, lineHeight: 1 }} aria-hidden="true">
                💵
              </span>
              <span style={{ fontWeight: 800, fontSize: 15 }}>Cash</span>
            </button>
            <button type="button" className="method-btn" onClick={() => setStage("UPI")}>
              <span style={{ fontSize: 30, lineHeight: 1 }} aria-hidden="true">
                📱
              </span>
              <span style={{ fontWeight: 800, fontSize: 15 }}>UPI</span>
            </button>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              width: "100%",
              marginTop: 14,
              border: "none",
              background: "none",
              color: "var(--ink-soft)",
              fontSize: 13,
              fontWeight: 700,
              padding: 8,
            }}
          >
            Cancel
          </button>
        </div>
      </Modal>
    );
  }

  // ---- cash --------------------------------------------------------------
  if (stage === "CASH") {
    return (
      <Modal key={stage} onClose={onClose} labelledBy="cash-heading">
        <div className="modal-body">
          <div style={{ textAlign: "center", marginBottom: 18 }}>
            <div className="modal-eyebrow" id="cash-heading">
              Cash payment
            </div>
          </div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "12px 14px",
              background: "var(--surface-sunk)",
              borderRadius: 11,
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 700, color: "rgba(0,0,0,.55)" }}>
              Total amount
            </span>
            <span style={{ fontSize: 20, fontWeight: 800 }}>{money(total)}</span>
          </div>

          <label style={{ display: "block", marginTop: 14 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: "rgba(0,0,0,.5)" }}>
              Amount received
            </span>
            <input
              inputMode="decimal"
              placeholder="0"
              autoFocus
              value={received}
              onChange={(event) => {
                setReceived(event.target.value.replace(/[^\d.]/g, ""));
                setError("");
              }}
              style={{
                width: "100%",
                marginTop: 6,
                border: "1px solid var(--border)",
                borderRadius: 11,
                padding: "13px 14px",
                fontSize: 20,
                fontWeight: 800,
                outline: "none",
              }}
            />
          </label>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "12px 14px",
              borderRadius: 11,
              marginTop: 10,
              background: cashIsEnough ? "var(--accent-tint)" : "oklch(0.96 0.03 40)",
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 700, color: "rgba(0,0,0,.55)" }}>
              {cashIsEnough ? "Change to return" : "Still due"}
            </span>
            <span
              style={{
                fontSize: 19,
                fontWeight: 800,
                color: cashIsEnough ? "oklch(0.45 0.11 152)" : "var(--warn-ink)",
              }}
            >
              {money(Math.abs(change))}
            </span>
          </div>

          {error && (
            <div className="error-text" role="alert" style={{ marginTop: 10 }}>
              {error}
            </div>
          )}

          <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => {
                setStage("method");
                setReceived("");
                setError("");
              }}
            >
              Back
            </button>
            <button
              type="button"
              className="confirm-btn"
              disabled={!cashIsEnough || sale.isPending}
              onClick={() => confirm("CASH")}
            >
              {sale.isPending ? "Recording…" : "Payment received"}
            </button>
          </div>
        </div>
      </Modal>
    );
  }

  // ---- UPI ---------------------------------------------------------------
  return (
    <Modal key={stage} onClose={onClose} labelledBy="upi-heading">
      <div className="modal-body">
        <div style={{ textAlign: "center", marginBottom: 6 }}>
          <div className="modal-eyebrow" id="upi-heading">
            UPI payment
          </div>
          <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-.6px", marginTop: 2 }}>
            {money(total)}
          </div>
        </div>

        <div
          style={{
            marginTop: 12,
            padding: 18,
            background: "var(--surface-sunk)",
            borderRadius: 14,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: ".6px",
              color: "var(--accent-deep)",
            }}
          >
            Scan to pay
          </div>
          <div
            style={{
              background: "#fff",
              padding: 12,
              borderRadius: 12,
              boxShadow: "0 2px 8px rgba(0,0,0,.06)",
              minWidth: 204,
              minHeight: 204,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {upi ? (
              <img src={upi.qr_data_uri} alt="UPI QR code" width={180} height={180} />
            ) : (
              <span style={{ fontSize: 12, color: "var(--ink-faint)", fontWeight: 600 }}>
                Building the QR…
              </span>
            )}
          </div>
          <div style={{ fontSize: 13, fontWeight: 700 }}>{upi?.upi_id ?? ""}</div>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-soft)" }}>
            GPay · PhonePe · Paytm · any UPI app
          </div>
        </div>

        {error && (
          <div className="error-text" role="alert" style={{ marginTop: 10 }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => {
              setStage("method");
              setError("");
            }}
          >
            Back
          </button>
          <button
            type="button"
            className="confirm-btn"
            disabled={sale.isPending}
            onClick={() => confirm("UPI")}
          >
            {sale.isPending ? "Recording…" : "Payment received"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
