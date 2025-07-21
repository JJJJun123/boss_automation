#!/usr/bin/env python3
"""
简化的测试应用
"""

import sys
import os
import logging

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from flask import Flask, jsonify
from flask_cors import CORS

# 创建Flask应用
app = Flask(__name__)
CORS(app)

# 条件导入真实Playwright爬虫
try:
    from crawler.real_playwright_spider import search_with_real_playwright
    REAL_PLAYWRIGHT_AVAILABLE = True
    logger.info("✅ 真实Playwright爬虫已加载")
except ImportError as e:
    logger.warning(f"⚠️ 真实Playwright爬虫不可用: {e}")
    REAL_PLAYWRIGHT_AVAILABLE = False
    
    def search_with_real_playwright(*args, **kwargs):
        logger.error("❌ Playwright未安装")
        return []

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>Boss直聘测试</title></head>
    <body>
        <h1>🎭 Boss直聘自动化测试</h1>
        <p>✅ 应用运行正常</p>
        <p>✅ Playwright可用: {}</p>
        <button onclick="testSearch()">测试搜索</button>
        <div id="result"></div>
        
        <script>
        async function testSearch() {{
            document.getElementById('result').innerHTML = '搜索中...';
            try {{
                const response = await fetch('/api/test-search');
                const data = await response.json();
                document.getElementById('result').innerHTML = 
                    '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
            }} catch (e) {{
                document.getElementById('result').innerHTML = '错误: ' + e.message;
            }}
        }}
        </script>
    </body>
    </html>
    '''.format(REAL_PLAYWRIGHT_AVAILABLE)

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy',
        'playwright_available': REAL_PLAYWRIGHT_AVAILABLE
    })

@app.route('/api/test-search')
def test_search():
    logger.info("🔍 开始测试搜索...")
    
    if REAL_PLAYWRIGHT_AVAILABLE:
        try:
            jobs = search_with_real_playwright('数据分析', 'shanghai', 2)
            return jsonify({
                'success': True,
                'jobs_found': len(jobs),
                'jobs': jobs[:2],  # 只返回前2个
                'source': 'real_playwright'
            })
        except Exception as e:
            logger.error(f"❌ 搜索失败: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'source': 'real_playwright'
            })
    else:
        return jsonify({
            'success': False,
            'error': 'Playwright不可用',
            'source': 'fallback'
        })

if __name__ == '__main__':
    logger.info("🚀 启动测试应用...")
    app.run(host='127.0.0.1', port=5002, debug=True)