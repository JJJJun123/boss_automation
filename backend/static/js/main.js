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
    // 移除分析相关元素
    
    // 岗位搜索相关元素
    const startBtn = document.getElementById('start-search-btn');
    const progressBar = document.getElementById('progress-bar');
    const progressFill = document.getElementById('progress-fill');
    const progressMessage = document.getElementById('progress-message');
    const progressLogs = document.getElementById('progress-logs');
    const statsCard = document.getElementById('stats-card');
    const jobsList = document.getElementById('jobs-list');
    const emptyState = document.getElementById('empty-state');
    
    // ========== 单页面应用，移除页面切换功能 ==========
    
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
    
    
    // 显示AI分析结果 - 适配新的LangGPT格式
    // 移除复杂的AI分析显示功能，改为简单的简历状态更新
    
    // 重置上传区域
    function resetUploadArea() {
        if (uploadProgress) uploadProgress.style.display = 'none';
        if (uploadArea) uploadArea.style.display = 'block';
        // 移除分析结果相关元素的处理
    }
    
    // 更新简历状态（简化版本）
    function updateResumeStatus(resumeData) {
        const resumeStatusEl = document.getElementById('resume-status');
        
        if (resumeStatusEl && resumeData) {
            resumeStatusEl.innerHTML = `
                <div class="flex items-center justify-between py-2">
                    <div class="flex items-center space-x-2">
                        <div class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center">
                            <span class="text-green-600 text-xs font-bold">✓</span>
                        </div>
                        <div>
                            <div class="text-sm font-medium text-gray-900">${resumeData.name || '简历已上传'}</div>
                            <div class="text-xs text-gray-500">${resumeData.current_position || '已加载个人信息'}</div>
                        </div>
                    </div>
                    <button onclick="window.deleteResume()" class="text-red-600 hover:text-red-700 text-xs font-medium">
                        删除
                    </button>
                </div>
            `;
        }
    }
    
    // 重置简历状态（简化版本）
    function resetResumeStatus() {
        const resumeStatusEl = document.getElementById('resume-status');
        
        if (resumeStatusEl) {
            resumeStatusEl.innerHTML = `
                <div class="text-center py-2">
                    <p class="text-sm text-gray-600">未上传简历</p>
                    <p class="text-xs text-gray-500">上传后获得更精准匹配</p>
                </div>
            `;
        }
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
        
        if (qualifiedJobs && qualifiedJobs.length > 0) {
            renderJobsList(qualifiedJobs);
            // 重新显示市场分析报告
            if (currentMarketAnalysis) {
                displayMarketAnalysis(currentMarketAnalysis);
            }
        } else {
            // 没有合格岗位时显示提示
            const jobsList = document.getElementById('jobs-list');
            if (jobsList) {
                jobsList.innerHTML = `
                    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
                        <div class="w-16 h-16 bg-yellow-100 rounded-full mx-auto mb-4 flex items-center justify-center">
                            <span class="text-3xl">📊</span>
                        </div>
                        <h3 class="text-lg font-semibold text-yellow-800 mb-2">暂无合格岗位</h3>
                        <p class="text-yellow-700 mb-4">
                            当前没有评分达标的岗位。
                        </p>
                        <p class="text-sm text-yellow-600">
                            建议：点击"总搜索数"查看所有岗位，或调整搜索条件
                        </p>
                    </div>
                `;
            }
            
            // 仍然显示市场分析报告（如果有）
            if (currentMarketAnalysis) {
                displayMarketAnalysis(currentMarketAnalysis);
            }
        }
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
                    max_jobs: parseInt(document.getElementById('max_jobs').value) || 5
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
        console.log('🔄 更新进度:', data);
        
        // 更新主要状态消息
        if (progressMessage) {
            progressMessage.textContent = data.message;
        }
        
        // 更新进度条和百分比
        if (data.progress !== undefined) {
            const progressBar = document.getElementById('progress-bar');
            const progressFill = document.getElementById('progress-fill');
            const progressPercentage = document.getElementById('progress-percentage');
            const stageIndicators = document.getElementById('stage-indicators');
            
            if (progressBar && progressFill) {
                progressBar.style.display = 'block';
                progressFill.style.width = data.progress + '%';
                
                if (progressPercentage) {
                    progressPercentage.style.display = 'block';
                    progressPercentage.textContent = Math.round(data.progress) + '%';
                }
                
                // 显示阶段指示器
                if (stageIndicators) {
                    stageIndicators.style.display = 'grid';
                    updateStageIndicators(data.progress, data.message);
                }
                
                // 当进度达到100%时，重置搜索按钮状态（双重保险）
                if (data.progress >= 100) {
                    isSearching = false;
                    const startBtn = document.getElementById('start-search-btn');
                    if (startBtn) {
                        startBtn.textContent = '开始搜索';
                        startBtn.disabled = false;
                    }
                }
            }
        }
        
        // 添加到详细日志
        const progressLogs = document.getElementById('progress-logs');
        if (progressLogs) {
            const logItem = document.createElement('div');
            logItem.className = 'flex items-start py-1 px-2 hover:bg-gray-50 rounded text-xs';
            
            // 检查消息是否已包含emoji，如果有就不添加额外图标
            let icon = '•';
            const hasEmoji = /[\u{1F600}-\u{1F64F}]|[\u{1F300}-\u{1F5FF}]|[\u{1F680}-\u{1F6FF}]|[\u{1F1E0}-\u{1F1FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]/u.test(data.message);
            
            if (!hasEmoji) {
                if (data.message.includes('开始') || data.message.includes('初始化')) icon = '🚀';
                else if (data.message.includes('搜索') || data.message.includes('设置')) icon = '🔍';
                else if (data.message.includes('AI') || data.message.includes('智能')) icon = '🧠';
                else if (data.message.includes('分析') || data.message.includes('市场')) icon = '📊';
                else if (data.message.includes('完成') || data.message.includes('成功')) icon = '✅';
                else if (data.message.includes('警告') || data.message.includes('未检测')) icon = '⚠️';
                else if (data.message.includes('失败') || data.message.includes('错误')) icon = '❌';
            } else {
                icon = ''; // 如果消息已有emoji就不显示额外图标
            }
            
            logItem.innerHTML = `
                <span class="mr-2 flex-shrink-0">${icon}</span>
                <div class="flex-1">
                    <span class="text-gray-700">${data.message}</span>
                    <span class="text-gray-400 ml-2">${data.timestamp}</span>
                </div>
            `;
            progressLogs.appendChild(logItem);
            progressLogs.scrollTop = progressLogs.scrollHeight;
        }
        
        // 处理结果数据
        if (data.data) {
            console.log('📦 收到数据:', Object.keys(data.data));
            
            // 检查是否需要简历
            if (data.data.requires_resume) {
                displayResumeRequiredMessage(data.data);
            } else {
                displayResults(data.data.results, data.data.stats, data.data.market_analysis);
                
                // 存储并自动显示市场分析报告
                if (data.data.market_analysis) {
                    console.log('📊 收到市场分析数据:', data.data.market_analysis);
                    console.log('📊 市场分析数据结构:', Object.keys(data.data.market_analysis));
                    currentMarketAnalysis = data.data.market_analysis;
                    displayMarketAnalysis(data.data.market_analysis);
                } else {
                    console.log('❌ 未收到市场分析数据');
                    // 如果没有市场分析，清除之前的数据
                    currentMarketAnalysis = null;
                    console.log('🧹 清除之前的市场分析数据');
                }
            }
            
            // 总是存储所有岗位数据
            if (data.data.all_jobs) {
                allJobs = data.data.all_jobs;
            }
        }
    }
    
    // 更新阶段指示器
    function updateStageIndicators(progress, message) {
        const stageItems = document.querySelectorAll('.stage-item');
        
        // 重置所有阶段
        stageItems.forEach(item => {
            const circle = item.querySelector('div');
            const text = item.querySelector('div:last-child');
            circle.className = 'w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-xs font-bold mx-auto mb-1';
            text.className = 'text-xs text-center text-gray-500';
        });
        
        // 根据进度和消息内容更准确地判断阶段
        let currentStage = '';
        
        if (progress >= 5 && progress <= 50) {
            currentStage = 'search';
        } else if (progress > 50 && (message.includes('AI') || message.includes('智能') || message.includes('分析') || progress <= 80)) {
            currentStage = 'extract'; // 实际上是AI分析阶段
        } else if (progress > 80 && progress < 100) {
            currentStage = 'analysis'; // 实际上是保存和整理阶段
        } else if (progress >= 100) {
            currentStage = 'complete';
        }
        
        // 阶段1：搜索岗位 (5-50%)
        const searchStage = document.querySelector('[data-stage="search"]');
        if (searchStage) {
            const circle = searchStage.querySelector('div');
            const text = searchStage.querySelector('div:last-child');
            if (currentStage === 'search') {
                circle.className = 'w-8 h-8 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1 animate-pulse';
                circle.innerHTML = '1';
                text.className = 'text-xs text-center text-blue-600 font-medium';
            } else if (progress > 50) {
                circle.className = 'w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1';
                circle.innerHTML = '✓';
                text.className = 'text-xs text-center text-green-600';
            }
        }
        
        // 阶段2：AI分析 (50-80%) - 重新标记为AI分析
        const extractStage = document.querySelector('[data-stage="extract"]');
        if (extractStage) {
            const circle = extractStage.querySelector('div');
            const text = extractStage.querySelector('div:last-child');
            // 更新标签文本
            text.textContent = 'AI分析';
            
            if (currentStage === 'extract') {
                circle.className = 'w-8 h-8 rounded-full bg-purple-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1 animate-pulse';
                circle.innerHTML = '2';
                text.className = 'text-xs text-center text-purple-600 font-medium';
            } else if (progress > 80) {
                circle.className = 'w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1';
                circle.innerHTML = '✓';
                text.className = 'text-xs text-center text-green-600';
            }
        }
        
        // 阶段3：整理结果 (80-95%)
        const analysisStage = document.querySelector('[data-stage="analysis"]');
        if (analysisStage) {
            const circle = analysisStage.querySelector('div');
            const text = analysisStage.querySelector('div:last-child');
            // 更新标签文本
            text.textContent = '整理结果';
            
            if (currentStage === 'analysis') {
                circle.className = 'w-8 h-8 rounded-full bg-orange-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1 animate-pulse';
                circle.innerHTML = '3';
                text.className = 'text-xs text-center text-orange-600 font-medium';
            } else if (progress >= 100) {
                circle.className = 'w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1';
                circle.innerHTML = '✓';
                text.className = 'text-xs text-center text-green-600';
            }
        }
        
        if (progress >= 100) {
            // 阶段4：完成
            const completeStage = document.querySelector('[data-stage="complete"]');
            if (completeStage) {
                const circle = completeStage.querySelector('div');
                const text = completeStage.querySelector('div:last-child');
                circle.className = 'w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1';
                circle.innerHTML = '🎉';
                text.className = 'text-xs text-center text-green-600 font-medium';
            }
        }
    }
    
    // 切换日志显示
    window.toggleProgressLogs = function() {
        const logs = document.getElementById('progress-logs');
        const toggleBtn = document.getElementById('toggle-logs');
        
        if (logs && toggleBtn) {
            if (logs.style.display === 'none' || logs.style.display === '') {
                logs.style.display = 'block';
                toggleBtn.textContent = '收起';
            } else {
                logs.style.display = 'none';
                toggleBtn.textContent = '展开';
            }
        }
    }
    
    // 显示需要简历的提示消息
    function displayResumeRequiredMessage(data) {
        console.log('📋 显示需要简历的提示');
        
        // 显示统计信息（搜索到的岗位数量）
        if (data.stats) {
            const totalEl = document.getElementById('total-jobs');
            const qualifiedEl = document.getElementById('qualified-jobs');
            if (totalEl) totalEl.textContent = data.stats.total;
            if (qualifiedEl) qualifiedEl.textContent = '需要简历';
            if (statsCard) statsCard.style.display = 'block';
        }
        
        // 显示提示消息
        const jobsList = document.getElementById('jobs-list');
        if (jobsList) {
            jobsList.innerHTML = `
                <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
                    <div class="w-16 h-16 bg-yellow-100 rounded-full mx-auto mb-4 flex items-center justify-center">
                        <span class="text-3xl">📄</span>
                    </div>
                    <h3 class="text-lg font-semibold text-yellow-800 mb-2">需要上传简历</h3>
                    <p class="text-yellow-700 mb-4">
                        已搜索到 <strong>${data.stats?.total || 0}</strong> 个岗位，但需要先上传简历才能进行AI智能分析和匹配
                    </p>
                    <p class="text-sm text-yellow-600 mb-4">
                        上传简历后，系统将为每个岗位提供：
                    </p>
                    <ul class="text-sm text-yellow-600 text-left max-w-md mx-auto mb-4">
                        <li class="flex items-center mb-1">
                            <span class="w-1.5 h-1.5 bg-yellow-500 rounded-full mr-2"></span>
                            1-10分的匹配度评分
                        </li>
                        <li class="flex items-center mb-1">
                            <span class="w-1.5 h-1.5 bg-yellow-500 rounded-full mr-2"></span>
                            详细的匹配原因分析
                        </li>
                        <li class="flex items-center mb-1">
                            <span class="w-1.5 h-1.5 bg-yellow-500 rounded-full mr-2"></span>
                            个性化的推荐建议
                        </li>
                        <li class="flex items-center">
                            <span class="w-1.5 h-1.5 bg-yellow-500 rounded-full mr-2"></span>
                            市场趋势分析报告
                        </li>
                    </ul>
                    <button onclick="showPage('resume')" class="bg-yellow-600 hover:bg-yellow-700 text-white px-6 py-2 rounded-lg text-sm font-medium transition-colors">
                        前往上传简历
                    </button>
                </div>
            `;
        }
        
        if (emptyState) emptyState.style.display = 'none';
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
        } else {
            // 没有合格岗位时，清空岗位列表并显示相应提示
            console.log('📋 没有合格岗位，清空之前的结果');
            qualifiedJobs = [];
            
            // 清空岗位列表
            const jobsList = document.getElementById('jobs-list');
            if (jobsList) {
                if (marketAnalysis) {
                    // 如果有市场分析，显示分析结果但提示没有合格岗位
                    jobsList.innerHTML = '';
                    displayMarketAnalysis(marketAnalysis);
                    
                    // 添加无合格岗位的提示
                    const noJobsMessage = document.createElement('div');
                    noJobsMessage.className = 'bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center mt-6';
                    noJobsMessage.innerHTML = `
                        <div class="w-16 h-16 bg-yellow-100 rounded-full mx-auto mb-4 flex items-center justify-center">
                            <span class="text-3xl">📊</span>
                        </div>
                        <h3 class="text-lg font-semibold text-yellow-800 mb-2">暂无合格岗位</h3>
                        <p class="text-yellow-700 mb-4">
                            虽然搜索到了 <strong>${stats?.total || 0}</strong> 个岗位，但根据当前简历分析，没有找到评分达标的岗位。
                        </p>
                        <p class="text-sm text-yellow-600">
                            建议：调整搜索关键词或查看市场分析报告了解技能要求差距
                        </p>
                    `;
                    jobsList.appendChild(noJobsMessage);
                } else {
                    // 没有市场分析时的提示
                    jobsList.innerHTML = `
                        <div class="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
                            <div class="w-16 h-16 bg-gray-100 rounded-full mx-auto mb-4 flex items-center justify-center">
                                <span class="text-3xl">🔍</span>
                            </div>
                            <h3 class="text-lg font-semibold text-gray-800 mb-2">暂无合格岗位</h3>
                            <p class="text-gray-600">
                                搜索到了 <strong>${stats?.total || 0}</strong> 个岗位，但没有找到评分达标的岗位。
                            </p>
                        </div>
                    `;
                }
            }
            
            if (emptyState) emptyState.style.display = 'none';
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
            // 如果没有市场分析，显示基本提示
            let marketAnalysisEl = document.getElementById('market-analysis');
            if (!marketAnalysisEl) {
                marketAnalysisEl = document.createElement('div');
                marketAnalysisEl.id = 'market-analysis';
                marketAnalysisEl.className = 'bg-blue-50 border border-blue-200 rounded-xl p-6 mb-6';
                
                const jobsList = document.getElementById('jobs-list');
                if (jobsList) {
                    jobsList.insertBefore(marketAnalysisEl, jobsList.firstChild);
                }
            }
            
            marketAnalysisEl.innerHTML = `
                <h3 class="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                    <span class="text-2xl mr-2">📊</span>
                    市场整体分析报告
                    <span class="text-sm font-normal text-gray-600 ml-2">
                        (基于 ${window.currentSearchData?.all_jobs?.length || 0} 个岗位)
                    </span>
                </h3>
                <div class="text-sm text-gray-600">
                    <p>市场分析功能暂未启用，请查看具体岗位的详细匹配分析。</p>
                </div>
            `;
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
        
        // 构建新的可视化市场分析内容
        let analysisHTML = `
            <h3 class="text-lg font-semibold text-gray-800 mb-6 flex items-center">
                <span class="text-2xl mr-2">📊</span>
                市场整体分析报告
                <span class="text-sm font-normal text-gray-600 ml-2">
                    基于 ${analysis.total_jobs_analyzed || window.currentSearchData?.all_jobs?.length || 0} 个岗位分析
                </span>
            </h3>
        `;
        
        // 共同技能要求 - AI智能提取
        const commonSkills = analysis.common_skills || [];
        if (commonSkills.length > 0) {
            analysisHTML += `
                <div class="mb-6">
                    <h4 class="text-sm font-medium text-gray-700 mb-4">🔧 共同技能要求（AI识别）</h4>
                    <div class="space-y-3">
                        ${commonSkills.map(skill => {
                            const barWidth = Math.max(skill.percentage || 0, 5); // 最小宽度5%
                            return `
                                <div class="flex items-center text-sm">
                                    <div class="w-24 text-gray-700 font-medium flex-shrink-0">${skill.name || '未知'}</div>
                                    <div class="flex-1 mx-3">
                                        <div class="bg-gray-200 rounded-full h-4 relative">
                                            <div class="bg-blue-500 h-4 rounded-full flex items-center justify-end pr-2" style="width: ${barWidth}%">
                                                <span class="text-xs text-white font-medium">${skill.percentage || 0}%</span>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="text-xs text-gray-500 w-16 text-right">${skill.percentage || 0}%岗位</div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }

        // 关键词云 - AI提取
        const keywordCloud = analysis.keyword_cloud || [];
        if (keywordCloud.length > 0) {
            analysisHTML += `
                <div class="mb-6">
                    <h4 class="text-sm font-medium text-gray-700 mb-4">☁️ 关键词云（AI提取）</h4>
                    <div class="flex flex-wrap gap-2">
                        ${keywordCloud.map(keyword => {
                            const count = keyword.count || 0;
                            const fontSize = Math.min(16 + count * 0.5, 24); // 根据频率调整字体大小
                            return `
                                <span class="inline-flex items-center px-3 py-1 rounded-full bg-purple-100 text-purple-700 hover:bg-purple-200 transition-colors"
                                      style="font-size: ${fontSize}px">
                                    ${keyword.word || keyword}
                                    <span class="ml-1 text-xs text-purple-500">(${count})</span>
                                </span>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }

        // 差异化分析 - AI深度分析
        const diffAnalysis = analysis.differentiation_analysis?.analysis || analysis.differentiation_analysis;
        if (diffAnalysis && diffAnalysis !== '暂无差异化分析') {
            analysisHTML += `
                <div class="mb-6 bg-gradient-to-r from-yellow-50 to-orange-50 rounded-lg p-4 border border-yellow-200">
                    <h4 class="text-sm font-medium text-gray-700 mb-3">🔍 差异化分析（AI洞察）</h4>
                    <div class="text-sm text-gray-700 whitespace-pre-line leading-relaxed">
                        ${diffAnalysis}
                    </div>
                </div>
            `;
        }
        
        // 学历和经验要求分布
        const hasDistributionData = (analysis.education_distribution && Object.keys(analysis.education_distribution).length > 0) ||
                                   (analysis.experience_distribution && Object.keys(analysis.experience_distribution).length > 0);
        
        if (hasDistributionData) {
            analysisHTML += `
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            `;
            
            // 学历要求分布
            if (analysis.education_distribution && Object.keys(analysis.education_distribution).length > 0) {
                const eduData = analysis.education_distribution;
                analysisHTML += `
                    <div>
                        <h4 class="text-sm font-medium text-gray-700 mb-3">🎓 学历要求分布</h4>
                        <div class="space-y-2">
                            ${Object.entries(eduData).map(([edu, percentage]) => `
                                <div class="flex items-center text-sm">
                                    <div class="w-12 text-gray-700 font-medium">${edu}</div>
                                    <div class="flex-1 mx-3">
                                        <div class="bg-gray-200 rounded h-3 relative">
                                            <div class="bg-green-500 h-3 rounded" style="width: ${percentage}%"></div>
                                        </div>
                                    </div>
                                    <div class="text-xs text-gray-600 w-10 text-right">${percentage}%</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }
            
            // 经验要求分布
            if (analysis.experience_distribution && Object.keys(analysis.experience_distribution).length > 0) {
                const expData = analysis.experience_distribution;
                analysisHTML += `
                    <div>
                        <h4 class="text-sm font-medium text-gray-700 mb-3">📅 经验要求分布</h4>
                        <div class="space-y-2">
                            ${Object.entries(expData).map(([exp, percentage]) => `
                                <div class="flex items-center text-sm">
                                    <div class="w-16 text-gray-700 font-medium">${exp}</div>
                                    <div class="flex-1 mx-3">
                                        <div class="bg-gray-200 rounded h-3 relative">
                                            <div class="bg-purple-500 h-3 rounded" style="width: ${percentage}%"></div>
                                        </div>
                                    </div>
                                    <div class="text-xs text-gray-600 w-10 text-right">${percentage}%</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }
            
            analysisHTML += '</div>';
        }
        
        // 关键洞察 - 完全来自AI，无硬编码兜底
        const keyInsights = analysis.key_insights || [];
        if (keyInsights.length > 0) {
            analysisHTML += `
                <div class="bg-blue-50 rounded-lg p-4">
                    <h4 class="text-sm font-medium text-gray-700 mb-3">💡 关键洞察（AI生成）</h4>
                    <ul class="space-y-2 text-sm text-gray-700">
                        ${keyInsights.map(insight => `
                            <li class="flex items-start">
                                <span class="text-blue-500 mr-2 flex-shrink-0">•</span>
                                <span>${insight}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            `;
        } else {
            // AI未生成洞察时，明确说明而非使用硬编码
            analysisHTML += `
                <div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
                    <h4 class="text-sm font-medium text-gray-700 mb-2">💡 关键洞察</h4>
                    <p class="text-sm text-gray-500">AI未生成关键洞察，请查看上方的差异化分析和技能要求。</p>
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
                            职位链接
                        </a>
                    </div>
                ` : ''}
                
                ${isAnalyzed ? `
                    <div class="mt-3 pt-3 border-t border-gray-100">
                        <div class="text-sm text-gray-700 mb-2">
                            🎯 <strong>投递建议:</strong> 
                            <span class="px-2 py-1 rounded text-xs ${analysis.application_advice === '建议投递' ? 'bg-green-100 text-green-700' : analysis.application_advice === '条件投递' ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'}">
                                ${analysis.application_advice || analysis.action_recommendation || '建议投递'} ${analysis.application_advice === '建议投递' ? '✅' : analysis.application_advice === '条件投递' ? '⚠️' : '❌'}
                            </span>
                        </div>
                    </div>
                ` : ''}
            </div>
            
            <!-- 两个展开按钮 -->
            <div class="mt-4 flex gap-2">
                <button 
                    onclick="toggleJobDetails(${index})" 
                    class="flex-1 bg-blue-50 hover:bg-blue-100 text-blue-700 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                    id="toggle-details-${index}"
                >
                    📋 查看岗位详情 ↓
                </button>
                ${isAnalyzed ? `
                    <button 
                        onclick="toggleJobAnalysis(${index})" 
                        class="flex-1 bg-green-50 hover:bg-green-100 text-green-700 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                        id="toggle-analysis-${index}"
                    >
                        📊 查看匹配分析 ↓
                    </button>
                ` : ''}
            </div>
        `;
        
        // 准备岗位详情内容（隐藏状态，等待展开）
        const hasJobDetails = (job.job_description && job.job_description !== '具体要求请查看岗位详情' && 
            !job.job_description.includes('基于文本解析的岗位描述')) ||
            (job.job_requirements && job.job_requirements !== '具体要求请查看岗位详情');
            
        if (hasJobDetails) {
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
                
                const jobDetailsDiv = document.createElement('div');
                jobDetailsDiv.id = `job-details-${index}`;
                jobDetailsDiv.className = 'job-details-panel hidden mt-4';
                jobDetailsDiv.style.display = 'none';
                
                jobDetailsDiv.innerHTML = `
                    <div class="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <div class="text-sm font-medium text-gray-900 mb-3">📋 岗位详情</div>
                        <div class="text-xs text-gray-700 whitespace-pre-wrap" id="${detailId}_desc">
                            ${displayText}${isLong ? '...' : ''}
                        </div>
                        ${isLong ? `
                            <button data-detail-id="${detailId}_desc" data-full-text="${encodeURIComponent(cleanedContent)}" 
                                    onclick="toggleJobDetailSafe(this)" 
                                    class="text-xs text-blue-600 hover:text-blue-800 mt-2 underline">
                                展开全文
                            </button>
                        ` : ''}
                    </div>
                `;
                
                div.appendChild(jobDetailsDiv);
            }
        }
        
        
        // 准备匹配分析面板（隐藏状态）
        if (isAnalyzed && analysis) {
            const analysisDiv = document.createElement('div');
            analysisDiv.id = `job-analysis-${index}`;
            analysisDiv.className = 'job-analysis-panel hidden mt-4';
            analysisDiv.style.display = 'none';
            
            let analysisHTML = `
                <div class="bg-gradient-to-br from-green-50 to-blue-50 border border-green-200 rounded-lg p-4">
                    <div class="text-sm font-semibold text-gray-900 mb-4">📊 匹配度详情</div>
                    
                    <!-- 综合评分 -->
                    <div class="mb-4">
                        <div class="text-sm font-medium text-gray-700 mb-2">综合评分: ${score}/10</div>
                        ${analysis.detailed_dimension_scores ? `
                            <div class="grid grid-cols-3 gap-3 text-xs">
                                <div class="flex justify-between">
                                    <span>学历:</span>
                                    <span class="font-medium">${analysis.detailed_dimension_scores.education || 'N/A'}/10</span>
                                </div>
                                <div class="flex justify-between">
                                    <span>经验:</span>
                                    <span class="font-medium">${analysis.detailed_dimension_scores.experience || 'N/A'}/10</span>
                                </div>
                                <div class="flex justify-between">
                                    <span>技能:</span>
                                    <span class="font-medium">${analysis.detailed_dimension_scores.skills || 'N/A'}/10</span>
                                </div>
                            </div>
                        ` : ''}
                    </div>
                    
                    <!-- 匹配情况 -->
                    <div class="grid grid-cols-2 gap-4 mb-4">
                        <div>
                            <div class="text-xs font-medium text-green-700 mb-2">✅ 符合要求 (${analysis.matched_skills?.length || 0}项)</div>
                            ${analysis.matched_skills && analysis.matched_skills.length > 0 ? `
                                <div class="space-y-1">
                                    ${analysis.matched_skills.slice(0, 5).map(skill => 
                                        `<div class="text-xs text-gray-600">• ${skill}</div>`
                                    ).join('')}
                                </div>
                            ` : '<div class="text-xs text-gray-500">暂无匹配技能</div>'}
                        </div>
                        <div>
                            <div class="text-xs font-medium text-red-700 mb-2">❌ 能力缺口 (${analysis.missing_skills?.length || 0}项)</div>
                            ${analysis.missing_skills && analysis.missing_skills.length > 0 ? `
                                <div class="space-y-1">
                                    ${analysis.missing_skills.slice(0, 5).map(skill => 
                                        `<div class="text-xs text-gray-600">• ${skill}</div>`
                                    ).join('')}
                                </div>
                            ` : '<div class="text-xs text-gray-500">暂无缺失技能</div>'}
                        </div>
                    </div>
                    
                    <!-- 简历优化建议 -->
                    ${analysis.resume_optimization && analysis.resume_optimization.length > 0 ? `
                        <div class="mb-4">
                            <div class="text-xs font-medium text-gray-700 mb-2">📝 简历优化建议</div>
                            <ol class="text-xs text-gray-600 space-y-1">
                                ${analysis.resume_optimization.map((tip, idx) => 
                                    `<li class="pl-4">${idx + 1}. ${tip}</li>`
                                ).join('')}
                            </ol>
                        </div>
                    ` : ''}
                    
                    <!-- 投递决策 -->
                    <div class="mb-4">
                        <div class="text-xs font-medium text-gray-700 mb-2">💡 投递决策: ${analysis.application_advice || '建议投递'}</div>
                        ${analysis.decision_reason ? `
                            <div class="text-xs text-gray-600">理由: ${analysis.decision_reason}</div>
                        ` : ''}
                    </div>
                    
                    <!-- 面试准备 -->
                    ${analysis.interview_preparation && analysis.interview_preparation.length > 0 ? `
                        <div class="text-xs">
                            <div class="font-medium text-gray-700 mb-2">🎯 面试准备</div>
                            <div class="flex flex-wrap gap-2">
                                ${analysis.interview_preparation.map(tip => 
                                    `<span class="bg-blue-100 text-blue-700 px-2 py-1 rounded text-xs">• ${tip}</span>`
                                ).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
            
            analysisDiv.innerHTML = analysisHTML;
            div.appendChild(analysisDiv);
        }
        
        return div;
    }
    
    // 切换岗位详情展示
    window.toggleJobDetails = function(index) {
        const detailsPanel = document.getElementById(`job-details-${index}`);
        const toggleBtn = document.getElementById(`toggle-details-${index}`);
        
        if (detailsPanel && toggleBtn) {
            const isHidden = detailsPanel.style.display === 'none' || detailsPanel.style.display === '';
            
            if (isHidden) {
                detailsPanel.style.display = 'block';
                detailsPanel.classList.remove('hidden');
                toggleBtn.innerHTML = '📋 收起岗位详情 ↑';
                toggleBtn.className = toggleBtn.className.replace('bg-blue-50 hover:bg-blue-100 text-blue-700', 'bg-gray-100 hover:bg-gray-200 text-gray-700');
            } else {
                detailsPanel.style.display = 'none';
                detailsPanel.classList.add('hidden');
                toggleBtn.innerHTML = '📋 查看岗位详情 ↓';
                toggleBtn.className = toggleBtn.className.replace('bg-gray-100 hover:bg-gray-200 text-gray-700', 'bg-blue-50 hover:bg-blue-100 text-blue-700');
            }
        }
    };
    
    // 切换匹配分析展示  
    window.toggleJobAnalysis = function(index) {
        const analysisPanel = document.getElementById(`job-analysis-${index}`);
        const toggleBtn = document.getElementById(`toggle-analysis-${index}`);
        
        if (analysisPanel && toggleBtn) {
            const isHidden = analysisPanel.style.display === 'none' || analysisPanel.style.display === '';
            
            if (isHidden) {
                analysisPanel.style.display = 'block';
                analysisPanel.classList.remove('hidden');
                toggleBtn.innerHTML = '📊 收起匹配分析 ↑';
                toggleBtn.className = toggleBtn.className.replace('bg-green-50 hover:bg-green-100 text-green-700', 'bg-gray-100 hover:bg-gray-200 text-gray-700');
            } else {
                analysisPanel.style.display = 'none';
                analysisPanel.classList.add('hidden');
                toggleBtn.innerHTML = '📊 查看匹配分析 ↓';
                toggleBtn.className = toggleBtn.className.replace('bg-gray-100 hover:bg-gray-200 text-gray-700', 'bg-green-50 hover:bg-green-100 text-green-700');
            }
        }
    };
    
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
                    // 隐藏上传进度
                    if (uploadProgress) uploadProgress.style.display = 'none';
                    
                    // 更新简历状态 - 简化版本，不再显示AI分析
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
