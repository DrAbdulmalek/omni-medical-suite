'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import type { WebSocketMessage } from '@/types';

// ============================================================================
// Configuration
// ============================================================================

const DEFAULT_WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';
const MAX_RETRIES = 5;
const BASE_RETRY_DELAY_MS = 1000;

// ============================================================================
// Hook Return Type
// ============================================================================

interface UseWebSocketReturn {
  /** Whether the WebSocket is currently connected */
  isConnected: boolean;
  /** The most recent message received */
  lastMessage: WebSocketMessage | null;
  /** Number of reconnection attempts (0 = first connect) */
  retryCount: number;
  /** Send a JSON message through the WebSocket */
  send: (message: Record<string, unknown>) => void;
  /** Subscribe to specific message types */
  subscribe: (callback: (message: WebSocketMessage) => void) => () => void;
  /** Manually reconnect */
  reconnect: () => void;
}

// ============================================================================
// Custom Hook
// ============================================================================

export function useWebSocket(url: string = DEFAULT_WS_URL): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const subscribersRef = useRef<Set<(msg: WebSocketMessage) => void>>(new Set());
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalCloseRef = useRef(false);
  const mountedRef = useRef(true);

  /**
   * Calculate exponential backoff delay: BASE_DELAY * 2^attempt
   */
  const getRetryDelay = useCallback((attempt: number): number => {
    return Math.min(BASE_RETRY_DELAY_MS * Math.pow(2, attempt), 30000);
  }, []);

  /**
   * Notify all subscribers of a new message
   */
  const notifySubscribers = useCallback((message: WebSocketMessage) => {
    subscribersRef.current.forEach((cb) => {
      try {
        cb(message);
      } catch (err) {
        console.error('[WS] Subscriber error:', err);
      }
    });
  }, []);

  /**
   * Establish WebSocket connection
   */
  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    // Clean up any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        setRetryCount(0);
        console.log('[WS] Connected to', url);
      };

      ws.onmessage = (event: MessageEvent) => {
        if (!mountedRef.current) return;
        try {
          const parsed: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(parsed);
          notifySubscribers(parsed);
        } catch {
          console.warn('[WS] Failed to parse message:', event.data);
        }
      };

      ws.onclose = (event: CloseEvent) => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        wsRef.current = null;

        if (!intentionalCloseRef.current) {
          console.log(`[WS] Disconnected (code: ${event.code}). Reconnecting...`);
          const delay = getRetryDelay(retryCount);
          setRetryCount((prev) => {
            const next = prev + 1;
            if (next > MAX_RETRIES) {
              console.error('[WS] Max retries exceeded.');
              return prev;
            }
            retryTimerRef.current = setTimeout(() => {
              if (mountedRef.current) connect();
            }, delay);
            return next;
          });
        }
      };

      ws.onerror = (error: Event) => {
        console.error('[WS] Error:', error);
        ws.close();
      };
    } catch (err) {
      console.error('[WS] Failed to create WebSocket:', err);
    }
  }, [url, retryCount, getRetryDelay, notifySubscribers]);

  /**
   * Send a JSON-serialized message
   */
  const send = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('[WS] Cannot send — connection not open.');
    }
  }, []);

  /**
   * Subscribe to messages. Returns an unsubscribe function.
   */
  const subscribe = useCallback(
    (callback: (message: WebSocketMessage) => void): (() => void) => {
      subscribersRef.current.add(callback);
      return () => {
        subscribersRef.current.delete(callback);
      };
    },
    []
  );

  /**
   * Manual reconnect
   */
  const reconnect = useCallback(() => {
    intentionalCloseRef.current = false;
    setRetryCount(0);
    connect();
  }, [connect]);

  // --- Lifecycle ---

  useEffect(() => {
    mountedRef.current = true;
    intentionalCloseRef.current = false;
    connect();

    return () => {
      mountedRef.current = false;
      intentionalCloseRef.current = true;
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  return {
    isConnected,
    lastMessage,
    retryCount,
    send,
    subscribe,
    reconnect,
  };
}

export default useWebSocket;
