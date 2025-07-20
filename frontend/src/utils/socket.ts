import { io, Socket } from 'socket.io-client';
import { ProgressUpdate } from '@/types';

class SocketService {
  private socket: Socket | null = null;
  private progressCallback: ((update: ProgressUpdate) => void) | null = null;

  connect() {
    if (this.socket?.connected) {
      return;
    }

    this.socket = io('/', {
      transports: ['websocket', 'polling'],
      timeout: 20000,
    });

    this.socket.on('connect', () => {
      console.log('WebSocket连接成功');
    });

    this.socket.on('disconnect', () => {
      console.log('WebSocket连接断开');
    });

    this.socket.on('connected', (data) => {
      console.log('服务器确认连接:', data);
    });

    this.socket.on('progress_update', (update: ProgressUpdate) => {
      if (this.progressCallback) {
        this.progressCallback(update);
      }
    });

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket连接错误:', error);
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  onProgress(callback: (update: ProgressUpdate) => void) {
    this.progressCallback = callback;
  }

  offProgress() {
    this.progressCallback = null;
  }

  isConnected(): boolean {
    return this.socket?.connected || false;
  }
}

// 创建单例实例
export const socketService = new SocketService();

export default socketService;