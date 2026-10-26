import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";

import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { initials } from "../lib/format";
import type { UserCreate, UserDetail, UserRole, UserUpdate } from "../types";

interface StaffForm {
  name: string;
  role: UserRole;
  pin: string;
}

export default function Staff() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [form, setForm] = useState<StaffForm>({ name: "", role: "CASHIER", pin: "" });
  const [error, setError] = useState("");
  const [resetting, setResetting] = useState<number | null>(null);
  const [newPin, setNewPin] = useState("");

  const { data: staff = [], isLoading } = useQuery<UserDetail[], ApiError>({
    queryKey: ["staff"],
    queryFn: () => api<UserDetail[]>("/users"),
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["staff"] });
    queryClient.invalidateQueries({ queryKey: ["pin-targets"] });
  }

  const addUser = useMutation<UserDetail, ApiError, UserCreate>({
    mutationFn: (body) => api<UserDetail>("/users", { method: "POST", body }),
    onSuccess: () => {
      setForm({ name: "", role: "CASHIER", pin: "" });
      setError("");
      refresh();
    },
    onError: (err) => setError(err.detail),
  });

  const patchUser = useMutation<UserDetail, ApiError, { id: number; body: UserUpdate }>({
    mutationFn: ({ id, body }) => api<UserDetail>(`/users/${id}`, { method: "PATCH", body }),
    onSuccess: () => {
      setError("");
      setResetting(null);
      setNewPin("");
      refresh();
    },
    onError: (err) => setError(err.detail),
  });

  const deactivate = useMutation<UserDetail, ApiError, number>({
    mutationFn: (id) => api<UserDetail>(`/users/${id}/deactivate`, { method: "PATCH" }),
    onSuccess: () => {
      setError("");
      refresh();
    },
    onError: (err) => setError(err.detail),
  });

  const activeManagers = staff.filter(
    (member) => member.role === "MANAGER" && member.is_active,
  ).length;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.name.trim()) {
      setError("Enter a name.");
      return;
    }
    if (!/^\d{4}$/.test(form.pin)) {
      setError("The PIN must be 4 digits.");
      return;
    }
    addUser.mutate({ name: form.name.trim(), role: form.role, pin: form.pin });
  }

  return (
    <div className="centered-page">
      <div className="centered-col" style={{ maxWidth: 760 }}>
        <form className="card" style={{ padding: "16px 18px" }} onSubmit={submit}>
          <div className="card-title" style={{ marginBottom: 12 }}>
            Add a team member
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "flex-end" }}>
            <label className="field" style={{ flex: "2 1 200px" }}>
              <span className="field-label">Full name</span>
              <input
                className="input"
                placeholder="e.g. Karthik S."
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </label>
            <label className="field" style={{ flex: "1 1 130px" }}>
              <span className="field-label">Role</span>
              <select
                className="select"
                value={form.role}
                onChange={(event) => setForm({ ...form, role: event.target.value as UserRole })}
              >
                <option value="CASHIER">Cashier</option>
                <option value="MANAGER">Manager</option>
              </select>
            </label>
            <label className="field" style={{ flex: "0 1 110px" }}>
              <span className="field-label">4-digit PIN</span>
              <input
                className="input"
                inputMode="numeric"
                placeholder="0000"
                style={{ letterSpacing: 3 }}
                value={form.pin}
                onChange={(event) =>
                  setForm({ ...form, pin: event.target.value.replace(/\D/g, "").slice(0, 4) })
                }
              />
            </label>
            <button type="submit" className="btn-primary" disabled={addUser.isPending}>
              {addUser.isPending ? "Adding…" : "Add user"}
            </button>
          </div>
          <div className="error-text" role="alert" style={{ marginTop: 8 }}>
            {error}
          </div>
        </form>

        <div className="card" style={{ overflow: "hidden" }}>
          <div
            className="card-title"
            style={{ padding: "14px 18px", borderBottom: "1px solid var(--hairline)" }}
          >
            Team members
          </div>

          {isLoading && <div className="empty">Loading the team…</div>}

          {staff.map((member) => {
            const isSelf = member.id === user?.id;
            const isLastManager =
              member.role === "MANAGER" && member.is_active && activeManagers <= 1;
            const lockRemoval = isSelf || isLastManager || !member.is_active;

            return (
              <div
                key={member.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: "12px 18px",
                  borderBottom: "1px solid rgba(0,0,0,.05)",
                  flexWrap: "wrap",
                  opacity: member.is_active ? 1 : 0.55,
                }}
              >
                <div className={`avatar${member.role === "MANAGER" ? " is-manager" : ""}`}>
                  {initials(member.name)}
                </div>
                <div style={{ flex: "1 1 160px", minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>{member.name}</span>
                    {isSelf && <span className="role-badge">You</span>}
                    {!member.is_active && (
                      <span className="role-badge" style={{ background: "var(--surface-sunk-alt)", color: "var(--ink-soft)" }}>
                        Removed
                      </span>
                    )}
                  </div>
                  <div
                    style={{ fontSize: 11.5, fontWeight: 600, color: "rgba(0,0,0,.42)" }}
                  >
                    PIN ••••
                  </div>
                </div>

                {resetting === member.id ? (
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <input
                      className="input"
                      inputMode="numeric"
                      autoFocus
                      placeholder="New PIN"
                      style={{ width: 92, letterSpacing: 3 }}
                      value={newPin}
                      onChange={(event) =>
                        setNewPin(event.target.value.replace(/\D/g, "").slice(0, 4))
                      }
                    />
                    <button
                      type="button"
                      className="mini-btn accent"
                      disabled={newPin.length !== 4}
                      onClick={() => patchUser.mutate({ id: member.id, body: { pin: newPin } })}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      className="mini-btn"
                      onClick={() => {
                        setResetting(null);
                        setNewPin("");
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <>
                    <select
                      className="select"
                      style={{ fontSize: 12.5, fontWeight: 600, padding: "8px 10px" }}
                      value={member.role}
                      disabled={isLastManager || !member.is_active}
                      onChange={(event) =>
                        patchUser.mutate({
                          id: member.id,
                          body: { role: event.target.value as UserRole },
                        })
                      }
                      aria-label={`Role for ${member.name}`}
                    >
                      <option value="CASHIER">Cashier</option>
                      <option value="MANAGER">Manager</option>
                    </select>
                    <button
                      type="button"
                      className="mini-btn"
                      disabled={!member.is_active}
                      onClick={() => setResetting(member.id)}
                    >
                      Reset PIN
                    </button>
                    <button
                      type="button"
                      className="icon-btn"
                      disabled={lockRemoval}
                      title={
                        isSelf
                          ? "You can't remove yourself"
                          : isLastManager
                            ? "You can't remove the only manager"
                            : `Remove ${member.name}`
                      }
                      aria-label={`Remove ${member.name}`}
                      onClick={() => deactivate.mutate(member.id)}
                    >
                      ×
                    </button>
                  </>
                )}
              </div>
            );
          })}

          <div
            style={{
              padding: "11px 18px",
              fontSize: 11.5,
              fontWeight: 600,
              color: "var(--ink-soft)",
            }}
          >
            You can't remove yourself or the only manager. Removed members keep their
            past orders.
          </div>
        </div>
      </div>
    </div>
  );
}
