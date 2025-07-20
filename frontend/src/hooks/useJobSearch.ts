import { useState, useEffect, useCallback } from 'react';
import { TaskStatus, TaskResults, JobInfo } from '@/types';
import { apiService } from '@/utils/api';

export const useJobSearch = () => {
  const [taskStatus, setTaskStatus] = useState<TaskStatus>({ status: 'idle' });
  const [results, setResults] = useState<JobInfo[]>([]);
  const [stats, setStats] = useState({
    total_jobs: 0,
    analyzed_jobs: 0,
    qualified_jobs: 0,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 获取任务状态
  const fetchTaskStatus = useCallback(async () => {
    try {
      const status = await apiService.getJobStatus();
      setTaskStatus(status);
      return status;
    } catch (err) {
      console.error('获取任务状态失败:', err);
      return null;
    }
  }, []);

  // 获取任务结果
  const fetchResults = useCallback(async () => {
    try {
      const resultData = await apiService.getJobResults();
      setResults(resultData.results);
      setStats(resultData.stats);
      return resultData;
    } catch (err) {
      console.error('获取结果失败:', err);
      return null;
    }
  }, []);

  // 启动搜索任务
  const startSearch = useCallback(async (params: any = {}) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await apiService.startJobSearch(params);
      
      // 开始轮询任务状态
      const pollStatus = async () => {
        const status = await fetchTaskStatus();
        if (status && (status.status === 'completed' || status.status === 'failed')) {
          // 任务完成，获取结果
          await fetchResults();
          setLoading(false);
        } else if (status && status.status === 'running') {
          // 任务进行中，继续轮询
          setTimeout(pollStatus, 2000);
        }
      };
      
      // 开始轮询
      setTimeout(pollStatus, 1000);
      
      return response;
    } catch (err) {
      setError(err instanceof Error ? err.message : '启动搜索失败');
      setLoading(false);
      return null;
    }
  }, [fetchTaskStatus, fetchResults]);

  // 组件挂载时获取当前状态
  useEffect(() => {
    fetchTaskStatus();
    fetchResults();
  }, [fetchTaskStatus, fetchResults]);

  return {
    taskStatus,
    results,
    stats,
    loading,
    error,
    startSearch,
    fetchTaskStatus,
    fetchResults,
  };
};