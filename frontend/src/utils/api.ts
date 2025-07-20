import axios from 'axios';
import { AppConfig, TaskStatus, TaskResults } from '@/types';

// 创建axios实例
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    const message = error.response?.data?.error || error.message || '请求失败';
    return Promise.reject(new Error(message));
  }
);

// API方法
export const apiService = {
  // 健康检查
  async healthCheck() {
    return api.get('/health');
  },

  // 获取配置
  async getConfig(): Promise<AppConfig> {
    return api.get('/config');
  },

  // 更新配置
  async updateConfig(config: Partial<AppConfig>) {
    return api.post('/config', config);
  },

  // 启动岗位搜索
  async startJobSearch(params: any = {}) {
    return api.post('/jobs/search', params);
  },

  // 获取任务状态
  async getJobStatus(): Promise<TaskStatus> {
    return api.get('/jobs/status');
  },

  // 获取任务结果
  async getJobResults(): Promise<TaskResults> {
    return api.get('/jobs/results');
  },
};

export default api;