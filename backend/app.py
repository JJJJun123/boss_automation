#!/usr/bin/env python3
"""
Boss直聘自动化Web应用后端
Flask + SocketIO 实现
"""

import os
import sys
import logging
import threading
from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_manager import ConfigManager
from crawler.unified_crawler_interface import unified_search_jobs, get_crawler_capabilities
from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer


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
    return render_template('index.html')


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
        from analyzer.resume.resume_analyzer import ResumeAnalyzer
        
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
        
        # 调试：保存简历文本用于调试
        try:
            with open("debug_resume_text.txt", "w", encoding='utf-8') as f:
                f.write("=== 上传的简历文本 ===\n")
                f.write(f"文件名: {file.filename}\n")
                f.write(f"长度: {len(resume_text)}\n")
                f.write(f"前100字符: {repr(resume_text[:100])}\n")
                f.write("\n=== 完整文本 ===\n")
                f.write(resume_text)
            print(f"简历文本已保存到 debug_resume_text.txt")
        except Exception as debug_e:
            print(f"保存简历文本失败: {debug_e}")
        
        # AI分析简历 - 使用统一的AI架构，从配置读取AI提供商
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            ai_provider = config_manager.get_app_config('ai.default_provider', 'claude')
        except Exception:
            ai_provider = 'claude'
        
        analyzer = ResumeAnalyzer(ai_provider=ai_provider)
        ai_analysis = analyzer.analyze_resume(resume_text)
        
        # 保存完整的简历分析结果到文件
        from analyzer.resume.resume_manager import ResumeManager
        resume_manager = ResumeManager()
        
        # 构建完整的简历数据 - 适配新的LangGPT格式
        resume_core = ai_analysis.get('resume_core', {})
        
        # 从结构化数据中提取基本信息
        education = resume_core.get('education', [])
        work_experience = resume_core.get('work_experience', [])
        skills = resume_core.get('skills', {})
        
        # 估算工作年限
        experience_years = len(work_experience) * 2 if work_experience else 0  # 简单估算
        
        # 获取最高学历
        highest_degree = '未提供'
        if education and len(education) > 0:
            highest_degree = education[0].get('degree', '未提供')
        
        resume_full_data = {
            'basic_info': {
                'name': '已解析',  # 新格式不再包含个人信息
                'current_position': work_experience[0].get('position', '未提供') if work_experience else '未提供',
                'phone': '已脱敏',  # 隐私保护
                'email': '已脱敏'   # 隐私保护
            },
            'skills': skills.get('hard_skills', []) + skills.get('soft_skills', []),
            'experience_years': experience_years,
            'education_info': {'highest_degree': highest_degree},
            'work_experience': work_experience,
            'strengths': ai_analysis.get('strengths', []),
            'weaknesses': ai_analysis.get('weaknesses', []),  # 新增劣势字段
            'job_intentions': ai_analysis.get('recommended_positions', []),  # 使用新字段名
            'salary_expectations': {'min': 15, 'max': 35},  # 默认值
            'resume_core': resume_core,  # 保存完整的结构化数据
            'resume_text': resume_text,  # 保存原始简历文本
            'filename': file.filename,
            'upload_time': datetime.now().isoformat()
        }
        
        # 保存到文件
        resume_manager.save_resume(resume_full_data)
        logger.info("简历信息已保存到文件系统")
        
        # 构建用于显示的简化数据
        resume_data = {
            'name': resume_full_data['basic_info']['name'],
            'current_position': resume_full_data['basic_info']['current_position'],
            'experience_years': f"{resume_full_data['experience_years']}年",
            'phone': '已脱敏',
            'email': '已脱敏',
            'technical_skills': resume_full_data['skills'][:5] if resume_full_data['skills'] else [],  # 只显示前5个技能
            'education': ai_analysis.get('education_info', {}).get('highest_degree', '未提供'),
            'filename': file.filename,
            'upload_time': datetime.now().isoformat()
        }
        
        # 存储到session（只存储摘要信息）
        session['resume_data'] = resume_data
        session['resume_summary'] = {
            'length': len(resume_text),
            'has_text': True,
            'analyzed': True,
            'saved_to_file': True  # 标记已保存到文件
        }
        session['ai_analysis_summary'] = {
            'strengths_count': len(ai_analysis.get('strengths', [])),
            'weaknesses_count': len(ai_analysis.get('weaknesses', [])),
            'recommended_positions': ai_analysis.get('recommended_positions', []),
            'analyzed_at': datetime.now().isoformat()
        }
        
        # 简历上传时不需要创建岗位分析器，只在岗位搜索时才创建
        # 这里只保存简历分析结果，供后续岗位分析使用
        global job_analyzer_instance
        if 'job_analyzer_instance' in globals():
            # 如果已有分析器实例，更新简历分析数据
            if hasattr(job_analyzer_instance, 'set_resume_analysis'):
                job_analyzer_instance.set_resume_analysis(ai_analysis)
            else:
                job_analyzer_instance.resume_analysis = ai_analysis
            print("🎯 简历分析结果已加载到现有岗位分析器")
        
        strengths_count = len(ai_analysis.get('strengths', []))
        weaknesses_count = len(ai_analysis.get('weaknesses', []))
        logger.info(f"简历分析完成: {resume_data['name']}, 优势: {strengths_count}项, 改进点: {weaknesses_count}项")
        
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
        
        # 清除持久化的简历文件
        from analyzer.resume.resume_manager import ResumeManager
        resume_manager = ResumeManager()
        resume_manager.clear_resume()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"删除简历失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/resume/info', methods=['GET'])
