import React from 'react';
import { ProgressUpdate, TaskStatus } from '@/types';
import Card from './Card';
import ProgressBar from './ProgressBar';
import { 
  ClockIcon, 
  CheckCircleIcon, 
  ExclamationCircleIcon,
  InformationCircleIcon 
} from '@heroicons/react/24/outline';
import classNames from 'classnames';

interface ProgressPanelProps {
  taskStatus: TaskStatus;
  progressUpdates: ProgressUpdate[];
  latestUpdate: ProgressUpdate | null;
}

const ProgressPanel: React.FC<ProgressPanelProps> = ({
  taskStatus,
  progressUpdates,
  latestUpdate,
}) => {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <ExclamationCircleIcon className="w-5 h-5 text-red-500" />;
      case 'running':
      case 'starting':
        return <ClockIcon className="w-5 h-5 text-blue-500 animate-spin" />;
      default:
        return <InformationCircleIcon className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'idle':
        return '等待开始';
      case 'starting':
        return '正在启动...';
      case 'running':
        return '正在运行...';
      case 'completed':
        return '任务完成';
      case 'failed':
        return '任务失败';
      case 'stopping':
        return '正在停止...';
      case 'stopped':
        return '已停止';
      default:
        return status;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-100 dark:bg-green-900/30';
      case 'failed':
        return 'text-red-600 bg-red-100 dark:bg-red-900/30';
      case 'running':
      case 'starting':
        return 'text-blue-600 bg-blue-100 dark:bg-blue-900/30';
      default:
        return 'text-gray-600 bg-gray-100 dark:bg-gray-900/30';
    }
  };

  const currentProgress = latestUpdate?.progress || 0;
  const isActive = ['starting', 'running'].includes(taskStatus.status);

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-dark-900">
          任务进度
        </h3>
        <div className={classNames(
          'inline-flex items-center px-3 py-1 rounded-full text-sm font-medium',
          getStatusColor(taskStatus.status)
        )}>
          {getStatusIcon(taskStatus.status)}
          <span className="ml-2">{getStatusText(taskStatus.status)}</span>
        </div>
      </div>

      {/* 进度条 */}
      {isActive && (
        <div className="mb-6">
          <ProgressBar
            progress={currentProgress}
            label="总体进度"
            color={taskStatus.status === 'failed' ? 'error' : 'primary'}
          />
        </div>
      )}

      {/* 当前状态消息 */}
      {latestUpdate && (
        <div className="mb-4 p-4 bg-gray-50 dark:bg-dark-200 rounded-2xl">
          <div className="flex items-start">
            <div className="flex-shrink-0 mt-0.5">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            </div>
            <div className="ml-3 flex-1">
              <p className="text-sm font-medium text-gray-900 dark:text-dark-900">
                {latestUpdate.message}
              </p>
              <p className="text-xs text-gray-500 dark:text-dark-500 mt-1">
                {latestUpdate.timestamp}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 错误信息 */}
      {taskStatus.status === 'failed' && taskStatus.error && (
        <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl">
          <div className="flex items-start">
            <ExclamationCircleIcon className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="ml-3">
              <h4 className="text-sm font-medium text-red-800 dark:text-red-200">
                错误信息
              </h4>
              <p className="text-sm text-red-700 dark:text-red-300 mt-1">
                {taskStatus.error}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 历史进度 */}
      {progressUpdates.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 dark:text-dark-700 mb-3">
            执行日志
          </h4>
          <div className="max-h-48 overflow-y-auto space-y-2">
            {progressUpdates.slice(-10).map((update, index) => (
              <div
                key={index}
                className="flex items-start text-sm"
              >
                <div className="flex-shrink-0 mt-1">
                  <div className="w-1.5 h-1.5 bg-gray-400 rounded-full" />
                </div>
                <div className="ml-3 flex-1">
                  <span className="text-gray-600 dark:text-dark-600">
                    {update.message}
                  </span>
                  <span className="text-xs text-gray-400 dark:text-dark-400 ml-2">
                    {update.timestamp}
                  </span>
                </div>
                {update.progress !== undefined && (
                  <div className="flex-shrink-0 text-xs text-gray-500 dark:text-dark-500">
                    {update.progress}%
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 空状态 */}
      {!isActive && progressUpdates.length === 0 && taskStatus.status === 'idle' && (
        <div className="text-center py-8">
          <ClockIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500 dark:text-dark-500">
            点击"开始搜索"启动任务
          </p>
        </div>
      )}
    </Card>
  );
};

export default ProgressPanel;