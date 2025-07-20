import { useState, useEffect, useCallback } from 'react';
import { AppConfig } from '@/types';
import { apiService } from '@/utils/api';

export const useConfig = () => {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 加载配置
  const loadConfig = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const configData = await apiService.getConfig();
      setConfig(configData);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  // 更新配置
  const updateConfig = useCallback(async (newConfig: Partial<AppConfig>) => {
    try {
      setError(null);
      await apiService.updateConfig(newConfig);
      
      // 重新加载配置
      await loadConfig();
      
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新配置失败');
      return false;
    }
  }, [loadConfig]);

  // 初始化时加载配置
  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  return {
    config,
    loading,
    error,
    loadConfig,
    updateConfig,
  };
};