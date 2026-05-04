"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export type StreamStatus = "connecting" | "connected" | "disconnected";

export interface UsePortfolioStreamReturn {
  status: StreamStatus;
  lastMessage: unknown;
  reconnect: () => void;
}

const WS_URL = "ws://localhost:8000/portfolio/stream";
const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 1_000;

export function usePortfolioStream(): UsePortfolioStreamReturn {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const [lastMessage, setLastMessage] = useState<unknown>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const manualReconnectRef = useRef(false);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    setStatus("connecting");

    try {
      const ws = new WebSocket(WS_URL);
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

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setStatus("disconnected");
        wsRef.current = null;

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
        // Retry with backoff
        const delay = backoffRef.current;
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
        reconnectTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) connect();
        }, delay);
      }
    }
  }, []);

  const reconnect = useCallback(() => {
    manualReconnectRef.current = true;
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
