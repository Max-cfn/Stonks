import { apiClient } from "@/lib/api/client";

/**
 * Simple typed GET wrapper around apiClient.
 * Prepends /api prefix automatically.
 */
export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const url = new URL(
    path,
    typeof window !== "undefined" ? window.location.origin : "http://localhost:3000",
  );

  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v));
      }
    });
  }

  const pathWithSearch = url.pathname + url.search;
  return apiClient<T>(pathWithSearch);
}

/**
 * Simple typed POST wrapper around apiClient.
 */
export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiClient<T>(path, { method: "POST", body });
}
