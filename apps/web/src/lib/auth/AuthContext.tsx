"use client";

import React, {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { UserResponse, LoginRequest, RegisterRequest } from "@stonks/shared-types";
import {
  apiGetMe,
  apiLogin,
  apiLogout,
  apiRegister,
  clearTokens,
} from "@/lib/api/client";
import { useRouter } from "@/i18n/routing";

// ── Types ──
export interface AuthContextValue {
  user: UserResponse | null;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  register: (credentials: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ──
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const router = useRouter();
  const queryClient = useQueryClient();
  const mountedRef = useRef(false);

  // Fetch current user on mount
  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;

    let cancelled = false;

    async function fetchUser() {
      try {
        const me = await apiGetMe();
        if (!cancelled) {
          setUser(me);
        }
      } catch {
        // No active session — that's okay
        if (!cancelled) {
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    fetchUser();

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (credentials: LoginRequest) => {
      setIsLoading(true);
      try {
        await apiLogin(credentials);
        const me = await apiGetMe();
        setUser(me);
        queryClient.invalidateQueries({ queryKey: ["me"] });
      } finally {
        setIsLoading(false);
      }
    },
    [queryClient],
  );

  const register = useCallback(
    async (credentials: RegisterRequest) => {
      setIsLoading(true);
      try {
        await apiRegister(credentials);
        // Auto-login after register
        const tokens = await apiLogin({
          email: credentials.email,
          password: credentials.password,
        });
        if (tokens) {
          const me = await apiGetMe();
          setUser(me);
          queryClient.invalidateQueries({ queryKey: ["me"] });
        }
      } finally {
        setIsLoading(false);
      }
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    clearTokens();
    queryClient.clear();
    router.push("/login");
  }, [router, queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      login,
      register,
      logout,
      isAuthenticated: user !== null,
    }),
    [user, isLoading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
