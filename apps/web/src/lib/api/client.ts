import type {
  TokenResponse,
  UserResponse,
  LoginRequest,
  RegisterRequest,
  ApiError,
} from "@stonks/shared-types";

// ── Closure-based token store (in memory, never persisted) ──
let accessToken: string | null = null;
let refreshPromise: Promise<TokenResponse | null> | null = null;

// ── Public getters / setters ──
export function getAccessToken(): string | null {
  return accessToken;
}

export function setTokens(tokens: { access_token: string; refresh_token?: string }): void {
  accessToken = tokens.access_token;
}

export function clearTokens(): void {
  accessToken = null;
}

// ── Refresh logic (deduplicated) ──
async function refreshTokens(): Promise<TokenResponse | null> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const res = await fetch(`${window.location.origin}/api/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });

      if (!res.ok) {
        clearTokens();
        return null;
      }

      const data: TokenResponse = await res.json();
      setTokens(data);
      return data;
    } catch {
      clearTokens();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

// ── Error class ──
export class ApiClientError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiClientError";
  }
}

// ── apiClient (core) ──
export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  skipAuth?: boolean;
}

export async function apiClient<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, skipAuth = false, headers: extraHeaders, ...rest } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(extraHeaders as Record<string, string>),
  };

  if (!skipAuth && accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  let res = await fetch(path, {
    ...rest,
    credentials: "include",
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  // ── 401 → attempt refresh & retry once ──
  if (res.status === 401 && !skipAuth) {
    const newTokens = await refreshTokens();

    if (newTokens) {
      headers["Authorization"] = `Bearer ${newTokens.access_token}`;
      res = await fetch(path, {
        ...rest,
        credentials: "include",
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
    } else {
      if (typeof window !== "undefined") {
        const locale = window.location.pathname.split("/")[1] || "fr";
        window.location.href = `/${locale}/login`;
      }
      throw new ApiClientError(401, "Session expired");
    }
  }

  if (!res.ok) {
    const errBody = (await res.json().catch(() => ({ detail: "Network error" }))) as ApiError;
    throw new ApiClientError(res.status, errBody.detail ?? "Request failed");
  }

  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ── Auth convenience functions ──
export async function apiLogin(credentials: LoginRequest): Promise<TokenResponse> {
  const data = await apiClient<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: credentials,
    skipAuth: true,
  });
  setTokens(data);
  return data;
}

export async function apiRegister(credentials: RegisterRequest): Promise<UserResponse> {
  return apiClient<UserResponse>("/api/auth/register", {
    method: "POST",
    body: credentials,
    skipAuth: true,
  });
}

export async function apiLogout(): Promise<void> {
  try {
    await apiClient("/api/auth/logout", { method: "POST" });
  } catch {
    // Swallow — we clear tokens regardless
  } finally {
    clearTokens();
  }
}

export async function apiGetMe(): Promise<UserResponse> {
  return apiClient<UserResponse>("/api/auth/me");
}
