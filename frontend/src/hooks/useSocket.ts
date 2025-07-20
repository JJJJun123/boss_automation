import { useState, useEffect, useCallback } from 'react';
import { ProgressUpdate } from '@/types';
import { socketService } from '@/utils/socket';

export const useSocket = () => {
  const [connected, setConnected] = useState(false);
  const [progressUpdates, setProgressUpdates] = useState<ProgressUpdate[]>([]);
  const [latestUpdate, setLatestUpdate] = useState<ProgressUpdate | null>(null);

  // 连接WebSocket
  const connect = useCallback(() => {
    socketService.connect();
  }, []);

  // 断开WebSocket
  const disconnect = useCallback(() => {
    socketService.disconnect();
  }, []);

  // 清空进度更新
  const clearUpdates = useCallback(() => {
    setProgressUpdates([]);
    setLatestUpdate(null);
  }, []);

  useEffect(() => {
    // 连接状态检查
    const checkConnection = () => {
      setConnected(socketService.isConnected());
    };

    // 设置进度更新回调
    socketService.onProgress((update: ProgressUpdate) => {
      setProgressUpdates(prev => [...prev, update]);
      setLatestUpdate(update);
    });

    // 定期检查连接状态
    const interval = setInterval(checkConnection, 1000);

    // 初始连接
    connect();

    return () => {
      clearInterval(interval);
      socketService.offProgress();
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connected,
    progressUpdates,
    latestUpdate,
    connect,
    disconnect,
    clearUpdates,
  };
};