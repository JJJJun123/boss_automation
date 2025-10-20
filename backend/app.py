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
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"])

# 配置SocketIO
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='threading',
                   ping_timeout=60,
                   ping_interval=25)

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
        
        # 简化处理 - 直接解析文件内容
        try:
            # 根据文件类型进行解析
            if file.filename.lower().endswith('.pdf'):
                import PyPDF2
                from io import BytesIO
                pdf_reader = PyPDF2.PdfReader(BytesIO(file.read()))
                resume_text = ""
                for page in pdf_reader.pages:
                    resume_text += page.extract_text()
            elif file.filename.lower().endswith(('.docx', '.doc')):
                import docx
                from io import BytesIO
                doc = docx.Document(BytesIO(file.read()))
                resume_text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            else:  # 默认作为文本文件
                resume_text = file.read().decode('utf-8')
                
            if not resume_text.strip():
                raise Exception("文件内容为空")
                
        except Exception as e:
            logger.error(f"文件解析错误: {str(e)}")
            return jsonify({
                'success': False, 
                'error': f'文件解析失败: {str(e)}'
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
        
        # 简化处理 - 只提取关键信息，不进行AI分析
        logger.info("使用简化模式处理简历，不进行AI分析")
        
        # 不进行任何关键词提取或分析
        
        # 构建简化的简历数据
        resume_data = {
            'name': file.filename.split('.')[0] if file.filename else '用户',  # 使用文件名作为标识
            'resume_text': resume_text,  # 保存原文用于匹配
            'filename': file.filename,
            'upload_time': datetime.now().isoformat()
        }
        
        # 存储到session
        session['resume_data'] = resume_data
        session['resume_summary'] = {
            'length': len(resume_text),
            'has_text': True,
            'analyzed': False,  # 标记为未进行AI分析
            'saved_to_file': False
        }
        
        logger.info(f"简历上传完成: {resume_data['name']}")
        
        return jsonify({
            'success': True,
            'resume_data': resume_data,
            'message': '简历上传成功，已提取关键信息'
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

        # 简化版本：只清理session，无持久化文件
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"删除简历失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/resume/info', methods=['GET'])
def get_resume_info():
    """获取当前保存的简历信息（简化版本）"""
    try:
        # 简化版本：从session获取简历信息
        if 'resume_data' in session:
            resume_data = session['resume_data']
            return jsonify({
                'success': True,
                'has_resume': True,
                'resume_info': {
                    'name': resume_data.get('name', '未知'),
                    'skills': resume_data.get('skills', []),
                    'experience_years': resume_data.get('experience_years', '0年'),
                    'filename': resume_data.get('filename', ''),
                    'current_position': resume_data.get('current_position', '待识别')
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
    """更新求职意向（简化版本）"""
    try:
        data = request.json
        intentions = data.get('intentions', [])
        
        # 简化版本：直接更新session中的求职意向
        if 'resume_data' not in session:
            return jsonify({
                'success': False,
                'error': '请先上传简历'
            })
        
        # 更新session中的求职意向
        session['resume_data']['job_intentions'] = intentions
        session.modified = True  # 标记session已修改
        
        return jsonify({
            'success': True,
            'message': '求职意向已更新'
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

        # 1. 如果前端传来了AI provider参数，先更新配置
        if 'ai_provider' in params:
            ai_provider = params['ai_provider']
            logger.info(f"🤖 用户选择AI服务商: {ai_provider}")
            config_manager.set_user_preference('ai_analysis.provider', ai_provider)
            config_manager.save_user_preferences()
            emit_progress(f"🤖 AI服务商: {ai_provider.upper()}", 8)

        # 2. 从前端参数获取搜索配置，如果没有则使用默认配置
        search_config = config_manager.get_search_config()
        ai_config = config_manager.get_ai_config()

        # 使用前端传来的参数覆盖配置文件中的值
        keyword = params.get('keyword', search_config['keyword'])
        max_jobs = params.get('max_jobs', search_config['max_jobs'])
        selected_city = params.get('city', 'shanghai')  # 默认上海
        
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
        
        # 5. 检查是否有简历数据进行匹配优化
        has_session_resume = session_data.get('has_resume_data', False)
        
        # 6. AI岗位分析 - 恢复原有的深度分析功能
        emit_progress("🤖 开始AI岗位分析...", 80)
        
        # 创建JobAnalyzer实例
        global job_analyzer_instance
        
        # 如果没有现有实例，创建新的分析器
        if 'job_analyzer_instance' not in globals():
            # 使用标准的JobAnalyzer进行岗位分析
            from analyzer.job_analyzer import JobAnalyzer
            print(f"🔄 创建JobAnalyzer实例，模型: {ai_config['provider']}")
            job_analyzer_instance = JobAnalyzer(ai_provider=ai_config['provider'])
        
        analyzer = job_analyzer_instance
        
        # 使用AI进行岗位分析
        emit_progress("🧠 启动AI岗位匹配分析...", 82)
        
        try:
            # 使用JobAnalyzer的analyze_jobs方法进行批量分析
            analyzed_jobs = analyzer.analyze_jobs(jobs)
            emit_progress(f"📈 AI分析完成", 90)
            
        except Exception as e:
            logger.error(f"AI分析失败，使用降级分析: {e}")
            # 降级到逐个分析
            analyzed_jobs = []
            for i, job in enumerate(jobs):
                progress = 82 + (i / len(jobs)) * 8  # 82-90
                emit_progress(f"🤖 分析第 {i+1}/{len(jobs)} 个岗位...", progress)

                try:
                    if has_session_resume and hasattr(analyzer, 'analyze_job_match'):
                        # 有简历时使用智能匹配，直接传递原始简历文本
                        resume_data = session_data.get('resume_data', {})
                        resume_text = resume_data.get('resume_text', '')
                        # 构建简历分析数据（包含原始文本）
                        resume_analysis = {'resume_text': resume_text}
                        analysis_result = analyzer.analyze_job_match(job, resume_analysis)
                    else:
                        # 无简历时使用简单匹配
                        analysis_result = analyzer.analyze_job_match_simple(job, analyzer.user_requirements)
                    
                    job['analysis'] = analysis_result
                except Exception as e:
                    logger.error(f"分析岗位失败: {e}")
                    job['analysis'] = {
                        "score": 0,
                        "overall_score": 0,
                        "recommendation": "分析失败",
                        "reason": f"分析过程中出错: {e}",
                        "summary": "无法分析此岗位"
                    }
                
                analyzed_jobs.append(job)
            
        # 7. 过滤和排序
        emit_progress("🎯 过滤和排序结果...", 92)
        qualified_jobs = analyzer.filter_and_sort_jobs(analyzed_jobs, ai_config['min_score'])
        
        # 8. 保存结果
        emit_progress("💾 保存结果...", 95)
        from utils.data_saver import save_all_job_results
        save_all_job_results(analyzed_jobs, qualified_jobs)
        
        # 9. 生成并获取市场分析
        market_analysis = None
        logger.info(f"开始生成市场分析，岗位数量: {len(jobs)}")
        if hasattr(analyzer, 'generate_market_analysis') and hasattr(analyzer, 'get_market_analysis'):
            try:
                # 先生成市场分析
                logger.info("调用 analyzer.generate_market_analysis...")
                analyzer.generate_market_analysis(jobs)
                # 再获取分析结果
                logger.info("调用 analyzer.get_market_analysis...")
                market_analysis = analyzer.get_market_analysis()
                logger.info(f"市场分析生成完成: {market_analysis is not None}")
                if market_analysis:
                    logger.info(f"市场分析数据结构: {list(market_analysis.keys()) if isinstance(market_analysis, dict) else type(market_analysis)}")
            except Exception as e:
                logger.error(f"市场分析生成失败: {e}")
                import traceback
                logger.error(f"详细错误: {traceback.format_exc()}")
                market_analysis = None
        else:
            logger.warning("analyzer没有generate_market_analysis或get_market_analysis方法")
        
        # 10. 完成
        current_job.update({
            'status': 'completed',
            'end_time': datetime.now(),
            'results': qualified_jobs,
            'analyzed_jobs': analyzed_jobs,
            'total_jobs': len(jobs),
            'analyzed_jobs_count': len(analyzed_jobs),
            'qualified_jobs': len(qualified_jobs),
            'market_analysis': market_analysis
        })
        
        emit_progress(f"✅ 任务完成! 找到 {len(qualified_jobs)} 个合适岗位", 100, {
            'results': qualified_jobs,
            'all_jobs': analyzed_jobs,
            'market_analysis': market_analysis,
            'stats': {
                'total': len(jobs),
                'analyzed': len(analyzed_jobs),
                'qualified': len(qualified_jobs)
            }
        })
        
        # 发送搜索完成事件，重置前端按钮状态
        socketio.emit('search_complete', {'status': 'success', 'message': '搜索完成'})
        return
        
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
                port=3001, 
                debug=True,
                use_reloader=False,
                allow_unsafe_werkzeug=True)  # 避免重载时的问题