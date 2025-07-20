import React, { useState, useEffect } from 'react';
import { useConfig } from '@/hooks/useConfig';
import { useSocket } from '@/hooks/useSocket';
import { useJobSearch } from '@/hooks/useJobSearch';
import { JobInfo } from '@/types';

import ConfigPanel from '@/components/ConfigPanel';
import ProgressPanel from '@/components/ProgressPanel';
import JobCard from '@/components/JobCard';
import Card from '@/components/Card';
import Button from '@/components/Button';

import { 
  SparklesIcon,
  DocumentArrowDownIcon,
  AdjustmentsHorizontalIcon,
  ChartBarIcon
} from '@heroicons/react/24/outline';

const MainPage: React.FC = () => {
  const { config, loading: configLoading, updateConfig } = useConfig();
  const { progressUpdates, latestUpdate, connected } = useSocket();
  const { taskStatus, results, stats, startSearch } = useJobSearch();
  
  const [selectedJob, setSelectedJob] = useState<JobInfo | null>(null);
  const [showStats, setShowStats] = useState(false);

  const isSearching = ['starting', 'running'].includes(taskStatus.status);
  const hasResults = results.length > 0;

  const handleStartSearch = async () => {
    await startSearch();
  };

  const handleConfigChange = async (newConfig: any) => {
    await updateConfig(newConfig);
  };

  const handleExportResults = () => {
    const dataStr = JSON.stringify(results, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `job-results-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (configLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-dark-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-dark-600">加载配置中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-dark-50">
      {/* 头部 */}
      <header className="bg-white/80 dark:bg-dark-100/80 backdrop-blur-xl border-b border-gray-200 dark:border-dark-300 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <SparklesIcon className="w-8 h-8 text-primary-600 mr-3" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-dark-900">
                  Boss直聘 AI助手
                </h1>
                <p className="text-sm text-gray-600 dark:text-dark-600">
                  智能化岗位筛选工具
                </p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3">
              {/* 连接状态 */}
              <div className="flex items-center">
                <div className={`w-2 h-2 rounded-full mr-2 ${
                  connected ? 'bg-green-500' : 'bg-red-500'
                }`} />
                <span className="text-xs text-gray-500 dark:text-dark-500">
                  {connected ? '已连接' : '未连接'}
                </span>
              </div>

              {/* 统计按钮 */}
              {hasResults && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowStats(!showStats)}
                  icon={<ChartBarIcon className="w-4 h-4" />}
                >
                  统计
                </Button>
              )}

              {/* 导出按钮 */}
              {hasResults && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleExportResults}
                  icon={<DocumentArrowDownIcon className="w-4 h-4" />}
                >
                  导出
                </Button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 左侧配置面板 */}
          <div className="lg:col-span-1">
            <div className="space-y-6">
              <ConfigPanel
                config={config}
                onConfigChange={handleConfigChange}
                onStartSearch={handleStartSearch}
                isSearching={isSearching}
              />
              
              <ProgressPanel
                taskStatus={taskStatus}
                progressUpdates={progressUpdates}
                latestUpdate={latestUpdate}
              />
            </div>
          </div>

          {/* 右侧结果展示 */}
          <div className="lg:col-span-2">
            <div className="space-y-6">
              {/* 统计信息 */}
              {(showStats || isSearching) && (
                <Card>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-dark-900 mb-4 flex items-center">
                    <ChartBarIcon className="w-5 h-5 mr-2" />
                    统计信息
                  </h3>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-primary-600">
                        {stats.total_jobs}
                      </div>
                      <div className="text-sm text-gray-600 dark:text-dark-600">
                        总搜索数
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">
                        {stats.analyzed_jobs}
                      </div>
                      <div className="text-sm text-gray-600 dark:text-dark-600">
                        已分析
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">
                        {stats.qualified_jobs}
                      </div>
                      <div className="text-sm text-gray-600 dark:text-dark-600">
                        合格岗位
                      </div>
                    </div>
                  </div>
                </Card>
              )}

              {/* 岗位列表 */}
              {hasResults ? (
                <div>
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-semibold text-gray-900 dark:text-dark-900">
                      推荐岗位 ({results.length})
                    </h2>
                  </div>
                  
                  <div className="grid gap-6">
                    {results.map((job, index) => (
                      <JobCard
                        key={index}
                        job={job}
                        onViewDetails={setSelectedJob}
                      />
                    ))}
                  </div>
                </div>
              ) : (
                /* 空状态 */
                <Card className="text-center py-12">
                  <AdjustmentsHorizontalIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 dark:text-dark-900 mb-2">
                    等待搜索结果
                  </h3>
                  <p className="text-gray-600 dark:text-dark-600 mb-6">
                    配置搜索参数并点击"开始搜索"来查找合适的岗位
                  </p>
                  {!isSearching && (
                    <Button
                      variant="primary"
                      onClick={handleStartSearch}
                      disabled={!config?.search?.keyword}
                    >
                      开始搜索
                    </Button>
                  )}
                </Card>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* 岗位详情模态框 */}
      {selectedJob && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <Card className="max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold text-gray-900 dark:text-dark-900">
                岗位详情
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedJob(null)}
              >
                ×
              </Button>
            </div>
            
            <div className="space-y-4">
              <div>
                <h4 className="font-medium text-gray-900 dark:text-dark-900">
                  {selectedJob.title}
                </h4>
                <p className="text-gray-600 dark:text-dark-600">
                  {selectedJob.company}
                </p>
              </div>
              
              {selectedJob.job_description && (
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-dark-900 mb-2">
                    岗位描述
                  </h4>
                  <p className="text-sm text-gray-600 dark:text-dark-600 whitespace-pre-wrap">
                    {selectedJob.job_description}
                  </p>
                </div>
              )}
              
              {selectedJob.job_requirements && (
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-dark-900 mb-2">
                    岗位要求
                  </h4>
                  <p className="text-sm text-gray-600 dark:text-dark-600 whitespace-pre-wrap">
                    {selectedJob.job_requirements}
                  </p>
                </div>
              )}
              
              {selectedJob.company_details && (
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-dark-900 mb-2">
                    公司详情
                  </h4>
                  <p className="text-sm text-gray-600 dark:text-dark-600">
                    {selectedJob.company_details}
                  </p>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default MainPage;