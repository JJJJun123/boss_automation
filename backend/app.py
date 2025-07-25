#!/usr/bin/env python3
"""
Boss直聘自动化Web应用后端
Flask + SocketIO 实现
"""

import os
import sys
import logging
import threading
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_manager import ConfigManager
from crawler.boss_spider import BossSpider
from crawler.playwright_spider import search_with_playwright_mcp
from analyzer.job_analyzer import JobAnalyzer


# 创建Flask应用
app = Flask(__name__)
app.secret_key = 'boss-zhipin-automation-secret-key-2024'  # 添加secret key用于session

# 配置CORS
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5000", "http://127.0.0.1:5000"])

# 配置SocketIO
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5000", "http://127.0.0.1:5000"])

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局变量
config_manager = None
current_spider = None
current_job = None  # 存储当前分析任务状态


def init_config():
    """初始化配置管理器"""
    global config_manager
    try:
        config_manager = ConfigManager()
        logger.info("配置管理器初始化成功")
        return True
    except Exception as e:
        logger.error(f"配置管理器初始化失败: {e}")
        return False


def emit_progress(message, progress=None, data=None):
    """发送进度更新到前端"""
    payload = {
        'message': message,
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }
    if progress is not None:
        payload['progress'] = progress
    if data is not None:
        payload['data'] = data
    
    socketio.emit('progress_update', payload)
    logger.info(f"Progress: {message}")


