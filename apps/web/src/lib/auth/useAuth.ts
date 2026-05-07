"use client";

import { useContext } from "react";
import { AuthContext, type AuthContextValue } from "./AuthContext";

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  // Auth desactivee — retourne un contexte guest par defaut
  if (!ctx) {
    return {
      user: null,
      isLoading: false,
      login: async () => {},
      register: async () => {},
      logout: async () => {},
      isAuthenticated: false,
    };
  }
  return ctx;
}
