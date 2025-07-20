import React from 'react';
import classNames from 'classnames';

interface ProgressBarProps {
  progress: number; // 0-100
  className?: string;
  showLabel?: boolean;
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  color?: 'primary' | 'success' | 'warning' | 'error';
}

const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  className,
  showLabel = true,
  label,
  size = 'md',
  color = 'primary',
}) => {
  const normalizedProgress = Math.min(100, Math.max(0, progress));

  const containerClasses = classNames(
    'progress-bar',
    {
      'h-1': size === 'sm',
      'h-2': size === 'md',
      'h-3': size === 'lg',
    },
    className
  );

  const fillClasses = classNames(
    'progress-fill',
    {
      'bg-gradient-to-r from-primary-500 to-primary-600': color === 'primary',
      'bg-gradient-to-r from-green-500 to-green-600': color === 'success',
      'bg-gradient-to-r from-yellow-500 to-yellow-600': color === 'warning',
      'bg-gradient-to-r from-red-500 to-red-600': color === 'error',
    }
  );

  return (
    <div className="w-full">
      {showLabel && (
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-medium text-gray-700 dark:text-dark-700">
            {label || '进度'}
          </span>
          <span className="text-sm text-gray-500 dark:text-dark-500">
            {Math.round(normalizedProgress)}%
          </span>
        </div>
      )}
      <div className={containerClasses}>
        <div
          className={fillClasses}
          style={{ width: `${normalizedProgress}%` }}
        />
      </div>
    </div>
  );
};

export default ProgressBar;