/**
 * useLiveChat Hook
 *
 * WebSocket-based hook for real-time inbox stats and notifications.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useSWRConfig } from 'swr';

// =============================================================================
// TYPES
// =============================================================================

export interface LiveChatStats {
  open_count: number;
  pending_count: number;
  resolved_count: number;
  unassigned_count: number;
  total_unread: number;
  agents_online: number;
}

export interface InboxEvent {
  event: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export type InboxChannel = 'stats' | 'conversations' | 'messages';

export interface UseLiveChatOptions {
  /** Which channel to subscribe to (default: 'stats') */
  channel?: InboxChannel;
  /** Whether the WebSocket connection is enabled (default: true) */
  enabled?: boolean;
  /** Agent ID for agent-specific notifications */
  agentId?: number;
  /** Callback when a message is received */
  onMessage?: (event: InboxEvent) => void;
  /** Callback when a conversation is updated */
  onConversationUpdate?: (data: Record<string, unknown>) => void;
  /** Callback when a new message arrives */
  onNewMessage?: (data: Record<string, unknown>) => void;
}

export interface UseLiveChatReturn {
  /** Current live stats (null if not connected or channel !== 'stats') */
  stats: LiveChatStats | null;
  /** Whether the WebSocket is connected */
  isConnected: boolean;
  /** Connection error if any */
  error: Error | null;
  /** Manually reconnect */
  reconnect: () => void;
  /** Subscribe to additional channel */
  subscribe: (channel: InboxChannel) => void;
}

// =============================================================================
// HELPERS
// =============================================================================

function getWebSocketUrl(channel: InboxChannel, agentId?: number): string {
  // Get API base URL and convert to WebSocket URL
  const apiBase = process.env.NEXT_PUBLIC_API_URL || '';

  let wsBase: string;
  if (apiBase) {
    // Convert http(s):// to ws(s)://
    wsBase = apiBase.replace(/^http/, 'ws');
  } else if (typeof window !== 'undefined') {
    // Use current origin with ws protocol
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    wsBase = `${protocol}//${window.location.host}`;
  } else {
    // Server-side fallback (shouldn't be used)
    return '';
  }

  const params = new URLSearchParams({ channel });
  if (agentId) {
    params.set('agent_id', String(agentId));
  }

  return `${wsBase}/api/inbox/ws/inbox?${params.toString()}`;
}

// =============================================================================
// HOOK
// =============================================================================

export function useLiveChat(options: UseLiveChatOptions = {}): UseLiveChatReturn {
  const {
    channel = 'stats',
    enabled = true,
    agentId,
    onMessage,
    onConversationUpdate,
    onNewMessage,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [stats, setStats] = useState<LiveChatStats | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const shouldReconnectRef = useRef(true);

  const { mutate } = useSWRConfig();

  // Max reconnect attempts before giving up
  const MAX_RECONNECT_ATTEMPTS = 5;
  const BASE_RECONNECT_DELAY = 1000; // 1 second

  const clearTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as InboxEvent;

        // Handle different event types
        switch (data.event) {
          case 'connected':
            // Connection confirmed
            break;

          case 'stats_update':
            if (channel === 'stats') {
              setStats(data.data as unknown as LiveChatStats);
            }
            // Invalidate SWR cache for inbox analytics
            mutate((key: unknown) =>
              typeof key === 'string' && key.includes('/inbox/analytics')
            );
            break;

          case 'conversation_update':
          case 'conversation_assigned':
            onConversationUpdate?.(data.data);
            // Invalidate conversations cache
            mutate((key: unknown) =>
              typeof key === 'string' && key.includes('/inbox/conversations')
            );
            break;

          case 'new_message':
            onNewMessage?.(data.data);
            // Invalidate relevant caches
            mutate((key: unknown) =>
              typeof key === 'string' &&
              (key.includes('/inbox/conversations') || key.includes('/inbox/analytics'))
            );
            break;

          case 'heartbeat':
          case 'pong':
            // Heartbeat received, connection is alive
            break;

          default:
            // Unknown event type
            break;
        }

        // Call generic onMessage handler
        onMessage?.(data);
      } catch {
        // Invalid JSON, ignore
      }
    },
    [channel, mutate, onMessage, onConversationUpdate, onNewMessage]
  );

  const connect = useCallback(() => {
    // Only run in browser
    if (typeof window === 'undefined') return;
    if (!enabled) return;
    if (!shouldReconnectRef.current) return;

    const url = getWebSocketUrl(channel, agentId);
    if (!url) return;

    // Close existing connection
    if (socketRef.current) {
      socketRef.current.close();
    }

    clearTimers();

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;

        // Setup ping interval to keep connection alive
        heartbeatIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 25000); // Send ping every 25 seconds
      };

      ws.onclose = () => {
        setIsConnected(false);
        clearTimers();

        // Attempt reconnect with exponential backoff
        if (
          shouldReconnectRef.current &&
          enabled &&
          reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS
        ) {
          const delay = BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts.current);
          reconnectAttempts.current += 1;
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        setError(new Error('WebSocket connection failed'));
      };

      ws.onmessage = handleMessage;

      socketRef.current = ws;
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to create WebSocket'));
    }
  }, [enabled, channel, agentId, handleMessage, clearTimers]);

  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0;
    shouldReconnectRef.current = true;
    connect();
  }, [connect]);

  const subscribe = useCallback(
    (newChannel: InboxChannel) => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(
          JSON.stringify({ type: 'subscribe', channel: newChannel })
        );
      }
    },
    []
  );

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();

    return () => {
      shouldReconnectRef.current = false;
      clearTimers();
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [connect, clearTimers]);

  // Reconnect when options change
  useEffect(() => {
    if (enabled && !isConnected) {
      connect();
    } else if (!enabled && socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
  }, [enabled, connect, isConnected]);

  return {
    stats,
    isConnected,
    error,
    reconnect,
    subscribe,
  };
}

export default useLiveChat;
