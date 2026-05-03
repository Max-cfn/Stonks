import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useRouter, useSegments, useRootNavigationState } from "expo-router";
import { tokenStore, StoredUser } from "../stores/tokenStore";
import { useApi } from "../api/client";
import type { UserResponse, TokenResponse, LoginRequest, RegisterRequest } from "../api/types";

interface AuthState {
  user: StoredUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<StoredUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const segments = useSegments();
  const navigationState = useRootNavigationState();
  const { get, post } = useApi();

  const isAuthenticated = user !== null;

  // Check stored tokens on mount
  useEffect(() => {
    async function bootstrap() {
      try {
        const storedUser = await tokenStore.getUser();
        const token = await tokenStore.getAccessToken();
        if (storedUser && token) {
          setUser(storedUser);
        }
      } catch {
        // not authed
      } finally {
        setIsLoading(false);
      }
    }
    bootstrap();
  }, []);

  // Redirect based on auth state — only after navigation is ready
  useEffect(() => {
    if (!navigationState?.key) return;

    const inAuthGroup = segments[0] === "(auth)";

    if (!isLoading) {
      if (!isAuthenticated && !inAuthGroup) {
        router.replace("/(auth)/login");
      } else if (isAuthenticated && inAuthGroup) {
        router.replace("/(tabs)/dashboard");
      }
    }
  }, [isAuthenticated, isLoading, segments, navigationState?.key, router]);

  const login = useCallback(
    async (data: LoginRequest) => {
      const tokens = await post<TokenResponse>("/auth/login", data);
      await tokenStore.setAccessToken(tokens.access_token);
      await tokenStore.setRefreshToken(tokens.refresh_token);

      // Fetch user profile
      const userData = await get<UserResponse>("/auth/me");
      const storedUser: StoredUser = {
        id: userData.id,
        email: userData.email,
        is_active: userData.is_active,
        created_at: userData.created_at,
      };
      await tokenStore.setUser(storedUser);
      setUser(storedUser);
    },
    [get, post]
  );

  const register = useCallback(
    async (data: RegisterRequest) => {
      await post<UserResponse>("/auth/register", data);
      // Auto-login after register
      await login(data);
    },
    [login, post]
  );

  const logout = useCallback(async () => {
    await tokenStore.clear();
    setUser(null);
    router.replace("/(auth)/login");
  }, [router]);

  const refreshUser = useCallback(async () => {
    try {
      const userData = await get<UserResponse>("/auth/me");
      const storedUser: StoredUser = {
        id: userData.id,
        email: userData.email,
        is_active: userData.is_active,
        created_at: userData.created_at,
      };
      await tokenStore.setUser(storedUser);
      setUser(storedUser);
    } catch {
      // ignore
    }
  }, [get]);

  return (
    <AuthContext.Provider
      value={{ user, isLoading, isAuthenticated, login, register, logout, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
