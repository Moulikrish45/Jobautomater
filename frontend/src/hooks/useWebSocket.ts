import { useEffect, useRef, useState, useCallback } from 'react';

export interface WebSocketMessage {
  type: string;
  user_id: string;
  timestamp: string;
  data?: any;
  message?: string;
}

export interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'error';
  sendMessage: (message: any) => void;
  lastMessage: WebSocketMessage | null;
  reconnect: () => void;
}

export const useWebSocket = (
  userId: string,
  options: UseWebSocketOptions = {}
): UseWebSocketReturn => {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectInterval = 5000,
    maxReconnectAttempts = 3,
  } = options;

  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(true);
  const hasShownErrorRef = useRef(false);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setConnectionState('connecting');
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/${userId}`;
    
    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        setConnectionState('connected');
        reconnectAttemptsRef.current = 0;
        hasShownErrorRef.current = false;
        onConnect?.();
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          onMessage?.(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      wsRef.current.onclose = (event) => {
        setConnectionState('disconnected');
        wsRef.current = null;
        
        // Only call onDisconnect if we were previously connected
        if (reconnectAttemptsRef.current === 0) {
          onDisconnect?.();
        }

        // Attempt to reconnect if not manually closed
        if (shouldReconnectRef.current && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++;
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          setConnectionState('error');
          shouldReconnectRef.current = false;
          
          // Only show error once
          if (!hasShownErrorRef.current) {
            hasShownErrorRef.current = true;
            onError?.(new Event('max_reconnect_attempts_reached'));
          }
        }
      };

      wsRef.current.onerror = (error) => {
        // Only log and notify on first error
        if (!hasShownErrorRef.current) {
          console.error('WebSocket connection failed');
          hasShownErrorRef.current = true;
        }
      };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setConnectionState('error');
    }
  }, [userId, onMessage, onConnect, onDisconnect, onError, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }
    
    setConnectionState('disconnected');
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected. Message not sent:', message);
    }
  }, []);

  const reconnect = useCallback(() => {
    disconnect();
    shouldReconnectRef.current = true;
    reconnectAttemptsRef.current = 0;
    setTimeout(connect, 100);
  }, [connect, disconnect]);

  useEffect(() => {
    if (userId) {
      shouldReconnectRef.current = true;
      connect();
    }

    return () => {
      disconnect();
    };
  }, [userId, connect, disconnect]);

  // Send ping every 30 seconds to keep connection alive
  useEffect(() => {
    if (connectionState === 'connected') {
      const pingInterval = setInterval(() => {
        sendMessage({ type: 'ping', timestamp: new Date().toISOString() });
      }, 30000);

      return () => clearInterval(pingInterval);
    }
  }, [connectionState, sendMessage]);

  return {
    isConnected: connectionState === 'connected',
    connectionState,
    sendMessage,
    lastMessage,
    reconnect,
  };
};