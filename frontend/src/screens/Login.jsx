import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { initials, roleLabel } from "../lib/format";

export default function Login() {
  const { signIn, status } = useAuth();
  const navigate = useNavigate();
  const [pickedId, setPickedId] = useState(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { data: staff = [], isLoading } = useQuery({
    queryKey: ["pin-targets"],
    queryFn: () => api("/users/pin-targets", { auth: false }),
  });

  // Preselect whoever is first on the list so the PIN field is one tap away.
  useEffect(() => {
    if (pickedId === null && staff.length) setPickedId(staff[0].id);
  }, [staff, pickedId]);

  if (status === "signed-in") return <Navigate to="/register" replace />;

  const picked = staff.find((member) => member.id === pickedId);
  const canSubmit = Boolean(picked) && pin.length === 4 && !busy;

  async function handleSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError("");
    try {
      await signIn(picked.id, pin);
      navigate("/register", { replace: true });
    } catch (err) {
      setError(err.detail || "That didn't work. Try again.");
      setPin("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
            marginBottom: 26,
          }}
        >
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: 14,
              background: "var(--accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontWeight: 800,
              fontSize: 23,
            }}
            aria-hidden="true"
          >
            तु
          </div>
          <div style={{ textAlign: "center", lineHeight: 1.2 }}>
            <div style={{ fontWeight: 800, fontSize: 20, letterSpacing: "-.4px" }}>
              Tulsi Tiffins
            </div>
            <div style={{ fontSize: 12.5, color: "var(--ink-soft)", fontWeight: 600 }}>
              Point of Sale · Staff sign in
            </div>
          </div>
        </div>

        <div className="login-legend">Who's on the counter?</div>
        <div
          style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}
          role="radiogroup"
          aria-label="Staff member"
        >
          {isLoading && <div className="empty">Loading the team…</div>}
          {!isLoading && staff.length === 0 && (
            <div className="empty">No staff accounts yet. Seed the database to sign in.</div>
          )}
          {staff.map((member) => {
            const isPicked = member.id === pickedId;
            return (
              <button
                key={member.id}
                type="button"
                role="radio"
                aria-checked={isPicked}
                className={`staff-option${isPicked ? " is-picked" : ""}`}
                onClick={() => {
                  setPickedId(member.id);
                  setError("");
                }}
              >
                <div className={`avatar${member.role === "MANAGER" ? " is-manager" : ""}`}>
                  {initials(member.name)}
                </div>
                <div style={{ textAlign: "left", flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>{member.name}</div>
                  <div
                    style={{ fontSize: 11.5, color: "var(--ink-soft)", fontWeight: 600 }}
                  >
                    {roleLabel(member.role)}
                  </div>
                </div>
                <div
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 12,
                    fontWeight: 800,
                    color: "#fff",
                    background: "var(--accent)",
                    opacity: isPicked ? 1 : 0,
                  }}
                  aria-hidden="true"
                >
                  ✓
                </div>
              </button>
            );
          })}
        </div>

        <label className="login-legend" htmlFor="pin">
          4-digit PIN
        </label>
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 6 }}>
          <input
            id="pin"
            className="pin-input"
            type="password"
            inputMode="numeric"
            autoComplete="off"
            maxLength={4}
            placeholder="••••"
            value={pin}
            onChange={(event) => {
              setPin(event.target.value.replace(/\D/g, "").slice(0, 4));
              setError("");
            }}
          />
        </div>
        <div className="error-text" role="alert" style={{ marginBottom: 8 }}>
          {error}
        </div>

        <button type="submit" className="signin-btn" disabled={!canSubmit}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