@app.route('/')
def serve_frontend():
    """提供前端页面"""
    return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Boss直聘智能简历分析与岗位匹配系统</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
    <script src="https://cdn.socket.io/4.7.4/socket.io.min.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'San Francisco', 'Helvetica Neue', Arial, sans-serif; }
        .glass { backdrop-filter: blur(20px); background: rgba(255, 255, 255, 0.8); }
        .btn { @apply px-6 py-3 rounded-2xl font-medium transition-all duration-200 transform hover:scale-105; }
        .btn-primary { @apply bg-blue-600 hover:bg-blue-700 text-white; }
        .btn-secondary { @apply bg-gray-100 hover:bg-gray-200 text-gray-800; }
        .card { @apply bg-white rounded-3xl shadow-lg p-6 border border-gray-200; }
        
        /* 页面切换样式 */
        .page-content { display: none; }
        .page-content.active { display: block; }
        .nav-btn { transition: all 0.2s ease; }
        .nav-btn.active { 
            color: #2563eb !important; 
            border-bottom-color: #2563eb !important; 
            font-weight: 600;
        }
        
        /* 文件上传样式 */
        .upload-area {
            border: 2px dashed #d1d5db;
            transition: all 0.2s ease;
        }
        .upload-area.dragover {
            border-color: #2563eb;
            background-color: #eff6ff;
        }
        
        /* AI输出查看器样式 */
        .ai-output-viewer {
            max-height: 500px;
            overflow-y: auto;
        }
        .analysis-step {
            border-left: 3px solid #e5e7eb;
            transition: all 0.2s ease;
        }
        .analysis-step.expanded {
            border-left-color: #2563eb;
            background-color: #f8fafc;
        }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- 头部 -->
    <header class="glass border-b border-gray-200 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 py-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center">
                    <div class="w-10 h-10 bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl mr-4 flex items-center justify-center">
                        <span class="text-white font-bold text-lg">🤖</span>
                    </div>
                    <div>
                        <h1 class="text-2xl font-bold text-gray-900">Boss直聘智能助手</h1>
                        <p class="text-sm text-gray-600">AI驱动的简历分析与岗位匹配系统</p>
                    </div>
                </div>
                <div class="flex items-center space-x-6">
                    <nav class="flex space-x-6">
                        <button id="nav-resume" class="nav-btn px-4 py-2 text-blue-600 border-b-2 border-blue-600 font-medium" onclick="showPage('resume')">
                            📄 简历管理
                        </button>
                        <button id="nav-job-analysis" class="nav-btn px-4 py-2 text-gray-600 hover:text-blue-600 font-medium" onclick="showPage('job-analysis')">
                            🔍 岗位分析
                        </button>
                    </nav>
                    <div class="flex items-center">
                        <div id="status-dot" class="w-2 h-2 rounded-full bg-red-500 mr-2"></div>
                        <span id="status-text" class="text-xs text-gray-500">未连接</span>
                    </div>
                </div>
            </div>
        </div>
    </header>

    <!-- 主内容 -->
    <main class="max-w-7xl mx-auto px-4 py-8">
        
        <!-- 简历管理页面 -->
        <div id="resume-page" class="page-content active">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <!-- 左侧：简历上传 -->
                <div class="space-y-6">
                    <div class="card">
                        <h2 class="text-2xl font-bold text-gray-900 mb-6">📄 简历上传与分析</h2>
                        
                        <!-- 简历上传区域 -->
                        <div id="upload-section">
                            <div id="upload-area" class="upload-area p-8 rounded-2xl text-center">
                                <div class="mb-4">
                                    <div class="w-16 h-16 bg-blue-100 rounded-full mx-auto mb-4 flex items-center justify-center">
                                        <span class="text-3xl">📤</span>
                                    </div>
                                    <h3 class="text-lg font-semibold text-gray-900 mb-2">上传简历文件</h3>
                                    <p class="text-sm text-gray-600 mb-4">支持 PDF、DOCX、TXT 格式，最大 10MB</p>
                                </div>
                                
                                <div class="space-y-4">
                                    <input type="file" id="resume-file-input" accept=".pdf,.docx,.txt" class="hidden">
                                    <button onclick="document.getElementById('resume-file-input').click()" class="btn btn-primary">
                                        选择文件
                                    </button>
                                    <p class="text-xs text-gray-500">或拖拽文件到此区域</p>
                                </div>
                            </div>
                            
                            <!-- 上传进度 -->
                            <div id="upload-progress" class="mt-4" style="display: none;">
                                <div class="flex items-center justify-between mb-2">
                                    <span class="text-sm font-medium text-gray-700">正在分析简历...</span>
                                    <span id="upload-percentage" class="text-sm text-gray-500">0%</span>
                                </div>
                                <div class="w-full bg-gray-200 rounded-full h-2">
                                    <div id="upload-bar" class="bg-blue-600 h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 简历状态卡片 -->
                    <div class="card">
                        <h3 class="text-lg font-semibold text-gray-900 mb-4">📋 简历状态</h3>
                        <div id="resume-status">
                            <div class="text-center py-6">
                                <div class="text-4xl mb-2">📄</div>
                                <p class="text-sm text-gray-600">未上传简历</p>
                                <p class="text-xs text-gray-500 mt-1">请先上传简历文件</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 右侧：AI分析结果 -->
                <div class="space-y-6">
                    <div class="card">
                        <h3 class="text-xl font-bold text-gray-900 mb-6">🤖 AI分析结果</h3>
                        
                        <!-- 等待分析状态 -->
                        <div id="analysis-empty" class="text-center py-12">
                            <div class="text-6xl mb-4">🤖</div>
                            <h3 class="text-lg font-medium text-gray-900 mb-2">等待简历分析</h3>
                            <p class="text-gray-600">上传简历后，AI将为您提供详细的分析报告</p>
                        </div>
                        
                        <!-- AI分析结果显示 -->
                        <div id="analysis-result" class="space-y-6" style="display: none;">
                            <div class="p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl border">
                                <h4 class="font-bold text-gray-900 mb-2">📊 竞争力评估</h4>
                                <div id="competitiveness-score" class="text-2xl font-bold text-blue-600">0/10</div>
                                <p id="competitiveness-desc" class="text-sm text-gray-600 mt-1">正在分析...</p>
                            </div>
                            
                            <div class="space-y-4">
                                <h4 class="font-bold text-gray-900">🎯 推荐岗位类型</h4>
                                <div id="recommended-jobs" class="space-y-2"></div>
                            </div>
                            
                            <div class="space-y-4">
                                <h4 class="font-bold text-gray-900">💡 提升建议</h4>
                                <div id="improvement-suggestions" class="space-y-2"></div>
                            </div>
                            
                            <div class="space-y-4">
                                <h4 class="font-bold text-gray-900">📈 市场匹配度</h4>
                                <div id="market-analysis" class="text-sm text-gray-700"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 岗位分析页面 -->
        <div id="job-analysis-page" class="page-content">
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <!-- 左侧：搜索配置 -->
                <div class="lg:col-span-1 space-y-6">
                    <!-- 搜索配置 -->
                    <div class="card">
                        <h2 class="text-xl font-semibold text-gray-900 mb-6">🔍 搜索配置</h2>
                        
                        <div class="space-y-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">搜索关键词</label>
                                <input type="text" id="keyword" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="如：市场风险管理、数据分析、AI工程师" value="">
                            </div>
                            
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">🌍 目标城市</label>
                                <select id="city" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500">
                                    <option value="">请选择城市</option>
                                    <option value="shanghai">上海</option>
                                    <option value="beijing">北京</option>
                                    <option value="shenzhen">深圳</option>
                                    <option value="hangzhou">杭州</option>
                                </select>
                            </div>
                            
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">搜索数量</label>
                                    <input type="number" id="max_jobs" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="20" min="1" max="100">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">分析数量</label>
                                    <input type="number" id="max_analyze_jobs" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="10" min="1" max="50">
                                </div>
                            </div>
                            
                            <button id="start-search-btn" class="btn btn-primary w-full">
                                开始搜索
                            </button>
                        </div>
                    </div>

                    <!-- 进度卡片 -->
                    <div class="card">
                        <h3 class="text-lg font-semibold text-gray-900 mb-4">任务进度</h3>
                        <div id="progress-container">
                            <div id="progress-bar" class="w-full h-2 bg-gray-200 rounded-full mb-4" style="display: none;">
                                <div id="progress-fill" class="h-full bg-blue-600 rounded-full transition-all duration-500" style="width: 0%"></div>
                            </div>
                            <div id="progress-message" class="text-sm text-gray-600">等待开始搜索...</div>
                            <div id="progress-logs" class="mt-4 max-h-48 overflow-y-auto space-y-2"></div>
                        </div>
                    </div>
                </div>

                <!-- 右侧：结果展示 -->
                <div class="lg:col-span-2">
                    <div id="results-container" class="space-y-6">
                        <!-- 统计信息 -->
                        <div id="stats-card" class="card" style="display: none;">
                            <h3 class="text-lg font-semibold text-gray-900 mb-4">统计信息</h3>
                            <div class="grid grid-cols-2 gap-4">
                                <div class="text-center cursor-pointer hover:bg-gray-50 rounded-lg p-3 transition-colors" onclick="showAllJobs()">
                                    <div id="total-jobs" class="text-2xl font-bold text-blue-600">0</div>
                                    <div class="text-sm text-gray-600">总搜索数</div>
                                    <div class="text-xs text-gray-400 mt-1">点击查看所有</div>
                                </div>
                                <div class="text-center cursor-pointer hover:bg-gray-50 rounded-lg p-3 transition-colors" onclick="showQualifiedJobs()">
                                    <div id="qualified-jobs" class="text-2xl font-bold text-purple-600">0</div>
                                    <div class="text-sm text-gray-600">合格岗位</div>
                                    <div class="text-xs text-gray-400 mt-1">点击查看推荐</div>
                                </div>
                            </div>
                        </div>

                        <!-- 岗位列表 -->
                        <div id="jobs-list"></div>
                        
                        <!-- 空状态 -->
                        <div id="empty-state" class="card text-center py-12">
                            <div class="w-16 h-16 bg-gray-100 rounded-full mx-auto mb-4 flex items-center justify-center">
                                <span class="text-2xl">🔍</span>
                        </div>
                        <h3 class="text-lg font-medium text-gray-900 mb-2">等待搜索结果</h3>
                        <p class="text-gray-600 mb-6">配置搜索参数并点击"开始搜索"来查找合适的岗位</p>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <script>
    // 等待DOM加载完成
    document.addEventListener('DOMContentLoaded', function() {
        console.log('🚀 DOM加载完成，初始化系统...');
        
        // ========== 初始化核心变量 ==========
        console.log('🔌 初始化Socket.IO连接...');
        const socket = io();
        
        let isSearching = false;
        let allJobs = [];
        let qualifiedJobs = [];
        let currentView = 'qualified';
        
        // ========== 初始化所有DOM元素 ==========
        console.log('📋 初始化DOM元素...');
        
        // WebSocket状态元素
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        
        // 简历上传相关元素
        const resumeFileInput = document.getElementById('resume-file-input');
        const uploadArea = document.getElementById('upload-area');
        const uploadProgress = document.getElementById('upload-progress');
        const uploadBar = document.getElementById('upload-bar');
        const uploadPercentage = document.getElementById('upload-percentage');
        const analysisEmpty = document.getElementById('analysis-empty');
        const analysisResult = document.getElementById('analysis-result');
        
        // 岗位搜索相关元素
        const startBtn = document.getElementById('start-search-btn');
        const progressBar = document.getElementById('progress-bar');
        const progressFill = document.getElementById('progress-fill');
        const progressMessage = document.getElementById('progress-message');
        const progressLogs = document.getElementById('progress-logs');
        const statsCard = document.getElementById('stats-card');
        const jobsList = document.getElementById('jobs-list');
        const emptyState = document.getElementById('empty-state');
        
        // ========== 页面切换功能 ==========
        window.showPage = function(pageId) {
            console.log('🔄 切换到页面:', pageId);
            
            // 隐藏所有页面
            document.querySelectorAll('.page-content').forEach(page => {
                page.classList.remove('active');
            });
            
            // 显示目标页面
            const targetPage = document.getElementById(pageId + '-page');
            if (targetPage) {
                targetPage.classList.add('active');
                console.log('✅ 页面已显示:', pageId);
            } else {
                console.error('❌ 页面不存在:', pageId);
            }
            
            // 更新导航按钮状态
            document.querySelectorAll('.nav-btn').forEach(btn => {
                btn.classList.remove('text-blue-600', 'border-b-2', 'border-blue-600');
                btn.classList.add('text-gray-600');
            });
            
            const activeBtn = document.getElementById('nav-' + pageId);
            if (activeBtn) {
                activeBtn.classList.remove('text-gray-600');
                activeBtn.classList.add('text-blue-600', 'border-b-2', 'border-blue-600');
            }
        };
        
        // ========== WebSocket连接处理 ==========
        socket.on('connect', () => {
            console.log('✅ WebSocket已连接, ID:', socket.id);
            if (statusDot) {
                statusDot.className = 'w-2 h-2 rounded-full bg-green-500 mr-2';
            }
            if (statusText) {
                statusText.textContent = '已连接';
            }
        });
        
        socket.on('disconnect', () => {
            console.log('❌ WebSocket断开连接');
            if (statusDot) {
                statusDot.className = 'w-2 h-2 rounded-full bg-red-500 mr-2';
            }
            if (statusText) {
                statusText.textContent = '未连接';
            }
        });
        
        socket.on('connect_error', (error) => {
            console.error('❌ WebSocket连接错误:', error.message);
        });
        
        socket.on('progress_update', (data) => {
            updateProgress(data);
        });
        
        socket.on('search_complete', (data) => {
            console.log('🎉 搜索完成');
            isSearching = false;
            if (startBtn) {
                startBtn.textContent = '开始搜索';
                startBtn.disabled = false;
            }
        });
        
        // ========== 文件上传功能 ==========
        // 注意：文件上传事件监听器已在后面的代码中设置，避免重复绑定
        
        if (uploadArea) {
            // 拖拽上传
            uploadArea.addEventListener('dragover', function(e) {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', function(e) {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', function(e) {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    uploadResume(files[0]);
                }
            });
        }
        
        // 上传简历函数在后面定义
        
        // 更新上传进度
        function updateUploadProgress(percentage) {
            if (uploadBar) uploadBar.style.width = percentage + '%';
            if (uploadPercentage) uploadPercentage.textContent = Math.round(percentage) + '%';
        }
        
        
        // 显示AI分析结果
        function displayAIAnalysis(aiAnalysis) {
            console.log('🤖 显示AI分析结果:', aiAnalysis);
            if (analysisEmpty) analysisEmpty.style.display = 'none';
            if (analysisResult) analysisResult.style.display = 'block';
            
            // 更新竞争力评分
            const scoreEl = document.getElementById('competitiveness-score');
            if (scoreEl) scoreEl.textContent = (aiAnalysis.competitiveness_score || 0) + '/10';
            
            const descEl = document.getElementById('competitiveness-desc');
            if (descEl) descEl.textContent = aiAnalysis.competitiveness_desc || '分析中...';
            
            // 更新推荐岗位
            const recommendedJobsDiv = document.getElementById('recommended-jobs');
            if (recommendedJobsDiv && aiAnalysis.recommended_jobs && aiAnalysis.recommended_jobs.length > 0) {
                recommendedJobsDiv.innerHTML = aiAnalysis.recommended_jobs.map(job => 
                    `<div class="px-3 py-2 bg-green-50 text-green-700 rounded-lg text-sm">• ${job}</div>`
                ).join('');
            }
            
            // 更新提升建议
            const suggestionsDiv = document.getElementById('improvement-suggestions');
            if (suggestionsDiv && aiAnalysis.improvement_suggestions && aiAnalysis.improvement_suggestions.length > 0) {
                suggestionsDiv.innerHTML = aiAnalysis.improvement_suggestions.map(suggestion => 
                    `<div class="px-3 py-2 bg-yellow-50 text-yellow-700 rounded-lg text-sm">• ${suggestion}</div>`
                ).join('');
            }
            
            // 更新市场分析
            const marketAnalysisDiv = document.getElementById('market-analysis');
            if (marketAnalysisDiv && aiAnalysis.market_position) {
                marketAnalysisDiv.textContent = aiAnalysis.market_position;
            }
            
            // 存储AI原始输出（保留用于调试）
            window.resumeAIOutput = aiAnalysis.full_output || '';
        }
        
        // 重置上传区域
        function resetUploadArea() {
            if (uploadProgress) uploadProgress.style.display = 'none';
            if (uploadArea) uploadArea.style.display = 'block';
            if (analysisResult) analysisResult.style.display = 'none';
            if (analysisEmpty) analysisEmpty.style.display = 'block';
        }
        
        // 更新简历状态（简历管理页）
        function updateResumeStatus(resumeData) {
            const resumeStatusEl = document.getElementById('resume-status');
            const searchSection = document.getElementById('search-section');
            
            if (resumeStatusEl && resumeData) {
                resumeStatusEl.innerHTML = `
                    <div class="flex items-center justify-between p-4 bg-green-50 border border-green-200 rounded-lg">
                        <div class="flex items-center space-x-3">
                            <div class="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                                <span class="text-green-600 text-sm font-bold">${resumeData.name ? resumeData.name.charAt(0) : '✓'}</span>
                            </div>
                            <div>
                                <div class="text-sm font-medium text-green-900">简历已成功上传</div>
                                <div class="text-xs text-green-600">${resumeData.name || '可以开始岗位分析了'}</div>
                            </div>
                        </div>
                        <button onclick="window.deleteResume()" class="text-red-600 hover:text-red-700 text-sm font-medium">
                            删除简历
                        </button>
                    </div>
                `;
                // 启用岗位分析页面的搜索功能
                if (searchSection) searchSection.style.display = 'block';
            }
        }
        
        // 重置简历状态（简历管理页）
        function resetResumeStatus() {
            const resumeStatusEl = document.getElementById('resume-status');
            const searchSection = document.getElementById('search-section');
            
            if (resumeStatusEl) {
                resumeStatusEl.innerHTML = `
                    <div class="text-center py-6">
                        <div class="text-4xl mb-2">📄</div>
                        <p class="text-sm text-gray-600">未上传简历</p>
                        <p class="text-xs text-gray-500 mt-1">请先上传简历文件</p>
                    </div>
                `;
            }
            if (searchSection) searchSection.style.display = 'none';
        }
        
        // ========== 全局函数导出 ==========
        window.showAIDetails = function(type, output) {
            console.log('👁️ 显示AI详情:', type);
            const modal = document.getElementById('ai-details-modal');
            const title = document.getElementById('ai-details-title');
            const content = document.getElementById('ai-details-content');
            
            if (modal && title && content) {
                switch (type) {
                    case 'resume':
                        title.textContent = '简历AI分析完整输出';
                        content.textContent = window.resumeAIOutput || '暂无AI输出记录';
                        break;
                    case 'job':
                        title.textContent = '岗位匹配AI分析输出';
                        content.textContent = output || '暂无AI输出记录';
                        break;
                    default:
                        title.textContent = 'AI分析输出';
                        content.textContent = output || '暂无AI输出记录';
                }
                modal.classList.remove('hidden');
            }
        };
        
        window.hideAIDetails = function() {
            const modal = document.getElementById('ai-details-modal');
            if (modal) modal.classList.add('hidden');
        };
        
        window.deleteResume = async function() {
            if (!confirm('确定要删除当前简历吗？此操作无法撤销。')) {
                return;
            }
            
            try {
                const response = await axios.post('/api/delete_resume');
                if (response.data.success) {
                    resetUploadArea();
                    resetResumeStatus();
                    console.log('🗑️ 简历已删除');
                } else {
                    alert('删除失败: ' + response.data.error);
                }
            } catch (error) {
                console.error('❌ 删除失败:', error);
                alert('删除失败: ' + (error.response?.data?.error || error.message));
            }
        };
        
        window.showAllJobs = function() {
            console.log('📋 显示所有岗位');
            currentView = 'all';
            if (allJobs && allJobs.length > 0) {
                renderJobsList(allJobs);
            } else {
                fetchAllJobs();
            }
        };
        
        window.showQualifiedJobs = function() {
            console.log('⭐ 显示合格岗位');
            currentView = 'qualified';
            renderJobsList(qualifiedJobs);
        };
        
        // ========== 岗位搜索功能 ==========
        if (startBtn) {
            startBtn.addEventListener('click', async () => {
                if (isSearching) return;
                
                const keyword = document.getElementById('keyword').value.trim();
                const city = document.getElementById('city').value;
                
                if (!keyword) {
                    alert('请输入搜索关键词');
                    return;
                }
                if (!city) {
                    alert('请选择目标城市');
                    return;
                }
                
                isSearching = true;
                startBtn.textContent = '搜索中...';
                startBtn.disabled = true;
                
                console.log('🔍 开始搜索:', { keyword, city });
                
                try {
                    const response = await axios.post('/api/jobs/search', {
                        keyword,
                        city,
                        max_jobs: parseInt(document.getElementById('max_jobs').value) || 20,
                        max_analyze_jobs: parseInt(document.getElementById('max_analyze_jobs').value) || 10,
                        spider_engine: 'playwright_mcp',
                        fetch_details: true
                    });
                    
                    console.log('✅ 搜索任务已启动:', response.data);
                } catch (error) {
                    console.error('❌ 启动搜索失败:', error);
                    alert('启动搜索失败: ' + (error.response?.data?.error || error.message));
                    isSearching = false;
                    startBtn.textContent = '开始搜索';
                    startBtn.disabled = false;
                }
            });
        }
        
        // 更新进度
        function updateProgress(data) {
            if (progressMessage) progressMessage.textContent = data.message;
            
            if (data.progress !== undefined && progressBar && progressFill) {
                progressBar.style.display = 'block';
                progressFill.style.width = data.progress + '%';
            }
            
            // 添加日志
            if (progressLogs) {
                const logItem = document.createElement('div');
                logItem.className = 'flex items-start text-sm';
                logItem.innerHTML = `
                    <div class="w-1.5 h-1.5 bg-gray-400 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                    <div class="flex-1">
                        <span class="text-gray-600">${data.message}</span>
                        <span class="text-xs text-gray-400 ml-2">${data.timestamp}</span>
                    </div>
                `;
                progressLogs.appendChild(logItem);
                progressLogs.scrollTop = progressLogs.scrollHeight;
            }
            
            // 处理结果数据
            if (data.data && data.data.results) {
                displayResults(data.data.results, data.data.stats);
                if (data.data.all_jobs) {
                    allJobs = data.data.all_jobs;
                }
            }
        }
        
        // 显示结果
        function displayResults(results, stats) {
            console.log('📊 显示结果:', { results: results?.length, stats });
            
            if (stats) {
                const totalEl = document.getElementById('total-jobs');
                const qualifiedEl = document.getElementById('qualified-jobs');
                if (totalEl) totalEl.textContent = stats.total;
                if (qualifiedEl) qualifiedEl.textContent = stats.qualified;
                if (statsCard) statsCard.style.display = 'block';
            }
            
            if (results && results.length > 0) {
                if (emptyState) emptyState.style.display = 'none';
                qualifiedJobs = results;
                renderJobsList(results);
            }
        }
        
        // 渲染岗位列表
        function renderJobsList(jobs) {
            console.log('🎨 渲染岗位列表:', jobs.length);
            if (!jobsList) return;
            
            jobsList.innerHTML = '';
            
            jobs.forEach((job, index) => {
                const jobCard = createJobCard(job, index + 1);
                if (jobCard) {
                    jobsList.appendChild(jobCard);
                }
            });
        }
        
        // 创建岗位卡片
        function createJobCard(job, index) {
            const div = document.createElement('div');
            div.className = 'card relative';
            
            const analysis = job.analysis || {};
            const score = analysis.score || analysis.overall_score || 0;
            const isAnalyzed = analysis.recommendation !== '未分析';
            
            const getScoreColor = (score, isAnalyzed) => {
                if (!isAnalyzed) return 'text-gray-500 bg-gray-100';
                if (score >= 8) return 'text-green-600 bg-green-100';
                if (score >= 6) return 'text-yellow-600 bg-yellow-100';
                return 'text-red-600 bg-red-100';
            };
            
            div.innerHTML = `
                <div class="absolute top-4 right-4">
                    <div class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getScoreColor(score, isAnalyzed)}">
                        ${isAnalyzed ? `⭐ ${score}/10` : '⏩️ 未分析'}
                    </div>
                </div>
                <div class="pr-20 mb-4">
                    <h3 class="text-lg font-semibold text-gray-900 mb-2">${job.title || '未知岗位'}</h3>
                    <div class="text-gray-600 mb-2">🏢 ${job.company || '未知公司'} • 💰 ${job.salary || '薪资面议'}</div>
                    <div class="text-gray-600 mb-2">📍 ${job.work_location || '未知地点'}</div>
                </div>
            `;
            
            // 添加智能匹配分析展示
            if (isAnalyzed && analysis.dimension_scores) {
                const analysisDiv = document.createElement('div');
                analysisDiv.className = 'mt-4 p-4 bg-gray-50 rounded-lg';
                analysisDiv.innerHTML = `
                    <div class="text-sm font-medium text-gray-900 mb-3">📊 智能匹配分析</div>
                    <div class="grid grid-cols-2 gap-2 text-xs">
                        <div class="flex justify-between items-center py-1">
                            <span class="text-gray-600">岗位匹配</span>
                            <span class="font-medium">${analysis.dimension_scores.job_match || 0}/10</span>
                        </div>
                        <div class="flex justify-between items-center py-1">
                            <span class="text-gray-600">技能匹配</span>
                            <span class="font-medium">${analysis.dimension_scores.skill_match || 0}/10</span>
                        </div>
                    </div>
                `;
                div.appendChild(analysisDiv);
            }
            
            return div;
        }
        
        // 获取所有岗位
        async function fetchAllJobs() {
            try {
                const response = await axios.get('/api/jobs/all');
                if (response.data && response.data.jobs) {
                    allJobs = response.data.jobs;
                    if (currentView === 'all') {
                        renderJobsList(allJobs);
                    }
                }
            } catch (error) {
                console.error('❌ 获取所有岗位失败:', error);
                alert('获取数据失败: ' + error.message);
            }
        }
        
        // ========== 初始化完成 ==========
        console.log('✅ 系统初始化完成！');
        console.log('📊 初始化状态:', {
            socket: socket.connected ? '已连接' : '未连接',
            resumeFileInput: resumeFileInput ? '已找到' : '未找到',
            uploadArea: uploadArea ? '已找到' : '未找到',
            startBtn: startBtn ? '已找到' : '未找到'
        });
        
        
        // ========== 简历上传功能 ==========
        console.log('📎 设置简历上传功能...');
        
        // 文件上传事件
        if (resumeFileInput) {
            resumeFileInput.addEventListener('change', function(e) {
                if (e.target.files.length > 0) {
                    uploadResume(e.target.files[0]);
                }
            });
        }
        
        // 拖拽上传支持
        if (uploadArea) {
            uploadArea.addEventListener('dragover', function(e) {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', function(e) {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', function(e) {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    const file = files[0];
                    if (file.type === 'application/pdf' || 
                        file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
                        file.type === 'text/plain') {
                        uploadResume(file);
                    } else {
                        alert('请上传PDF、DOCX或TXT格式的文件');
                    }
                }
            });
        }
        
        // 上传简历函数
        async function uploadResume(file) {
            console.log('📤 开始上传简历:', file.name);
            
            // 显示上传进度
            if (uploadProgress) uploadProgress.style.display = 'block';
            if (uploadArea) uploadArea.style.display = 'none';
            
            const formData = new FormData();
            formData.append('resume', file);
            
            try {
                // 模拟上传进度
                let progress = 0;
                const progressInterval = setInterval(() => {
                    progress += Math.random() * 15;
                    if (progress >= 90) {
                        clearInterval(progressInterval);
                        progress = 90;
                    }
                    updateUploadProgress(progress);
                }, 200);
                
                // 发送到后端
                const response = await axios.post('/api/upload_resume', formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    }
                });
                
                clearInterval(progressInterval);
                updateUploadProgress(100);
                
                setTimeout(() => {
                    if (response.data.success) {
                        // 隐藏上传进度，显示分析结果
                        if (uploadProgress) uploadProgress.style.display = 'none';
                        
                        if (response.data.ai_analysis) {
                            displayAIAnalysis(response.data.ai_analysis);
                        }
                        
                        // 更新简历状态
                        updateResumeStatus(response.data.resume_data);
                        
                        console.log('✅ 简历上传成功:', response.data.resume_data.name);
                    } else {
                        alert('简历上传失败: ' + response.data.error);
                        resetUploadArea();
                    }
                }, 500);
                
            } catch (error) {
                console.error('❌ 上传失败:', error);
                alert('上传失败: ' + (error.response?.data?.error || error.message));
                resetUploadArea();
            }
        }
        
    }); // DOMContentLoaded结束
