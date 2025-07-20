import React, { useState, useEffect } from 'react';
import { AppConfig } from '@/types';
import Card from './Card';
import Button from './Button';
import { 
  CogIcon, 
  MagnifyingGlassIcon,
  MapPinIcon,
  CpuChipIcon,
  AdjustmentsHorizontalIcon 
} from '@heroicons/react/24/outline';
import classNames from 'classnames';

interface ConfigPanelProps {
  config: AppConfig | null;
  onConfigChange: (config: Partial<AppConfig>) => void;
  onStartSearch: () => void;
  isSearching: boolean;
}

const ConfigPanel: React.FC<ConfigPanelProps> = ({
  config,
  onConfigChange,
  onStartSearch,
  isSearching,
}) => {
  const [localConfig, setLocalConfig] = useState<Partial<AppConfig>>({});
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (config) {
      setLocalConfig(config);
    }
  }, [config]);

  const handleInputChange = (path: string, value: any) => {
    const newConfig = { ...localConfig };
    const keys = path.split('.');
    let current: any = newConfig;
    
    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) {
        current[keys[i]] = {};
      }
      current = current[keys[i]];
    }
    
    current[keys[keys.length - 1]] = value;
    setLocalConfig(newConfig);
  };

  const handleSaveConfig = () => {
    onConfigChange(localConfig);
  };

  const cities = config?.app?.cities || {};
  const cityOptions = Object.entries(cities).map(([key, city]) => ({
    value: key,
    label: city.name,
  }));

  const quickKeywords = localConfig.search?.quick_keywords || [];

  return (
    <Card className="h-fit">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-dark-900 flex items-center">
          <CogIcon className="w-5 h-5 mr-2" />
          搜索配置
        </h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded(!expanded)}
          icon={<AdjustmentsHorizontalIcon className="w-4 h-4" />}
        >
          {expanded ? '收起' : '展开'}
        </Button>
      </div>

      <div className="space-y-6">
        {/* 搜索关键词 */}
        <div>
          <label className="flex items-center text-sm font-medium text-gray-700 dark:text-dark-700 mb-2">
            <MagnifyingGlassIcon className="w-4 h-4 mr-2" />
            搜索关键词
          </label>
          <input
            type="text"
            className="input-field"
            value={localConfig.search?.keyword || ''}
            onChange={(e) => handleInputChange('search.keyword', e.target.value)}
            placeholder="输入搜索关键词"
          />
          
          {/* 快捷关键词 */}
          {quickKeywords.length > 0 && (
            <div className="mt-2">
              <p className="text-xs text-gray-500 dark:text-dark-500 mb-2">快捷选择:</p>
              <div className="flex flex-wrap gap-2">
                {quickKeywords.map((keyword, index) => (
                  <button
                    key={index}
                    className="tag hover:bg-primary-200 dark:hover:bg-primary-800/40 cursor-pointer transition-colors"
                    onClick={() => handleInputChange('search.keyword', keyword)}
                  >
                    {keyword}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 城市选择 */}
        <div>
          <label className="flex items-center text-sm font-medium text-gray-700 dark:text-dark-700 mb-2">
            <MapPinIcon className="w-4 h-4 mr-2" />
            目标城市
          </label>
          <select
            className="input-field"
            value={localConfig.search?.selected_cities?.[0] || ''}
            onChange={(e) => handleInputChange('search.selected_cities', [e.target.value])}
          >
            <option value="">选择城市</option>
            {cityOptions.map((city) => (
              <option key={city.value} value={city.value}>
                {city.label}
              </option>
            ))}
          </select>
        </div>

        {/* 基础配置 */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium text-gray-700 dark:text-dark-700 mb-2 block">
              搜索数量
            </label>
            <input
              type="number"
              className="input-field"
              value={localConfig.search?.max_jobs || 20}
              onChange={(e) => handleInputChange('search.max_jobs', parseInt(e.target.value))}
              min="1"
              max="100"
            />
          </div>
          
          <div>
            <label className="text-sm font-medium text-gray-700 dark:text-dark-700 mb-2 block">
              分析数量
            </label>
            <input
              type="number"
              className="input-field"
              value={localConfig.search?.max_analyze_jobs || 10}
              onChange={(e) => handleInputChange('search.max_analyze_jobs', parseInt(e.target.value))}
              min="1"
              max="50"
            />
          </div>
        </div>

        {/* 高级配置 */}
        {expanded && (
          <div className="space-y-4 pt-4 border-t border-gray-200 dark:border-dark-300">
            {/* AI模型选择 */}
            <div>
              <label className="flex items-center text-sm font-medium text-gray-700 dark:text-dark-700 mb-2">
                <CpuChipIcon className="w-4 h-4 mr-2" />
                AI模型
              </label>
              <select
                className="input-field"
                value={localConfig.ai?.provider || 'deepseek'}
                onChange={(e) => handleInputChange('ai.provider', e.target.value)}
              >
                <option value="deepseek">DeepSeek (推荐)</option>
                <option value="claude">Claude</option>
                <option value="gemini">Gemini</option>
              </select>
            </div>

            {/* 最低评分 */}
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-dark-700 mb-2 block">
                最低评分: {localConfig.ai?.min_score || 6}/10
              </label>
              <input
                type="range"
                className="w-full"
                min="1"
                max="10"
                value={localConfig.ai?.min_score || 6}
                onChange={(e) => handleInputChange('ai.min_score', parseInt(e.target.value))}
              />
            </div>

            {/* 获取详细信息 */}
            <div className="flex items-center">
              <input
                type="checkbox"
                id="fetch_details"
                className="w-4 h-4 text-primary-600 bg-gray-100 border-gray-300 rounded focus:ring-primary-500"
                checked={localConfig.search?.fetch_details || false}
                onChange={(e) => handleInputChange('search.fetch_details', e.target.checked)}
              />
              <label htmlFor="fetch_details" className="ml-2 text-sm text-gray-700 dark:text-dark-700">
                获取详细岗位信息 (会增加抓取时间)
              </label>
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex gap-3 pt-4">
          <Button
            variant="primary"
            onClick={onStartSearch}
            loading={isSearching}
            disabled={!localConfig.search?.keyword || isSearching}
            className="flex-1"
          >
            {isSearching ? '搜索中...' : '开始搜索'}
          </Button>
          
          <Button
            variant="secondary"
            onClick={handleSaveConfig}
            disabled={isSearching}
          >
            保存配置
          </Button>
        </div>
      </div>
    </Card>
  );
};

export default ConfigPanel;