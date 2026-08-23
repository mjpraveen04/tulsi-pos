import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthContext";

function Splash({ children }) {
  return (
    <div className="login-page">
      <div className="empty">{children}</div>
    </div>
  );
}

/** Signed-in users only. */
export function RequireAuth() {
  const { status } = useAuth();

  if (status === "checking") return <Splash>Signing you back in…</Splash>;
  if (status !== "signed-in") return <Navigate to="/login" replace />;
  return <Outlet />;
}

/**
 * Managers only. This hides the screen; the API enforces the same rule
 * independently, so a hand-typed URL gets a 403 either way (FR-04).
 */
export function RequireManager() {
  const { status, isManager } = useAuth();

  if (status === "checking") return <Splash>Signing you back in…</Splash>;
  if (status !== "signed-in") return <Navigate to="/login" replace />;
  if (!isManager) return <Navigate to="/register" replace />;
  return <Outlet />;
}
