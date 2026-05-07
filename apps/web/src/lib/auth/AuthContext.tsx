"use client";

import React, {
  createContext,
  useCallback,
  useMemo,
} from "react";
import { useRouter } from "@/i18n/routing";

// Auth desactivee temporairement — l'app fonctionne en mode guest.
// Pour reactiver, retablir les appels apiGetMe/apiLogin/apiLogout.

export interface AuthContextValue {
  user: null;
  isLoading: false;
  login: () => Promise<void>;
  register: () => Promise<void>;
  logout: () => Promise<void>;
  isAuthenticated: false;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  const login = useCallback(async () => {}, []);
  const register = useCallback(async () => {}, []);
  const logout = useCallback(async () => {
    router.push("/login");
  }, [router]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: null,
      isLoading: false as const,
      login,
      register,
      logout,
      isAuthenticated: false as const,
    }),
    [login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
