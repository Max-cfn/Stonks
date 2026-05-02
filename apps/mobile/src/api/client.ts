import { useRef, useCallback } from "react";
import { Platform } from "react-native";
import { tokenStore } from "../stores/tokenStore";

// In dev, use localhost:8000; for Expo Go on device, use LAN IP
// For production builds, use the deployed API URL
const getBaseUrl = (): string => {
  if (__DEV__) {
    // Expo Go: Android emulator uses 10.0.2.2, iOS simulator uses localhost
    if (Platform.OS === "android") {
      return "http://10.0.2.2:8000";
    }
    return "http://localhost:8000";
  }
  return "https://api.stonks.local";
};

const BASE_URL = getBaseUrl();

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true } = opts;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  if (auth) {
    const token = await tokenStore.getAccessToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  // Handle 401 — try refresh
  if (response.status === 401 && auth) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      const token = await tokenStore.getAccessToken();
      headers["Authorization"] = `Bearer ${token}`;
      const retryResponse = await fetch(`${BASE_URL}${path}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!retryResponse.ok) {
        throw await retryResponse.json();
      }
      return retryResponse.json() as Promise<T>;
    }
    // Refresh failed — clear tokens, will redirect to login
    await tokenStore.clear();
    throw new Error("Session expired");
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Network error" }));
    throw error;
  }

  // Handle 204 no content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = await tokenStore.getRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return false;

    const data = await response.json();
    await tokenStore.setAccessToken(data.access_token);
    await tokenStore.setRefreshToken(data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

// React hook that returns memoized API functions
export function useApi() {
  const abortRef = useRef<AbortController | null>(null);

  const get = useCallback(<T>(path: string) => request<T>(path), []);
  const post = useCallback(
    <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
    []
  );
  const put = useCallback(
    <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
    []
  );
  const del = useCallback(
    <T>(path: string) => request<T>(path, { method: "DELETE" }),
    []
  );

  return { get, post, put, del, abortRef };
}

export { BASE_URL, request };
