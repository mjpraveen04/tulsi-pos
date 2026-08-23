import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, setUnauthorizedHandler, tokenStore } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState(tokenStore.get() ? "checking" : "signed-out");

  const signOut = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setStatus("signed-out");
    queryClient.clear();
  }, [queryClient]);

  // A token that has expired mid-shift must land the cashier back on Login
  // rather than leaving a half-dead screen.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      tokenStore.clear();
      setUser(null);
      setStatus("signed-out");
    });
  }, []);

  // Restore the session on reload.
  useEffect(() => {
    if (!tokenStore.get()) return;
    let cancelled = false;
    api("/auth/me")
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        setStatus("signed-in");
      })
      .catch(() => {
        if (cancelled) return;
        tokenStore.clear();
        setStatus("signed-out");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(
    async (userId, pin) => {
      const result = await api("/auth/login", {
        method: "POST",
        auth: false,
        body: { user_id: userId, pin },
      });
      tokenStore.set(result.access_token);
      queryClient.clear();
      setUser(result.user);
      setStatus("signed-in");
      return result.user;
    },
    [queryClient],
  );

  const value = useMemo(
    () => ({
      user,
      status,
      signIn,
      signOut,
      isManager: user?.role === "MANAGER",
    }),
    [user, status, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
