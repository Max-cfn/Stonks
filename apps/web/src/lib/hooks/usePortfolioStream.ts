"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { getAccessToken } from "@/lib/api/client";

export type StreamStatus = "connecting" | "connected" | "disconnected";

export interface UsePortfolioStreamReturn {
  status: StreamStatus;
  lastMessage: unknown;
  reconnect: () => void;
}

const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 1_000;

/** Close code sent by backend when JWT is invalid or expired. */
const CLOSE_CODE_INVALID_TOKEN = 4001;

/**
 * Build the WebSocket base URL (host:port) from environment or fallback.
 *
 * Priority:
 *   1. NEXT_PUBLIC_WS_URL env var (e.g. "http://localhost:4174" or "192.168.1.56:4174")
 *   2. window.location.host (e.g. "192.168.1.56") + port 4174
 */
function getWsBaseUrl(): string {
  if (typeof window === "undefined") return "localhost:4174";

  const envUrl = process.env.NEXT_PUBLIC_WS_URL;
  if (envUrl) {
    try {
      const u = new URL(envUrl);
      return `${u.hostname}:${u.port || "4174"}`;
    } catch {
      // Not a valid URL — assume it's already "host:port"
      return envUrl;
    }
  }

  // Fallback: same hostname as the page, backend port
  return `${window.location.hostname}:4174`;
}

export function usePortfolioStream(): UsePortfolioStreamReturn {
  const [status, setStatus] = useState<StreamStatus>("disconnected");
  const [lastMessage, setLastMessage] = useState<unknown>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  // Snapshot the token ONCE at mount time so we don't reconnect
  // when the token refreshes mid-session. If the token was invalid
  // at mount, the user must refresh or revisit the page.
  const tokenAtMount = useMemo(() => {
    if (typeof window === "undefined") return null;
    return getAccessToken();
  }, []);

  const connect = useCallback(() => {
    // ── CRITICAL: no token → no connection, no reconnect loop ──
    if (!tokenAtMount) {
      setStatus("disconnected");
      return;
    }

    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    setStatus("connecting");

    const wsUrl = `ws://${getWsBaseUrl()}/portfolio/stream?token=${encodeURIComponent(tokenAtMount)}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setStatus("connected");
        backoffRef.current = INITIAL_BACKOFF_MS;
      };

      ws.onmessage = (event: MessageEvent) => {
        if (!mountedRef.current) return;
        try {
          const data = JSON.parse(event.data as string);
          setLastMessage(data);
        } catch {
          setLastMessage(event.data);
        }
      };

      ws.onclose = (event: CloseEvent) => {
        if (!mountedRef.current) return;
        setStatus("disconnected");
        wsRef.current = null;

        // ── Invalid token → stop forever (no reconnect) ──
        if (event.code === CLOSE_CODE_INVALID_TOKEN) {
          return;
        }

        // Exponential backoff reconnect
        const delay = backoffRef.current;
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);

        reconnectTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) connect();
        }, delay);
      };

      ws.onerror = () => {
        if (!mountedRef.current) return;
        setStatus("disconnected");
        wsRef.current = null;
      };
    } catch {
      if (mountedRef.current) {
        setStatus("disconnected");
        const delay = backoffRef.current;
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
        reconnectTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current && tokenAtMount) connect();
        }, delay);
      }
    }
  }, [tokenAtMount]);

  const reconnect = useCallback(() => {
    backoffRef.current = INITIAL_BACKOFF_MS;
    if (wsRef.current) {
      wsRef.current.close(1000, "Manual reconnect");
      wsRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    connect();
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, "Component unmounted");
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { status, lastMessage, reconnect };
}
