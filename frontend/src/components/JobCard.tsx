import React from 'react';
import { JobInfo } from '@/types';
import Card from './Card';
import Button from './Button';
import { 
  BuildingOfficeIcon, 
  CurrencyDollarIcon, 
  MapPinIcon,
  StarIcon,
  ExternalLinkIcon,
  ClipboardDocumentListIcon 
} from '@heroicons/react/24/outline';
import classNames from 'classnames';

interface JobCardProps {
  job: JobInfo;
  onViewDetails?: (job: JobInfo) => void;
}

const JobCard: React.FC<JobCardProps> = ({ job, onViewDetails }) => {
  const analysis = job.analysis;
  const score = analysis?.score || 0;
  
  const getScoreColor = (score: number) => {
    if (score >= 8) return 'text-green-600 bg-green-100 dark:bg-green-900/30';
    if (score >= 6) return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30';
    return 'text-red-600 bg-red-100 dark:bg-red-900/30';
  };

  const getRecommendationIcon = (score: number) => {
    if (score >= 8) return '⭐⭐⭐';
    if (score >= 6) return '⭐⭐';
    return '⭐';
  };

  return (
    <Card hover className="relative overflow-hidden">
      {/* 评分徽章 */}
      <div className="absolute top-4 right-4">
        <div className={classNames(
          'inline-flex items-center px-3 py-1 rounded-full text-sm font-medium',
          getScoreColor(score)
        )}>
          <StarIcon className="w-4 h-4 mr-1" />
          {score}/10
        </div>
      </div>

      {/* 岗位基本信息 */}
      <div className="mb-4 pr-20">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-dark-900 mb-2">
          {job.title}
        </h3>
        
        <div className="flex items-center text-gray-600 dark:text-dark-600 mb-2">
          <BuildingOfficeIcon className="w-4 h-4 mr-2" />
          <span>{job.company}</span>
        </div>

        <div className="flex items-center text-gray-600 dark:text-dark-600 mb-2">
          <CurrencyDollarIcon className="w-4 h-4 mr-2" />
          <span className="font-medium text-green-600">{job.salary}</span>
        </div>

        {job.work_location && (
          <div className="flex items-center text-gray-600 dark:text-dark-600 mb-2">
            <MapPinIcon className="w-4 h-4 mr-2" />
            <span>{job.work_location}</span>
          </div>
        )}
      </div>

      {/* 标签 */}
      {job.tags && job.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {job.tags.slice(0, 3).map((tag, index) => (
            <span
              key={index}
              className="tag"
            >
              {tag}
            </span>
          ))}
          {job.tags.length > 3 && (
            <span className="tag">
              +{job.tags.length - 3}
            </span>
          )}
        </div>
      )}

      {/* AI分析 */}
      {analysis && (
        <div className="mb-4 p-4 bg-gray-50 dark:bg-dark-200 rounded-2xl">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700 dark:text-dark-700">
              AI分析
            </span>
            <span className="text-sm">
              {getRecommendationIcon(score)} {analysis.recommendation}
            </span>
          </div>
          
          <p className="text-sm text-gray-600 dark:text-dark-600 mb-2">
            {analysis.summary}
          </p>
          
          <p className="text-xs text-gray-500 dark:text-dark-500 line-clamp-2">
            {analysis.reason}
          </p>
        </div>
      )}

      {/* 福利待遇 */}
      {job.benefits && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-gray-700 dark:text-dark-700 mb-2">
            福利待遇
          </h4>
          <p className="text-sm text-gray-600 dark:text-dark-600">
            {job.benefits}
          </p>
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex gap-2">
        {job.url && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => window.open(job.url, '_blank')}
            icon={<ExternalLinkIcon className="w-4 h-4" />}
          >
            查看详情
          </Button>
        )}
        
        {onViewDetails && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onViewDetails(job)}
            icon={<ClipboardDocumentListIcon className="w-4 h-4" />}
          >
            完整信息
          </Button>
        )}
      </div>
    </Card>
  );
};

export default JobCard;