// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 DOM加载完成，初始化系统...');
    
    // ========== 工具函数 ==========
    // 清理Markdown格式
    function cleanMarkdown(text) {
        if (!text) return text;
        // 使用简单的字符串替换避免复杂的正则表达式
        return text
            .replace(/\\*\\*([^*]+?)\\*\\*/g, '$1')  // 移除粗体**text**
            .replace(/\\*([^*]+?)\\*/g, '$1')        // 移除斜体*text*
            .replace(/__([^_]+?)__/g, '$1')          // 移除粗体__text__
            .replace(/_([^_]+?)_/g, '$1')            // 移除斜体_text_
            .replace(/`([^`]+?)`/g, '$1')            // 移除代码`text`
            .replace(/#{1,6}\\s+/g, '')              // 移除标题# text
            .trim();
    }

    // ========== 初始化核心变量 ==========
    console.log('🔌 初始化Socket.IO连接...');
    const socket = io();
    
    let isSearching = false;
    let allJobs = [];
    let qualifiedJobs = [];
    let currentView = 'qualified';
    let currentMarketAnalysis = null; // 存储当前市场分析数据
    
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
        
        // 更新简历市场分析
        const resumeMarketAnalysisDiv = document.getElementById('resume-market-analysis');
        if (resumeMarketAnalysisDiv && aiAnalysis.market_position) {
            resumeMarketAnalysisDiv.textContent = aiAnalysis.market_position;
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
    
    // 清理和格式化文本
    window.cleanJobText = function(text) {
        if (!text) return '';
        
        // 首先处理所有类型的空白字符
        // 包括：普通空格、全角空格(　)、不间断空格(&nbsp;)、制表符等
        let cleaned = text
            .replace(/[\u3000\u00A0]/g, ' ')  // 全角空格和不间断空格转为普通空格
            .replace(/&nbsp;/g, ' ')           // HTML实体空格
            .replace(/\t/g, ' ')               // 制表符转为空格
            .trim();
        
        // 移除每行开头的所有空白字符（包括全角空格）
        cleaned = cleaned.replace(/^[\\s\u3000\u00A0\t]+/gm, '');
        
        // 移除重复的标题（如"工作职责:"后面又有"工作职责:"）
        cleaned = cleaned.replace(/^(工作职责|任职资格|岗位职责|任职要求)[:：]\\s*(工作职责|任职资格|岗位职责|任职要求)[:：]/g, '$1：');
        
        // 移除开头的冒号和空白字符
        cleaned = cleaned.replace(/^[:：]\\s*/, '');
        
        // 使用cleanMarkdown函数清理Markdown格式
        cleaned = cleanMarkdown(cleaned);
        
        // 彻底清理所有多余空格
        // 1. 将多个连续空格替换为单个空格
        cleaned = cleaned.replace(/[ ]+/g, ' ');
        
        // 2. 移除换行前后的空格
        cleaned = cleaned.replace(/\\s*\\n\\s*/g, '\\n');
        
        // 3. 确保数字列表格式整齐
        cleaned = cleaned.replace(/\\n?(\\d+[、.)）])/g, '\\n$1');
        
        // 4. 移除行首行尾的空格（对每行单独处理）
        cleaned = cleaned.split('\\n').map(line => line.trim()).join('\\n');
        
        // 5. 合并多个连续换行
        cleaned = cleaned.replace(/\\n{3,}/g, '\\n\\n');
        
        // 6. 移除开头和结尾的换行
        cleaned = cleaned.replace(/^\\n+|\\n+$/g, '');
        
        // 7. 特殊处理：如果整个文本以大量空格开头（常见于爬取数据）
        cleaned = cleaned.replace(/^\\s{10,}/g, '');
        
        return cleaned;
    };
    
    // 切换岗位详情显示（展开/收起）- 原版本
    window.toggleJobDetail = function(elementId, fullText, buttonElement) {
        const element = document.getElementById(elementId);
        if (!element || !buttonElement) return;
        
        const isExpanded = buttonElement.textContent === '收起';
        
        // 清理文本格式
        const cleanedText = window.cleanJobText(fullText);
        
        if (isExpanded) {
            // 收起：显示截断文本
            const truncatedText = cleanedText.length > 800 ? cleanedText.substring(0, 800) + '...' : cleanedText;
            element.innerHTML = truncatedText;
            buttonElement.textContent = '展开全文';
        } else {
            // 展开：显示完整文本
            element.innerHTML = cleanedText;
            buttonElement.textContent = '收起';
        }
    };
    
    // 安全版本的岗位详情切换（使用data属性避免特殊字符问题）
    window.toggleJobDetailSafe = function(buttonElement) {
        if (!buttonElement) return;
        
        const elementId = buttonElement.getAttribute('data-detail-id');
        const encodedFullText = buttonElement.getAttribute('data-full-text');
        const element = document.getElementById(elementId);
        
        if (!element || !encodedFullText) {
            console.error('❌ 展开功能参数缺失:', {elementId, encodedFullText: !!encodedFullText});
            return;
        }
        
        const isExpanded = buttonElement.textContent.trim() === '收起';
        
        try {
            // 解码文本内容
            const fullText = decodeURIComponent(encodedFullText);
            const cleanedText = window.cleanJobText(fullText);
            
            if (isExpanded) {
                // 收起：显示截断文本
                const truncatedText = cleanedText.length > 800 ? cleanedText.substring(0, 800) + '...' : cleanedText;
                element.innerHTML = truncatedText;
                buttonElement.textContent = '展开全文';
                console.log('✅ 文本已收起');
            } else {
                // 展开：显示完整文本
                element.innerHTML = cleanedText;
                buttonElement.textContent = '收起';
                console.log('✅ 文本已展开，完整长度:', cleanedText.length);
            }
            
        } catch (error) {
            console.error('❌ 展开文本失败:', error);
            buttonElement.textContent = '展开失败';
        }
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
            // 重新显示市场分析报告
            if (currentMarketAnalysis) {
                displayMarketAnalysis(currentMarketAnalysis);
            }
        } else {
            fetchAllJobs();
        }
    };
    
    window.showQualifiedJobs = function() {
        console.log('⭐ 显示合格岗位');
        currentView = 'qualified';
        renderJobsList(qualifiedJobs);
        // 重新显示市场分析报告
        if (currentMarketAnalysis) {
            displayMarketAnalysis(currentMarketAnalysis);
        }
    };
    
    // ========== 岗位搜索功能 ==========
    if (startBtn) {
        startBtn.addEventListener('click', async () => {
            if (isSearching) return;
            
            const keyword = document.getElementById('keyword').value.trim();
            const city = document.getElementById('city').value;
            const aiModel = document.getElementById('ai_model').value;
            
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
            
            console.log('🔍 开始搜索:', { keyword, city, aiModel });
            
            try {
                const response = await axios.post('/api/jobs/search', {
                    keyword,
                    city,
                    max_jobs: parseInt(document.getElementById('max_jobs').value) || 20,
                    ai_model: aiModel  // 传递用户选择的AI模型
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
            displayResults(data.data.results, data.data.stats, data.data.market_analysis);
            
            // 存储并自动显示市场分析报告
            if (data.data.market_analysis) {
                console.log('📊 存储并自动显示市场分析报告');
                currentMarketAnalysis = data.data.market_analysis;
                displayMarketAnalysis(data.data.market_analysis);
            }
            if (data.data.all_jobs) {
                allJobs = data.data.all_jobs;
            }
        }
    }
    
    // 显示结果
    function displayResults(results, stats, marketAnalysis) {
        console.log('📊 显示结果:', { results: results?.length, stats, marketAnalysis });
        
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
            
            // 先渲染岗位列表（清空容器）
            renderJobsList(results);
            
            // 然后显示市场分析报告（插入到列表前面）
            if (marketAnalysis) {
                currentMarketAnalysis = marketAnalysis; // 存储市场分析数据
                displayMarketAnalysis(marketAnalysis);
            } else {
                console.warn('⚠️ 市场分析数据为空:', marketAnalysis);
            }
        }
    }
    
    // 显示市场分析报告
    function displayMarketAnalysis(analysis) {
        console.log('📊 显示市场分析:', analysis);
        console.log('📊 分析数据详情:', {
            market_overview: analysis?.market_overview,
            skill_requirements: analysis?.skill_requirements,
            key_findings: analysis?.key_findings?.length || 0,
            core_responsibilities: analysis?.core_responsibilities?.length || 0
        });
        
        if (!analysis || typeof analysis !== 'object') {
            console.error('❌ 市场分析数据无效:', analysis);
            return;
        }
        
        // 查找或创建市场分析容器
        let marketAnalysisEl = document.getElementById('market-analysis');
        if (!marketAnalysisEl) {
            // 在岗位列表之前创建市场分析容器
            marketAnalysisEl = document.createElement('div');
            marketAnalysisEl.id = 'market-analysis';
            marketAnalysisEl.className = 'bg-gradient-to-br from-purple-50 to-blue-50 rounded-lg p-6 mb-6 shadow-sm';
            
            // 正确插入到jobs-list容器内的最前面
            const jobsList = document.getElementById('jobs-list');
            if (jobsList) {
                // 总是插入到最前面
                if (jobsList.firstChild) {
                    jobsList.insertBefore(marketAnalysisEl, jobsList.firstChild);
                } else {
                    jobsList.appendChild(marketAnalysisEl);
                }
                console.log('✅ 市场分析容器已插入到jobs-list最前面');
            } else {
                console.error('❌ 未找到jobs-list容器');
                return;
            }
        }
        
        // 构建市场分析内容
        let analysisHTML = `
            <h3 class="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                <span class="text-2xl mr-2">📊</span>
                市场整体分析报告
                <span class="text-sm font-normal text-gray-600 ml-2">
                    (基于 ${analysis.market_overview?.total_jobs_analyzed || 0} 个岗位)
                </span>
            </h3>
        `;
        
        // 核心必备技能
        if (analysis.skill_requirements?.hard_skills?.core_required?.length > 0) {
            analysisHTML += `
                <div class="mb-4">
                    <h4 class="text-sm font-medium text-gray-700 mb-2">🔧 核心必备技能</h4>
                    <div class="space-y-1">
                        ${analysis.skill_requirements.hard_skills.core_required.slice(0, 5).map(skill => `
                            <div class="flex items-center text-sm">
                                <span class="text-gray-700 flex-1">${cleanMarkdown(skill.name)}</span>
                                <span class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                                    ${skill.frequency}
                                </span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        // 重要加分技能
        if (analysis.skill_requirements?.hard_skills?.important_preferred?.length > 0) {
            analysisHTML += `
                <div class="mb-4">
                    <h4 class="text-sm font-medium text-gray-700 mb-2">⭐ 重要加分技能</h4>
                    <div class="flex flex-wrap gap-2">
                        ${analysis.skill_requirements.hard_skills.important_preferred.slice(0, 8).map(skill => `
                            <span class="text-xs bg-white px-3 py-1 rounded-full border border-gray-200">
                                ${cleanMarkdown(skill.name)} 
                                <span class="text-gray-500">(${skill.frequency})</span>
                            </span>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        // 核心职责
        if (analysis.core_responsibilities && analysis.core_responsibilities.length > 0) {
            analysisHTML += `
                <div class="mb-4">
                    <h4 class="text-sm font-medium text-gray-700 mb-2">📋 核心职责</h4>
                    <ul class="list-disc list-inside text-sm text-gray-600 space-y-1">
                        ${analysis.core_responsibilities.slice(0, 5).map(resp => `
                            <li>${cleanMarkdown(resp)}</li>
                        `).join('')}
                    </ul>
                </div>
            `;
        }
        
        // 关键发现
        if (analysis.key_findings && analysis.key_findings.length > 0) {
            analysisHTML += `
                <div class="mb-2">
                    <h4 class="text-sm font-medium text-gray-700 mb-2">🎯 关键发现</h4>
                    <div class="space-y-2">
                        ${analysis.key_findings.map(finding => `
                            <div class="text-sm text-gray-600 bg-white p-2 rounded border-l-4 border-blue-400">
                                ${cleanMarkdown(finding)}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        marketAnalysisEl.innerHTML = analysisHTML;
        marketAnalysisEl.style.display = 'block';
    }
    
    // 渲染岗位列表
    function renderJobsList(jobs) {
        console.log('🎨 渲染岗位列表:', jobs.length);
        if (!jobsList) return;
        
        // 保留市场分析容器内容（如果存在）
        const marketAnalysisEl = document.getElementById('market-analysis');
        let marketAnalysisHTML = '';
        if (marketAnalysisEl) {
            marketAnalysisHTML = marketAnalysisEl.outerHTML;
            console.log('📊 保存市场分析内容用于重新插入');
        }
        
        // 清空容器
        jobsList.innerHTML = '';
        
        // 重新插入市场分析（如果存在）
        if (marketAnalysisHTML) {
            jobsList.innerHTML = marketAnalysisHTML;
            console.log('✅ 市场分析已重新插入到列表顶部');
        }
        
        // 添加岗位卡片
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
                <h3 class="text-lg font-semibold text-gray-900 mb-2">${cleanMarkdown(job.title) || '未知岗位'}</h3>
                <div class="text-gray-600 mb-2">🏢 ${cleanMarkdown(job.company) || '未知公司'} • 💰 ${cleanMarkdown(job.salary) || '薪资面议'}</div>
                <div class="text-gray-600 mb-2">📍 ${job.work_location || '未知地点'}</div>
                ${job.url ? `
                    <div class="text-gray-600 mb-2">
                        🔗 <a href="${job.url}" target="_blank" class="text-blue-600 hover:text-blue-800 underline text-sm">
                            查看岗位详情
                        </a>
                    </div>
                ` : ''}
            </div>
        `;
        
        // 添加岗位要求展示（合并工作职责和任职资格）
        if ((job.job_description && job.job_description !== '具体要求请查看岗位详情' && 
            !job.job_description.includes('基于文本解析的岗位描述')) ||
            (job.job_requirements && job.job_requirements !== '具体要求请查看岗位详情')) {
            
            const jobDetailsDiv = document.createElement('div');
            jobDetailsDiv.className = 'mt-4';
            
            // 合并工作职责和任职资格内容
            let combinedContent = '';
            
            // 添加工作职责内容
            if (job.job_description && job.job_description.length > 20) {
                combinedContent += job.job_description;
            }
            
            // 添加任职资格内容（如果存在且不重复）
            if (job.job_requirements && job.job_requirements.length > 20) {
                // 如果工作职责中没有包含任职资格内容，则添加
                if (!combinedContent.includes(job.job_requirements.substring(0, 50))) {
                    if (combinedContent) {
                        combinedContent += '\\n\\n';
                    }
                    combinedContent += job.job_requirements;
                }
            }
            
            if (combinedContent) {
                // 清理文本格式
                const cleanedContent = window.cleanJobText(combinedContent);
                const isLong = cleanedContent.length > 800;
                const displayText = isLong ? cleanedContent.substring(0, 800) : cleanedContent;
                const detailId = 'detail_' + Math.random().toString(36).substr(2, 9);
                
                const jobDetailsHTML = `
                    <div class="bg-gray-50 p-3 rounded-lg">
                        <div class="text-sm font-medium text-gray-900 mb-2">📋 岗位要求</div>
                        <div class="text-xs text-gray-700 whitespace-pre-wrap" id="${detailId}_desc">
                            ${displayText}${isLong ? '...' : ''}
                        </div>
                        ${isLong ? `
                            <button data-detail-id="${detailId}_desc" data-full-text="${encodeURIComponent(cleanedContent)}" 
                                    onclick="toggleJobDetailSafe(this)" 
                                    class="text-xs text-gray-600 hover:text-gray-800 mt-2 underline">
                                展开全文
                            </button>
                        ` : ''}
                    </div>
                `;
                
                jobDetailsDiv.innerHTML = jobDetailsHTML;
                div.appendChild(jobDetailsDiv);
            }
        }
        
        
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
