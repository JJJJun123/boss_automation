// 应用类型定义

export interface JobInfo {
  title: string;
  company: string;
  salary: string;
  tags: string[];
  url: string;
  company_info?: string;
  work_location?: string;
  benefits?: string;
  experience_required?: string;
  job_description?: string;
  job_requirements?: string;
  company_details?: string;
  analysis?: JobAnalysis;
}

export interface JobAnalysis {
  score: number;
  recommendation: string;
  reason: string;
  summary: string;
}

export interface SearchConfig {
  keyword: string;
  selected_cities: string[];
  max_jobs: number;
  max_analyze_jobs: number;
  fetch_details: boolean;
  quick_keywords: string[];
}

export interface AIConfig {
  provider: string;
  min_score: number;
  analysis_depth: string;
}

export interface AppConfig {
  search: SearchConfig;
  ai: AIConfig;
  app: {
    name: string;
    version: string;
    cities: Record<string, { name: string; code: string }>;
  };
}

export interface TaskStatus {
  status: 'idle' | 'starting' | 'running' | 'completed' | 'failed' | 'stopping' | 'stopped';
  start_time?: string;
  end_time?: string;
  error?: string;
}

export interface TaskResults {
  status: string;
  results: JobInfo[];
  stats: {
    total_jobs: number;
    analyzed_jobs: number;
    qualified_jobs: number;
  };
  start_time?: string;
  end_time?: string;
}

export interface ProgressUpdate {
  message: string;
  progress?: number;
  timestamp: string;
  data?: any;
}

export interface Theme {
  mode: 'light' | 'dark' | 'auto';
}