def get_resume_info():
    """获取当前保存的简历信息"""
    try:
        from analyzer.resume.resume_manager import ResumeManager
        resume_manager = ResumeManager()
        
        if resume_manager.has_resume():
            profile = resume_manager.get_personal_profile()
            return jsonify({
                'success': True,
                'has_resume': True,
                'resume_info': {
                    'name': profile.get('name', '未知'),
                    'skills': profile.get('skills', []),
                    'experience_years': profile.get('experience_years', 0),
                    'strengths': profile.get('strengths', []),
                    'weaknesses': profile.get('weaknesses', []),
                    'job_intentions': profile.get('job_intentions', [])
                }
            })
        else:
            return jsonify({
                'success': True,
                'has_resume': False,
                'message': '请先上传简历'
            })
            
    except Exception as e:
        logger.error(f"获取简历信息失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/resume/update_intentions', methods=['POST'])
def update_job_intentions():
    """更新求职意向"""
    try:
        data = request.json
        intentions = data.get('intentions', [])
        
        from analyzer.resume.resume_manager import ResumeManager
        resume_manager = ResumeManager()
        
        if not resume_manager.has_resume():
            return jsonify({
                'success': False,
                'error': '请先上传简历'
            })
        
        success = resume_manager.update_job_intentions(intentions)
        
        if success:
            return jsonify({
                'success': True,
                'message': '求职意向已更新'
            })
        else:
            return jsonify({
                'success': False,
                'error': '更新失败'
            })
            
    except Exception as e:
        logger.error(f"更新求职意向失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

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
        
        # 传递session数据给后台任务（避免在线程中使用session）
        session_data = {
            'has_resume_data': 'resume_data' in session,
            'resume_data': session.get('resume_data', None)
        }
        
        # 在新线程中执行搜索任务
        thread = threading.Thread(target=run_job_search_task, args=(data, session_data))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': '任务已启动',
            'task_id': current_job.get('task_id', 'default')
        })
        
    except Exception as e:
        logger.error(f"启动搜索任务失败: {e}")
        return jsonify({'error': str(e)}), 500


