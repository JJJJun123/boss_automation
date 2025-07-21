#!/usr/bin/env python3
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>✅ 应用运行正常</h1><p><a href="/api/test">测试API</a></p>'

@app.route('/api/test')
def test():
    return jsonify({'status': 'ok', 'message': '测试成功'})

if __name__ == '__main__':
    print('🚀 启动简单测试应用...')
    app.run(host='127.0.0.1', port=5003, debug=False)