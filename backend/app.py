#!/usr/bin/env python3
"""
Boss直聘自动化Web应用后端
Flask + SocketIO 实现
"""

import os
import sys
import logging
import threading
from flask import Flask, request, jsonify
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
    <title>Boss直聘 AI助手</title>
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
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- 头部 -->
    <header class="glass border-b border-gray-200 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 py-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center">
                    <div class="w-8 h-8 bg-blue-600 rounded-lg mr-3 flex items-center justify-center">
                        <span class="text-white font-bold">AI</span>
                    </div>
                    <div>
                        <h1 class="text-2xl font-bold text-gray-900">Boss直聘 AI助手</h1>
                        <p class="text-sm text-gray-600">智能化岗位筛选工具</p>
                    </div>
                </div>
                <div class="flex items-center space-x-3">
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
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- 左侧配置面板 -->
            <div class="lg:col-span-1 space-y-6">
                <!-- 配置卡片 -->
                <div class="card">
                    <h2 class="text-xl font-semibold text-gray-900 mb-6">搜索配置</h2>
                    
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

            <!-- 右侧结果展示 -->
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
        // WebSocket连接
        const socket = io();
        let isSearching = false;

        // DOM元素
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        const startBtn = document.getElementById('start-search-btn');
        const progressBar = document.getElementById('progress-bar');
        const progressFill = document.getElementById('progress-fill');
        const progressMessage = document.getElementById('progress-message');
        const progressLogs = document.getElementById('progress-logs');
        const statsCard = document.getElementById('stats-card');
        const jobsList = document.getElementById('jobs-list');
        const emptyState = document.getElementById('empty-state');

        // 存储所有搜索结果 - 全局变量
        let allJobs = [];
        let qualifiedJobs = [];
        let currentView = 'qualified';  // 'all' or 'qualified'

        // WebSocket事件
        socket.on('connect', () => {
            statusDot.className = 'w-2 h-2 rounded-full bg-green-500 mr-2';
            statusText.textContent = '已连接';
        });

        socket.on('disconnect', () => {
            statusDot.className = 'w-2 h-2 rounded-full bg-red-500 mr-2';
            statusText.textContent = '未连接';
        });

        socket.on('progress_update', (data) => {
            updateProgress(data);
            
            // 如果任务完成或失败，重置按钮状态
            if (data.message.includes('完成') || data.message.includes('失败')) {
                isSearching = false;
                startBtn.textContent = '开始搜索';
                startBtn.disabled = false;
            }
        });

        // 更新进度
        function updateProgress(data) {
            progressMessage.textContent = data.message;
            
            if (data.progress !== undefined) {
                progressBar.style.display = 'block';
                progressFill.style.width = data.progress + '%';
            }

            // 添加日志
            const logItem = document.createElement('div');
            logItem.className = 'flex items-start text-sm';
            logItem.innerHTML = `
                <div class="w-1.5 h-1.5 bg-gray-400 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                <div class="flex-1">
                    <span class="text-gray-600">${data.message}</span>
                    <span class="text-xs text-gray-400 ml-2">${data.timestamp}</span>
                </div>
                ${data.progress ? `<div class="text-xs text-gray-500">${data.progress}%</div>` : ''}
            `;
            progressLogs.appendChild(logItem);
            progressLogs.scrollTop = progressLogs.scrollHeight;

            // 如果有结果数据
            if (data.data && data.data.results) {
                displayResults(data.data.results, data.data.stats);
                // 同时存储所有岗位数据
                if (data.data.all_jobs) {
                    allJobs = data.data.all_jobs;
                }
            }
        }

        // 显示结果
        function displayResults(results, stats) {
            // 调试：打印接收到的数据
            console.log('🔍 DisplayResults called with:', { results, stats });
            console.log('📊 Results type:', typeof results, 'Length:', results?.length);
            console.log('📄 All jobs stored:', allJobs.length);
            
            if (stats) {
                document.getElementById('total-jobs').textContent = stats.total;
                document.getElementById('qualified-jobs').textContent = stats.qualified;
                statsCard.style.display = 'block';
                console.log('📈 Stats updated:', stats);
            }

            if (results && results.length > 0) {
                console.log('✅ Showing jobs list, hiding empty state');
                emptyState.style.display = 'none';
                
                // 存储结果用于切换视图
                qualifiedJobs = results;
                // 注意：这里的results已经是过滤后的合格岗位
                // allJobs在updateProgress中已经设置
                
                renderJobsList(results);
            } else {
                console.log('⚠️ No results to display:', { results, length: results?.length });
            }
        }

        // 渲染岗位列表
        function renderJobsList(jobs) {
            console.log('🎨 renderJobsList called with:', jobs.length, 'jobs');
            console.log('🎯 jobsList element:', jobsList);
            console.log('📋 First job sample:', jobs[0]);
            
            if (!jobsList) {
                console.error('❌ jobsList element not found!');
                return;
            }
            
            jobsList.innerHTML = '';
            console.log('🧹 Cleared jobsList innerHTML');
            
            // 统计分析情况
            const analyzedCount = jobs.filter(job => job.analysis?.recommendation !== '未分析').length;
            const unanalyzedCount = jobs.filter(job => job.analysis?.recommendation === '未分析').length;
            console.log('📊 Stats:', { analyzedCount, unanalyzedCount });
            
            // 添加视图标题
            const viewTitle = document.createElement('div');
            viewTitle.className = 'mb-4 text-sm text-gray-600';
            if (currentView === 'all') {
                viewTitle.innerHTML = `
                    <span class="font-medium">显示所有搜索结果 (${jobs.length}个)</span>
                    ${unanalyzedCount > 0 ? `
                        <span class="ml-2 text-xs text-yellow-600">
                            其中 ${analyzedCount} 个已分析，${unanalyzedCount} 个未分析
                        </span>
                    ` : ''}
                `;
            } else {
                viewTitle.innerHTML = `<span class="font-medium">显示AI推荐岗位 (${jobs.length}个)</span>`;
            }
            jobsList.appendChild(viewTitle);
            console.log('📌 Added view title');
            
            jobs.forEach((job, index) => {
                console.log(`🔨 Creating job card ${index + 1}:`, job.title);
                try {
                    const jobCard = createJobCard(job, index + 1);
                    if (jobCard) {
                        jobsList.appendChild(jobCard);
                        console.log(`✅ Added job card ${index + 1}`);
                    } else {
                        console.error(`❌ createJobCard returned null for job ${index + 1}`);
                    }
                } catch (error) {
                    console.error(`❌ Error creating job card ${index + 1}:`, error);
                }
            });
            console.log(`🎉 Completed rendering ${jobs.length} job cards`);
            console.log('📄 Final jobsList HTML length:', jobsList.innerHTML.length);
        }

        // 显示所有岗位
        function showAllJobs() {
            console.log('🔄 showAllJobs called');
            console.log('📊 Current allJobs length:', allJobs ? allJobs.length : 'undefined');
            console.log('📊 Current qualifiedJobs length:', qualifiedJobs ? qualifiedJobs.length : 'undefined');
            console.log('📊 Current view before change:', currentView);
            
            currentView = 'all';
            console.log('📊 Current view after change:', currentView);
            
            if (allJobs && allJobs.length > 0) {
                console.log('📦 Rendering all jobs:', allJobs.length);
                renderJobsList(allJobs);
            } else {
                console.log('🔍 allJobs is empty or undefined, fetching from backend...');
                console.log('🔍 allJobs:', allJobs);
                fetchAllJobs();
            }
        }

        // 显示合格岗位
        function showQualifiedJobs() {
            currentView = 'qualified';
            renderJobsList(qualifiedJobs);
        }

        // 获取所有岗位
        async function fetchAllJobs() {
            try {
                console.log('🌐 Fetching all jobs from /api/jobs/all');
                console.log('🔄 Current location:', window.location.href);
                
                const response = await axios.get('/api/jobs/all');
                console.log('📥 Response received:', response);
                console.log('📊 Response status:', response.status);
                console.log('📄 Response data:', response.data);
                
                if (response.data && response.data.jobs) {
                    allJobs = response.data.jobs;
                    console.log('✅ All jobs loaded:', allJobs.length);
                    console.log('📋 Sample job titles:', allJobs.slice(0, 3).map(job => job.title));
                    
                    if (currentView === 'all') {
                        console.log('🎯 Rendering jobs list for "all" view');
                        renderJobsList(allJobs);
                    } else {
                        console.log('⏭️ Current view is not "all", skipping render');
                    }
                } else {
                    console.error('⚠️ No jobs data in response:', response.data);
                    alert('未找到岗位数据');
                }
            } catch (error) {
                console.error('❌ 获取所有岗位失败:', error);
                console.error('❌ Error details:', {
                    message: error.message,
                    response: error.response,
                    status: error.response?.status,
                    data: error.response?.data
                });
                const errorMsg = error.response ? 
                    `服务器错误(${error.response.status}): ${error.response.data?.error || error.message}` :
                    `网络错误: ${error.message}`;
                alert('获取数据失败: ' + errorMsg);
            }
        }

        // HTML转义函数
        function escapeHtml(text) {
            if (typeof text !== 'string') return text;
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // 创建岗位卡片
        function createJobCard(job, index) {
            console.log(`🔨 createJobCard called for: ${job.title}`);
            const div = document.createElement('div');
            div.className = 'card relative';
            
            const analysis = job.analysis || {};
            const score = analysis.score || 0;
            const isAnalyzed = analysis.recommendation !== '未分析';
            
            const getScoreColor = (score, isAnalyzed) => {
                if (!isAnalyzed) return 'text-gray-500 bg-gray-100';
                if (score >= 8) return 'text-green-600 bg-green-100';
                if (score >= 6) return 'text-yellow-600 bg-yellow-100';
                return 'text-red-600 bg-red-100';
            };

            // 使用安全的方式构建HTML，避免特殊字符问题
            const scoreDiv = document.createElement('div');
            scoreDiv.className = 'absolute top-4 right-4';
            
            const scoreSpan = document.createElement('div');
            scoreSpan.className = `inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getScoreColor(score, isAnalyzed)}`;
            scoreSpan.textContent = isAnalyzed ? `⭐ ${score}/10` : '⏩️ 未分析';
            scoreDiv.appendChild(scoreSpan);
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'pr-20 mb-4';
            
            const title = document.createElement('h3');
            title.className = 'text-lg font-semibold text-gray-900 mb-2';
            title.textContent = job.title || '未知岗位';
            contentDiv.appendChild(title);
            
            const company = document.createElement('div');
            company.className = 'text-gray-600 mb-2';
            company.innerHTML = '🏢 <span></span>';
            company.querySelector('span').textContent = job.company || '未知公司';
            contentDiv.appendChild(company);
            
            const salary = document.createElement('div');
            salary.className = 'text-gray-600 mb-2';
            salary.innerHTML = '💰 <span class="text-green-600 font-medium"></span>';
            salary.querySelector('span').textContent = job.salary || '面议';
            contentDiv.appendChild(salary);
            
            if (job.work_location) {
                const location = document.createElement('div');
                location.className = 'text-gray-600 mb-2';
                location.innerHTML = '📍 <span></span>';
                location.querySelector('span').textContent = job.work_location;
                contentDiv.appendChild(location);
            }
            
            if (job.url) {
                const urlDiv = document.createElement('div');
                urlDiv.className = 'text-gray-600 mb-2';
                urlDiv.innerHTML = '🔗 <a href="" target="_blank" class="text-blue-600 hover:text-blue-800 underline text-xs break-all"></a>';
                const link = urlDiv.querySelector('a');
                link.href = job.url;
                link.textContent = job.url;
                contentDiv.appendChild(urlDiv);
            }
            
            div.appendChild(scoreDiv);
            div.appendChild(contentDiv);
            
            console.log(`✅ Created basic structure for: ${job.title}`);
            return div;
        }

        // 开始搜索
        startBtn.addEventListener('click', async () => {
            if (isSearching) return;

            const keyword = document.getElementById('keyword').value.trim();
            const maxJobsInput = document.getElementById('max_jobs').value;
            const maxAnalyzeJobsInput = document.getElementById('max_analyze_jobs').value;
            const city = document.getElementById('city').value;

            // 表单验证
            if (!keyword) {
                alert('请输入搜索关键词');
                return;
            }
            if (!city) {
                alert('请选择目标城市');
                return;
            }

            // 设置默认值
            const maxJobs = maxJobsInput ? parseInt(maxJobsInput) : 20;
            const maxAnalyzeJobs = maxAnalyzeJobsInput ? parseInt(maxAnalyzeJobsInput) : 10;

            isSearching = true;
            startBtn.textContent = '搜索中...';
            startBtn.disabled = true;
            progressLogs.innerHTML = '';
            jobsList.innerHTML = '';
            emptyState.style.display = 'none';

            console.log('发送的搜索参数:', {
                keyword,
                max_jobs: maxJobs,
                max_analyze_jobs: maxAnalyzeJobs,
                spider_engine: 'playwright_mcp',
                city: city,
                fetch_details: true
            });

            try {
                const response = await axios.post('/api/jobs/search', {
                    keyword,
                    max_jobs: maxJobs,
                    max_analyze_jobs: maxAnalyzeJobs,
                    spider_engine: 'playwright_mcp',  // 使用真正的Playwright MCP
                    city: city,
                    fetch_details: true  // 默认获取详情
                });
                
                console.log('搜索任务已启动:', response.data);
            } catch (error) {
                console.error('启动搜索失败:', error);
                alert('启动搜索失败: ' + (error.response?.data?.error || error.message));
                isSearching = false;
                startBtn.textContent = '开始搜索';
                startBtn.disabled = false;
            }
        });

        // 显示岗位详细信息
        function showJobDetails(index) {
            const detailsDiv = document.getElementById(`job-details-${index}`);
            if (detailsDiv.style.display === 'none') {
                detailsDiv.style.display = 'block';
            } else {
                detailsDiv.style.display = 'none';
            }
        }
        
        // 使函数全局可用
        window.showJobDetails = showJobDetails;
        window.showAllJobs = showAllJobs;
        window.showQualifiedJobs = showQualifiedJobs;

        // 注意：progress_update事件已经在上面监听过了，这里只需要处理按钮状态
        // 在updateProgress函数中处理按钮状态更新
        
        // 调试功能 - 检查数据状态
        window.debugJobData = function() {
            console.log('=== 调试信息 ===');
            console.log('allJobs:', allJobs);
            console.log('allJobs length:', allJobs ? allJobs.length : 'undefined');
            console.log('qualifiedJobs:', qualifiedJobs);
            console.log('qualifiedJobs length:', qualifiedJobs ? qualifiedJobs.length : 'undefined');
            console.log('currentView:', currentView);
            console.log('================');
        };
        
        // 初始化时输出调试信息
        console.log('🚀 页面初始化完成，可以使用 debugJobData() 查看数据状态');
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
        analyzer = JobAnalyzer(ai_config['provider'])
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
                use_reloader=False)  # 避免重载时的问题