def run_job_search_task(params, session_data):
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
        selected_city = params.get('city', 'shanghai')  # 默认上海
        # ai_model参数已移除，系统固定使用EnhancedJobAnalyzer（GLM+DeepSeek）
        
        # 获取城市代码
        city_codes = search_config['city_codes']
        city_code = city_codes.get(selected_city, {}).get('code', '101210100')
        city_name = city_codes.get(selected_city, {}).get('name', '上海')
        
        emit_progress(f"🔍 搜索设置: {keyword} | {city_name} | {max_jobs}个岗位", 10)
        
        # 2. 使用统一爬虫引擎搜索岗位
        emit_progress("🕷️ 启动统一爬虫引擎...", 20)
        
        # 城市代码映射到城市名称
        city_map = {
            "101280600": "shenzhen",    # 深圳
            "101020100": "shanghai",    # 上海
            "101010100": "beijing",     # 北京
            "101210100": "hangzhou"     # 杭州
        }
        city_name = city_map.get(city_code, "shanghai")
        
        # 使用统一爬虫接口进行搜索
        import asyncio
        jobs = asyncio.run(unified_search_jobs(keyword, city_name, max_jobs))
        
        emit_progress(f"🔍 搜索完成: 找到 {len(jobs)} 个岗位", 50)
        
        if not jobs:
            raise Exception("未找到任何岗位")
        
        emit_progress(f"📊 找到 {len(jobs)} 个岗位，开始AI分析...", 50)
        
        # 5. 检查是否有简历，无简历时不进行AI分析
        from analyzer.resume.resume_manager import ResumeManager
        resume_manager = ResumeManager()
        
        # 双重检查：既要文件存在，也要session中有简历记录
        has_file_resume = resume_manager.has_resume()
        has_session_resume = session_data.get('has_resume_data', False)
        
        if not has_file_resume or not has_session_resume:
            # 无简历时直接返回原始岗位数据，不进行AI分析
            if not has_file_resume:
                emit_progress("⚠️ 未检测到简历文件，跳过AI分析", 80)
            else:
                emit_progress("⚠️ 当前会话无简历记录，跳过AI分析", 80)
            
            # 为所有岗位标记为"需要简历"
            jobs_without_analysis = []
            for job in jobs:
                job['analysis'] = {
                    'score': -1,
                    'overall_score': -1,
                    'recommendation': '需要简历',
                    'reason': '请先上传简历后再进行岗位匹配分析',
                    'summary': '上传简历后可获得详细的匹配度分析',
                    'requires_resume': True
                }
                jobs_without_analysis.append(job)
            
            # 7. 保存结果（无分析版本）
            emit_progress("💾 保存搜索结果...", 95)
            from utils.data_saver import save_all_job_results
            save_all_job_results(jobs_without_analysis, [])  # 保存原始岗位，合格岗位为空
            
            # 9. 完成（无分析版本）
            current_job.update({
                'status': 'completed',
                'end_time': datetime.now(),
                'results': [],  # 无合格岗位
                'analyzed_jobs': jobs_without_analysis,
                'total_jobs': len(jobs),
                'analyzed_jobs_count': 0,  # 未进行分析
                'qualified_jobs': 0,
                'market_analysis': None,
                'requires_resume': True  # 标记需要简历
            })
            
            emit_progress(f"📋 搜索完成! 找到 {len(jobs)} 个岗位，请上传简历后进行AI分析", 100, {
                'results': [],
                'all_jobs': jobs_without_analysis,
                'market_analysis': None,
                'requires_resume': True,
                'stats': {
                    'total': len(jobs),
                    'analyzed': 0,
                    'qualified': 0
                }
            })
            
            # 发送搜索完成事件，重置前端按钮状态
            socketio.emit('search_complete', {'status': 'success', 'message': '搜索完成，请上传简历进行分析'})
            return
        
        # 有简历时继续AI分析流程
        emit_progress("📝 检测到简历，开始AI智能分析...", 50)
        
        # 6. AI分析 - 支持动态模型选择
        global job_analyzer_instance
        
        # 如果没有现有实例，创建新的分析器
        if 'job_analyzer_instance' not in globals():
            # 检查是否启用智能分层分析器
            use_smart_analyzer = ai_config.get('use_smart_analyzer', False)  # 默认关闭，需要手动启用
            # 检查是否启用混合AI模式（GLM+DeepSeek）- 强制使用以获得市场分析报告
            use_enhanced_analyzer = True  # 强制启用EnhancedJobAnalyzer以获得完整的市场分析
            
            # 从ResumeManager获取最新的简历分析数据
            current_resume_analysis = None
            try:
                from analyzer.resume.resume_manager import ResumeManager
                resume_manager = ResumeManager()
                current_resume_data = resume_manager.get_current_resume()
                if current_resume_data:
                    current_resume_analysis = current_resume_data
                    print(f"📋 从ResumeManager获取到简历数据: {current_resume_data.get('basic_info', {}).get('name', '未知')}")
            except Exception as e:
                print(f"⚠️ 获取简历数据失败: {e}")
                # 尝试从现有实例获取（fallback）
                if 'job_analyzer_instance' in globals() and hasattr(job_analyzer_instance, 'resume_analysis'):
                    current_resume_analysis = job_analyzer_instance.resume_analysis
            
            if use_smart_analyzer:
                print(f"💎 创建智能分层JobAnalyzer实例（GLM批量提取+DeepSeek批量评分+Claude深度分析）")
                print(f"💰 预期成本: $0.65/100个岗位")
                
                # 创建智能分析器实例 - 实际不会执行，因为use_smart_analyzer总是False
                # job_analyzer_instance = SmartJobAnalyzer()  # 已弃用
                pass
                
                # 恢复简历分析数据（如果有）
                if current_resume_analysis:
                    job_analyzer_instance.resume_analysis = current_resume_analysis
                    print("🎯 已恢复简历数据到智能分析器实例")
                    
            elif use_enhanced_analyzer:
                print(f"🚀 创建增强型JobAnalyzer实例（GLM+Claude混合模式）")
                
                # 创建增强分析器实例
                job_analyzer_instance = EnhancedJobAnalyzer(
                    extraction_provider="glm",  # GLM-4.5用于信息提取
                    analysis_provider="claude"  # Claude用于分析
                )
                
                # 恢复简历分析数据
                if current_resume_analysis:
                    job_analyzer_instance.resume_analysis = current_resume_analysis
                    print("🎯 已恢复简历数据到增强分析器实例")
            else:
                print(f"🔄 创建传统JobAnalyzer实例，模型: {ai_config['provider']}")
                
                # 创建传统分析器实例
                job_analyzer_instance = JobAnalyzer(ai_provider=ai_config['provider'])
                
                # 恢复简历分析数据
                if current_resume_analysis:
                    job_analyzer_instance.resume_analysis = current_resume_analysis
                    print("🎯 已恢复简历数据到传统分析器实例")
        else:
            # 使用现有实例，但更新最新的简历数据
            if current_resume_analysis:
                job_analyzer_instance.resume_analysis = current_resume_analysis
                print("🎯 更新现有分析器的简历数据")
            elif hasattr(job_analyzer_instance, 'resume_analysis') and job_analyzer_instance.resume_analysis:
                print("🎯 使用现有分析器中的简历数据")
            else:
                print("⚠️ 现有分析器中没有简历数据")
        
        analyzer = job_analyzer_instance
        
        # 为所有岗位初始化分析结果
        all_jobs_with_analysis = []
        
        # 使用新的批量分析方法（包含AI岗位要求总结和成本优化）
        emit_progress("🧠 启动AI岗位要求总结和智能分析...", 50)
        
        try:
            # 检查是否使用智能分层分析器
            # 使用增强分析器的分析方法（包含岗位要求总结）
            all_jobs_with_analysis = analyzer.analyze_jobs(jobs)
            
            # 市场分析已完成
            emit_progress(f"📊 市场分析完成", 80)
            
        except Exception as e:
            logger.error(f"新分析方法失败，降级到传统分析: {e}")
            # 重新初始化，避免重复数据
            all_jobs_with_analysis = []
            # 降级到传统分析方法
            for i, job in enumerate(jobs):
                progress = 50 + (i / len(jobs)) * 30
                emit_progress(f"🤖 分析第 {i+1}/{len(jobs)} 个岗位...", progress)
                
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
                
                all_jobs_with_analysis.append(job)
        
        # 7. 过滤和排序
        emit_progress("🎯 过滤和排序结果...", 85)
        # 筛选合格岗位
        filtered_jobs = analyzer.filter_and_sort_jobs(all_jobs_with_analysis, ai_config['min_score'])
        
        # 8. 保存结果
        emit_progress("💾 保存结果...", 95)
        # 使用新的保存函数，保存所有岗位
        from utils.data_saver import save_all_job_results
        save_all_job_results(all_jobs_with_analysis, filtered_jobs)  # 保存所有岗位
        
        # 9. 获取市场分析结果
        # EnhancedJobAnalyzer有完整的市场分析
        market_analysis = analyzer.get_market_analysis()
        logger.info(f"EnhancedJobAnalyzer市场分析获取: {market_analysis is not None}")
        if market_analysis:
            logger.info(f"市场分析包含技能要求: {'skill_requirements' in market_analysis}")
            logger.info(f"市场分析包含核心职责: {'core_responsibilities' in market_analysis}")
        
        # 10. 完成
        current_job.update({
            'status': 'completed',
            'end_time': datetime.now(),
            'results': filtered_jobs,
            'analyzed_jobs': all_jobs_with_analysis,  # 存储所有岗位
            'total_jobs': len(jobs),
            'analyzed_jobs_count': len(all_jobs_with_analysis),
            'qualified_jobs': len(filtered_jobs),
            'market_analysis': market_analysis  # 保存市场分析
        })
        
        emit_progress(f"✅ 任务完成! 找到 {len(filtered_jobs)} 个合适岗位", 100, {
            'results': filtered_jobs,
            'all_jobs': all_jobs_with_analysis,  # 返回所有岗位
            'market_analysis': market_analysis,  # 传递市场分析
            'stats': {
                'total': len(jobs),  # 使用原始抓取的岗位数量
                'analyzed': len(all_jobs_with_analysis),  # 分析的岗位数量
                'qualified': len(filtered_jobs)  # 合格的岗位数量
            }
        })
        
        # 发送搜索完成事件，重置前端按钮状态
        socketio.emit('search_complete', {'status': 'success', 'message': '搜索完成'})
        
    except Exception as e:
        logger.error(f"搜索任务失败: {e}")
        # 打印详细错误信息用于调试
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        
        current_job.update({
            'status': 'failed',
            'error': str(e),
            'end_time': datetime.now()
        })
        emit_progress(f"❌ 任务失败: {str(e)}", None)
        
        # 发送搜索完成事件，重置前端按钮状态
        socketio.emit('search_complete', {'status': 'failed', 'message': f'搜索失败: {str(e)}'})
        
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