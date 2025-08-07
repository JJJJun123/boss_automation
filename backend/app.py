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
from analyzer.job_analyzer import JobAnalyzer
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
        
        # 获取可用的AI模型
        from analyzer.ai_client_factory import AIClientFactory
        available_models = AIClientFactory.get_available_models()
        
        return jsonify({
            'search': search_config,
            'ai': ai_config,
            'app': config_manager.get_app_config(),
            'available_ai_models': available_models
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
        global job_analyzer_instance
        if 'job_analyzer_instance' not in globals():
            # 获取AI配置
            try:
                config_manager = ConfigManager()
                ai_config = config_manager.get_app_config('ai', {})
                use_enhanced_analyzer = ai_config.get('use_enhanced_analyzer', True)
                
                if use_enhanced_analyzer:
                    print("🚀 创建增强型简历分析器（GLM+DeepSeek混合模式）")
                    job_analyzer_instance = EnhancedJobAnalyzer(
                        extraction_provider="glm",
                        analysis_provider="deepseek"
                    )
                else:
                    print("🔄 创建传统简历分析器")
                    job_analyzer_instance = JobAnalyzer()
            except Exception as e:
                print(f"⚠️ 配置读取失败，使用默认增强分析器: {e}")
                job_analyzer_instance = EnhancedJobAnalyzer(
                    extraction_provider="glm",
                    analysis_provider="deepseek"
                )
        
        # 设置简历分析数据（兼容两种分析器）
        if hasattr(job_analyzer_instance, 'set_resume_analysis'):
            job_analyzer_instance.set_resume_analysis(ai_analysis)
        else:
            job_analyzer_instance.resume_analysis = ai_analysis
        
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
        selected_city = params.get('city', 'shanghai')  # 默认上海
        ai_model = params.get('ai_model')  # 用户选择的AI模型
        
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
        
        # 5. AI分析 - 支持动态模型选择
        global job_analyzer_instance
        
        # 如果用户指定了AI模型，或者没有现有实例，创建新的分析器
        if ai_model or 'job_analyzer_instance' not in globals():
            # 检查是否启用混合AI模式（GLM+DeepSeek）
            use_enhanced_analyzer = ai_config.get('use_enhanced_analyzer', True)  # 默认启用
            
            if use_enhanced_analyzer:
                print(f"🚀 创建增强型JobAnalyzer实例（GLM+DeepSeek混合模式）")
                
                # 保存之前的简历分析数据（如果有）
                previous_resume_analysis = None
                if 'job_analyzer_instance' in globals() and hasattr(job_analyzer_instance, 'resume_analysis'):
                    previous_resume_analysis = job_analyzer_instance.resume_analysis
                
                # 创建增强分析器实例
                job_analyzer_instance = EnhancedJobAnalyzer(
                    extraction_provider="glm",  # GLM-4.5用于信息提取
                    analysis_provider="deepseek"  # DeepSeek用于分析
                )
                
                # 恢复简历分析数据
                if previous_resume_analysis:
                    job_analyzer_instance.resume_analysis = previous_resume_analysis
                    print("🎯 已恢复简历数据到增强分析器实例")
            else:
                print(f"🔄 创建传统JobAnalyzer实例，模型: {ai_model or ai_config['provider']}")
                
                # 保存之前的简历分析数据（如果有）
                previous_resume_analysis = None
                if 'job_analyzer_instance' in globals() and hasattr(job_analyzer_instance, 'resume_analysis'):
                    previous_resume_analysis = job_analyzer_instance.resume_analysis
                
                # 创建传统分析器实例
                if ai_model:
                    job_analyzer_instance = JobAnalyzer(model_name=ai_model)
                else:
                    job_analyzer_instance = JobAnalyzer(ai_provider=ai_config['provider'])
                
                # 恢复简历分析数据
                if previous_resume_analysis:
                    job_analyzer_instance.resume_analysis = previous_resume_analysis
                    print("🎯 已恢复简历数据到传统分析器实例")
        else:
            # 使用现有实例
            if hasattr(job_analyzer_instance, 'resume_analysis') and job_analyzer_instance.resume_analysis:
                print("🎯 使用已加载的简历数据进行智能匹配")
        
        analyzer = job_analyzer_instance
        
        # 为所有岗位初始化分析结果
        all_jobs_with_analysis = []
        
        # 使用新的批量分析方法（包含AI岗位要求总结和成本优化）
        emit_progress("🧠 启动AI岗位要求总结和智能分析...", 50)
        
        try:
            # 使用新的分析方法（包含岗位要求总结）
            all_jobs_with_analysis = analyzer.analyze_jobs(jobs)
            
            # 市场分析已完成，不再需要单独的成本报告
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
        
        # 6. 过滤和排序
        emit_progress("🎯 过滤和排序结果...", 85)
        # 筛选合格岗位
        filtered_jobs = analyzer.filter_and_sort_jobs(all_jobs_with_analysis, ai_config['min_score'])
        
        # 7. 保存结果
        emit_progress("💾 保存结果...", 95)
        # 使用新的保存函数，保存所有岗位
        from utils.data_saver import save_all_job_results
        save_all_job_results(all_jobs_with_analysis, filtered_jobs)  # 保存所有岗位
        
        # 8. 获取市场分析结果
        market_analysis = analyzer.get_market_analysis() if analyzer else None
        
        # 9. 完成
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