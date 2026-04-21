import { useEffect, useRef, useState, useCallback } from 'react';

interface WsState<T> {
  messages: T[];
  connected: boolean;
  lastMessage: T | null;
}

export default function useWebSocket<T>(path: string, maxHistory = 1000): WsState<T> {
  const [messages, setMessages] = useState<T[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef  = useRef<WebSocket | null>(null);
  const retry  = useRef(0);
  const active = useRef(true);

  const connect = useCallback(() => {
    if (!active.current) return;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}${path}`;
    const ws  = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => { setConnected(true); retry.current = 0; };

    ws.onmessage = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data as string) as T;
        setMessages(prev => {
          const next = [...prev, data];
          return next.length > maxHistory ? next.slice(-maxHistory) : next;
        });
      } catch {
        // non-JSON frame — ignore
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (!active.current) return;
      // Exponential back-off: 500ms → 1s → 2s → … → 30s
      const delay = Math.min(500 * 2 ** retry.current, 30_000);
      retry.current += 1;
      setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, [path, maxHistory]);

  useEffect(() => {
    active.current = true;
    connect();
    return () => {
      active.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  return { messages, connected, lastMessage: messages[messages.length - 1] ?? null };
}
