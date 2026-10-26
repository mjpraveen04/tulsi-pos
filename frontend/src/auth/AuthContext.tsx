import { useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, setUnauthorizedHandler, tokenStore } from "../api/client";
import type { LoginRequest, LoginResponse, UserPublic } from "../types";

export type AuthStatus = "checking" | "signed-in" | "signed-out";

export interface AuthValue {
  user: UserPublic | null;
  status: AuthStatus;
  signIn: (userId: number, pin: string) => Promise<UserPublic>;
  signOut: () => void;
  isManager: boolean;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<UserPublic | null>(null);
  const [status, setStatus] = useState<AuthStatus>(
    tokenStore.get() ? "checking" : "signed-out",
  );

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
    api<UserPublic>("/auth/me")
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
    async (userId: number, pin: string): Promise<UserPublic> => {
      const result = await api<LoginResponse>("/auth/login", {
        method: "POST",
        auth: false,
        body: { user_id: userId, pin } satisfies LoginRequest,
      });
      tokenStore.set(result.access_token);
      queryClient.clear();
      setUser(result.user);
      setStatus("signed-in");
      return result.user;
    },
    [queryClient],
  );

  const value = useMemo<AuthValue>(
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

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