</script>
</body>
</html>
    '''


@app.route('/api/health')
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    try:
        if not config_manager:
            return jsonify({'error': '配置管理器未初始化'}), 500
        
        search_config = config_manager.get_search_config()
        ai_config = config_manager.get_ai_config()
        
        # 移除敏感信息
        ai_config.pop('api_key', None)
        
        return jsonify({
            'search': search_config,
            'ai': ai_config,
            'app': config_manager.get_app_config()
        })
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['POST'])
def update_config():
    """更新用户配置"""
    try:
        if not config_manager:
            return jsonify({'error': '配置管理器未初始化'}), 500
        
        data = request.get_json()
        
        # 更新搜索配置
        if 'search' in data:
            for key, value in data['search'].items():
                config_manager.set_user_preference(f'search.{key}', value)
        
        # 更新AI配置
        if 'ai_analysis' in data:
            for key, value in data['ai_analysis'].items():
                config_manager.set_user_preference(f'ai_analysis.{key}', value)
        
        # 保存配置
        config_manager.save_user_preferences()
        
        return jsonify({'message': '配置更新成功'})
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload_resume', methods=['POST'])
def upload_resume():
    """处理简历上传和分析"""
    try:
        if 'resume' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'})
        
        file = request.files['resume']
        if file.filename == '':
            return jsonify({'success': False, 'error': '未选择文件'})
        
        logger.info(f"接收到文件: {file.filename}, 类型: {file.content_type}")
        
        # 使用新的解析器
        from analyzer.resume.resume_parser_v2 import ResumeParserV2
        from analyzer.resume.resume_analyzer_v2 import ResumeAnalyzerV2
        
        parser = ResumeParserV2()
        
        # 解析简历文本（直接从内存解析，不保存文件）
        resume_text = parser.parse_uploaded_file(file)
        
        if "文件解析失败" in resume_text:
            logger.error(f"文件解析错误: {resume_text}")
            return jsonify({
                'success': False, 
                'error': resume_text
            })
        
        logger.info(f"简历解析成功，文本长度: {len(resume_text)} 字符")
        
        # AI分析简历
        analyzer = ResumeAnalyzerV2()
        ai_analysis = analyzer.analyze_resume(resume_text)
        
        # 从AI分析结果中提取基本信息用于显示
        # 简化处理，直接使用AI分析的结果
        resume_data = {
            'name': '陈俊旭', # 临时硬编码，后续可从简历文本中简单提取
            'current_position': '待AI分析',
            'experience_years': '待AI分析',
            'phone': '已脱敏',
            'email': '已脱敏', 
            'technical_skills': [],
            'education': '待AI分析',
            'filename': file.filename,
            'upload_time': datetime.now().isoformat()
        }
        
        # 存储到session（避免存储大文本）
        session['resume_data'] = resume_data
        # 只存储摘要信息，不存储完整文本
        session['resume_summary'] = {
            'length': len(resume_text),
            'has_text': True,
            'analyzed': True
        }
        # 只存储关键分析结果，避免session过大
        session['ai_analysis_summary'] = {
            'competitiveness_score': ai_analysis.get('competitiveness_score', 0),
            'recommended_jobs': ai_analysis.get('recommended_jobs', []),
            'analyzed_at': datetime.now().isoformat()
        }
        
        # 更新全局分析器
        from analyzer.job_analyzer import JobAnalyzer
        global job_analyzer_instance
        if 'job_analyzer_instance' not in globals():
            job_analyzer_instance = JobAnalyzer()
        job_analyzer_instance.set_resume_analysis(ai_analysis)
        
        logger.info(f"简历分析完成: {resume_data['name']}, 竞争力评分: {ai_analysis.get('competitiveness_score')}/10")
        
        return jsonify({
            'success': True,
            'resume_data': resume_data,
            'ai_analysis': ai_analysis
        })
        
    except Exception as e:
        logger.error(f"简历上传处理失败: {e}", exc_info=True)
        return jsonify({
            'success': False, 
            'error': f"处理失败: {str(e)}"
        })

@app.route('/api/delete_resume', methods=['POST'])
def delete_resume():
    try:
        # 清除session中的简历数据
        session.pop('resume_data', None)
        session.pop('ai_analysis', None)
        
        # 清除JobAnalyzer中的简历分析
        global job_analyzer_instance
        if 'job_analyzer_instance' in globals():
            job_analyzer_instance.resume_analysis = None
        
        # 这里可以添加删除文件的逻辑
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"删除简历失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/jobs/search', methods=['POST'])
def start_job_search():
    """开始岗位搜索和分析"""
    global current_job, current_spider
    
    try:
        if current_job and current_job.get('status') == 'running':
            return jsonify({'error': '已有任务正在运行中'}), 400
        
        # 获取请求参数
        data = request.get_json() or {}
        
        # 启动后台任务
        current_job = {'status': 'starting', 'start_time': datetime.now()}
        
        # 在新线程中执行搜索任务
        thread = threading.Thread(target=run_job_search_task, args=(data,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': '任务已启动',
            'task_id': current_job.get('task_id', 'default')
        })
        
    except Exception as e:
        logger.error(f"启动搜索任务失败: {e}")
        return jsonify({'error': str(e)}), 500


def run_job_search_task(params):
    """在后台运行岗位搜索任务"""
    global current_job, current_spider
    
    try:
        current_job['status'] = 'running'
        emit_progress("🚀 开始初始化爬虫...", 5)
        
        # 1. 从前端参数获取搜索配置，如果没有则使用默认配置
        search_config = config_manager.get_search_config()
        ai_config = config_manager.get_ai_config()
        
        # 使用前端传来的参数覆盖配置文件中的值
        keyword = params.get('keyword', search_config['keyword'])
        max_jobs = params.get('max_jobs', search_config['max_jobs'])
        max_analyze_jobs = params.get('max_analyze_jobs', search_config['max_analyze_jobs'])
        spider_engine = params.get('spider_engine', 'playwright_mcp')  # 默认Playwright MCP
        fetch_details = params.get('fetch_details', True)  # 默认获取详情
        selected_city = params.get('city', 'shanghai')  # 默认上海
        
        # 获取城市代码
        city_codes = search_config['city_codes']
        city_code = city_codes.get(selected_city, {}).get('code', '101210100')
        city_name = city_codes.get(selected_city, {}).get('name', '上海')
        
        emit_progress(f"🔍 搜索设置: {keyword} | {city_name} | {max_jobs}个岗位", 10)
        emit_progress(f"🎭 使用爬虫引擎: {spider_engine.upper()}", 15)
        
        # 2. 根据选择的引擎初始化爬虫
        if spider_engine == 'playwright_mcp':
            emit_progress("🎭 启动Playwright MCP引擎...", 20)
            # 使用Playwright MCP进行搜索
            jobs = search_with_playwright_mcp(keyword, city_code, max_jobs, fetch_details)
        else:
            emit_progress("🤖 启动Selenium引擎...", 20)
            # 使用传统Selenium方式
            current_spider = BossSpider()
            if not current_spider.start():
                raise Exception("Selenium爬虫启动失败")
            
            emit_progress("🔐 等待用户登录...", 25)
            if not current_spider.login_with_manual_help():
                raise Exception("登录失败")
            
            emit_progress("✅ 登录成功，开始搜索岗位...", 30)
            jobs = current_spider.search_jobs(keyword, city_code, max_jobs, fetch_details)
            
            # 为Selenium获取的岗位添加引擎来源标识
            for job in jobs:
                job['engine_source'] = 'Selenium'
        
        emit_progress(f"🔍 搜索完成: 找到 {len(jobs)} 个岗位", 50)
        
        if not jobs:
            raise Exception("未找到任何岗位")
        
        emit_progress(f"📊 找到 {len(jobs)} 个岗位，开始AI分析...", 50)
        
        # 5. AI分析
        global job_analyzer_instance
        if 'job_analyzer_instance' not in globals():
            job_analyzer_instance = JobAnalyzer(ai_config['provider'])
        else:
            # 如果已有实例，检查是否有简历分析数据
            if hasattr(job_analyzer_instance, 'resume_analysis') and job_analyzer_instance.resume_analysis:
                print("🎯 使用已加载的简历数据进行智能匹配")
        
        analyzer = job_analyzer_instance
        jobs_to_analyze = jobs[:max_analyze_jobs]  # 只分析前几个
        
        # 为所有岗位初始化分析结果
        all_jobs_with_analysis = []
        
        # 先分析前max_analyze_jobs个岗位
        for i, job in enumerate(jobs):
            if i < max_analyze_jobs:
                # 分析前几个岗位
                progress = 50 + (i / max_analyze_jobs) * 30
                emit_progress(f"🤖 分析第 {i+1}/{max_analyze_jobs} 个岗位...", progress)
                
                try:
                    analysis_result = analyzer.ai_client.analyze_job_match(
                        job, analyzer.user_requirements
                    )
                    job['analysis'] = analysis_result
                except Exception as e:
                    logger.error(f"分析岗位失败: {e}")
                    job['analysis'] = {
                        "score": 0,
                        "recommendation": "分析失败",
                        "reason": f"分析过程中出错: {e}",
                        "summary": "无法分析此岗位"
                    }
            else:
                # 未分析的岗位给予默认分析结果
                job['analysis'] = {
                    "score": 0,
                    "recommendation": "未分析",
                    "reason": "超出分析数量限制，未进行AI分析",
                    "summary": "该岗位未进行详细分析"
                }
            
            all_jobs_with_analysis.append(job)
        
        # 6. 过滤和排序
        emit_progress("🎯 过滤和排序结果...", 85)
        # 只从分析过的岗位中筛选
        analyzed_jobs = [job for job in all_jobs_with_analysis if job['analysis']['recommendation'] != "未分析"]
        filtered_jobs = analyzer.filter_and_sort_jobs(analyzed_jobs, ai_config['min_score'])
        
        # 7. 保存结果
        emit_progress("💾 保存结果...", 95)
        # 使用新的保存函数，保存所有岗位
        from utils.data_saver import save_all_job_results
        save_all_job_results(all_jobs_with_analysis, filtered_jobs)  # 保存所有岗位
        
        # 8. 完成
        current_job.update({
            'status': 'completed',
            'end_time': datetime.now(),
            'results': filtered_jobs,
            'analyzed_jobs': all_jobs_with_analysis,  # 存储所有岗位（包括未分析的）
            'total_jobs': len(jobs),
            'analyzed_jobs_count': len(analyzed_jobs),
            'qualified_jobs': len(filtered_jobs)
        })
        
        emit_progress(f"✅ 任务完成! 找到 {len(filtered_jobs)} 个合适岗位", 100, {
            'results': filtered_jobs,
            'all_jobs': all_jobs_with_analysis,  # 返回所有岗位（包括未分析的）
            'stats': {
                'total': len(all_jobs_with_analysis),  # 总搜索数是所有搜索到的岗位
                'analyzed': len(analyzed_jobs),
                'qualified': len(filtered_jobs)
            }
        })
        
    except Exception as e:
        logger.error(f"搜索任务失败: {e}")
        current_job.update({
            'status': 'failed',
            'error': str(e),
            'end_time': datetime.now()
        })
        emit_progress(f"❌ 任务失败: {str(e)}", None)
        
    finally:
        # 清理资源
        if current_spider:
            try:
                current_spider.close()
            except:
                pass
            current_spider = None


@app.route('/api/jobs/all')
def get_all_jobs():
    """获取所有搜索到的岗位（未过滤）"""
    try:
        from utils.data_saver import load_all_job_results
        
        # 尝试从保存的文件中读取所有岗位
        job_data = load_all_job_results()
        if job_data and 'all_jobs' in job_data:
            all_jobs = job_data['all_jobs']
            logger.info(f"✅ 从文件加载了 {len(all_jobs)} 个岗位")
            return jsonify({
                'jobs': all_jobs,
                'total': len(all_jobs),
                'metadata': job_data.get('metadata', {})
            })
        
        # 如果文件中没有数据，fallback到current_job
        if current_job and 'analyzed_jobs' in current_job:
            jobs = current_job.get('analyzed_jobs', [])
            logger.info(f"⚠️ 从内存加载了 {len(jobs)} 个岗位")
            return jsonify({
                'jobs': jobs,
                'total': len(jobs)
            })
        
        return jsonify({'error': '没有可用的搜索结果，请先进行搜索'}), 404
        
    except Exception as e:
        logger.error(f"获取所有岗位失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/jobs/results')
def get_job_results():
    """获取最新的岗位搜索结果"""
    try:
        if not current_job:
            return jsonify({'error': '没有可用的搜索结果'}), 404
        
        return jsonify({
            'status': current_job.get('status'),
            'results': current_job.get('results', []),
            'stats': {
                'total_jobs': current_job.get('total_jobs', 0),
                'analyzed_jobs': current_job.get('analyzed_jobs', 0),
                'qualified_jobs': current_job.get('qualified_jobs', 0)
            },
            'start_time': current_job.get('start_time'),
            'end_time': current_job.get('end_time')
        })
        
    except Exception as e:
        logger.error(f"获取结果失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/jobs/status')
def get_job_status():
    """获取当前任务状态"""
    if not current_job:
        return jsonify({'status': 'idle'})
    
    return jsonify({
        'status': current_job.get('status', 'idle'),
        'start_time': current_job.get('start_time'),
        'error': current_job.get('error')
    })


@socketio.on('connect')
def handle_connect():
    """WebSocket连接处理"""
    logger.info('客户端已连接')
    emit('connected', {'message': '连接成功'})


@socketio.on('disconnect')
def handle_disconnect():
    """WebSocket断开连接处理"""
    logger.info('客户端已断开连接')


if __name__ == '__main__':
    # 初始化配置
    if not init_config():
        logger.error("配置初始化失败，退出程序")
        sys.exit(1)
    
    # 启动应用
    logger.info("启动Boss直聘自动化Web应用...")
    socketio.run(app, 
                host='127.0.0.1', 
                port=5000, 
                debug=True,
                use_reloader=False,
                allow_unsafe_werkzeug=True)  # 避免重载时的问题