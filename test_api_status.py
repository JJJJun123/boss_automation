#!/usr/bin/env python3
"""
检测各个AI API的可用性和剩余额度
"""

import os
import sys
import requests
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config_manager import ConfigManager

def test_deepseek_api():
    """测试DeepSeek API"""
    print("🔍 测试DeepSeek API...")
    
    try:
        config_manager = ConfigManager()
        api_key = config_manager.get_secret('DEEPSEEK_API_KEY')
        
        if not api_key or api_key == "your_deepseek_api_key_here":
            print("❌ DeepSeek API key未配置")
            return False
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": "测试连接，请回复'OK'"}
            ],
            "max_tokens": 10,
            "temperature": 0
        }
        
        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        print(f"DeepSeek状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ DeepSeek API可用")
            print(f"响应: {result.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')}")
            return True
        elif response.status_code == 401:
            print("❌ DeepSeek API key无效或过期")
            return False
        elif response.status_code == 429:
            print("⚠️ DeepSeek API请求频率限制")
            return False
        else:
            print(f"❌ DeepSeek API错误: {response.status_code}")
            try:
                error_info = response.json()
                print(f"错误详情: {error_info}")
            except:
                print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ DeepSeek API测试失败: {e}")
        return False

def test_glm_api():
    """测试GLM API"""
    print("\n🔍 测试GLM API...")
    
    try:
        config_manager = ConfigManager()
        api_key = config_manager.get_secret('GLM_API_KEY')
        
        if not api_key or api_key == "your_glm_api_key_here":
            print("❌ GLM API key未配置")
            return False
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            "model": "glm-4-flash",
            "messages": [
                {"role": "user", "content": "测试连接，请回复'OK'"}
            ],
            "max_tokens": 10,
            "temperature": 0
        }
        
        response = requests.post(
            'https://open.bigmodel.cn/api/paas/v4/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        print(f"GLM状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ GLM API可用")
            print(f"响应: {result.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')}")
            return True
        elif response.status_code == 401:
            print("❌ GLM API key无效或过期")
            return False
        elif response.status_code == 429:
            print("⚠️ GLM API请求频率限制或余额不足")
            return False
        else:
            print(f"❌ GLM API错误: {response.status_code}")
            try:
                error_info = response.json()
                print(f"错误详情: {error_info}")
            except:
                print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ GLM API测试失败: {e}")
        return False

def test_claude_api():
    """测试Claude API"""
    print("\n🔍 测试Claude API...")
    
    try:
        config_manager = ConfigManager()
        api_key = config_manager.get_secret('CLAUDE_API_KEY')
        
        if not api_key or not api_key.startswith('sk-ant-'):
            print("❌ Claude API key未配置或格式错误")
            return False
        
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        data = {
            "model": "claude-3-haiku-20240307",
            "messages": [
                {"role": "user", "content": "测试连接，请回复'OK'"}
            ],
            "max_tokens": 10
        }
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=30
        )
        
        print(f"Claude状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Claude API可用")
            content = result.get('content', [{}])
            if content:
                print(f"响应: {content[0].get('text', 'N/A')}")
            return True
        elif response.status_code == 401:
            print("❌ Claude API key无效")
            return False
        elif response.status_code == 429:
            print("⚠️ Claude API请求频率限制")
            return False
        else:
            print(f"❌ Claude API错误: {response.status_code}")
            try:
                error_info = response.json()
                print(f"错误详情: {error_info}")
            except:
                print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Claude API测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print(f"🧪 AI API状态检测 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    results = {}
    
    # 测试各个API
    results['deepseek'] = test_deepseek_api()
    results['glm'] = test_glm_api()
    results['claude'] = test_claude_api()
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    
    available_apis = []
    for api_name, is_available in results.items():
        status = "✅ 可用" if is_available else "❌ 不可用"
        print(f"   {api_name.upper()}: {status}")
        if is_available:
            available_apis.append(api_name)
    
    if not available_apis:
        print("\n⚠️ 所有API都不可用，请检查配置或余额！")
    else:
        print(f"\n✅ 可用的API: {', '.join(available_apis).upper()}")
        
        # 给出建议
        if 'deepseek' in available_apis and 'glm' in available_apis:
            print("💡 建议: GLM+DeepSeek混合模式可正常使用")
        elif 'deepseek' in available_apis:
            print("💡 建议: 可使用DeepSeek单一模式")
        elif 'claude' in available_apis:
            print("💡 建议: 可切换到Claude模式")

if __name__ == "__main__":
    main()