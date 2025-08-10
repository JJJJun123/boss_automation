#!/usr/bin/env python3
"""
直接测试GLM客户端的筛选功能
"""

import os
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyzer.clients.glm_client import GLMClient
from analyzer.prompts.extraction_prompts import ExtractionPrompts

def test_glm_screening():
    """测试GLM筛选功能"""
    print("=" * 60)
    print("🧪 测试GLM客户端筛选功能")
    print("=" * 60)
    
    # 创建GLM客户端
    print("\n1. 初始化GLM客户端...")
    try:
        client = GLMClient()
        print("✅ GLM客户端初始化成功")
    except Exception as e:
        print(f"❌ GLM客户端初始化失败: {e}")
        return
    
    # 测试岗位
    test_job = {
        "title": "市场风险分析师",
        "company": "某银行",
        "job_description": "负责市场风险管理，需要金融背景，熟悉风险模型"
    }
    
    # 用户意向
    user_intentions = """求职意向：
- 市场风险管理相关岗位
- AI/人工智能相关岗位
- 金融科技相关岗位

不接受的岗位：
- 纯销售岗位
- 纯客服岗位"""
    
    print(f"\n2. 测试岗位：{test_job['title']}")
    print(f"3. 生成筛选提示词...")
    
    # 生成筛选提示词
    prompt = ExtractionPrompts.get_job_relevance_screening_prompt(test_job, user_intentions)
    print(f"   提示词长度：{len(prompt)} 字符")
    
    print("\n4. 调用GLM进行筛选判断...")
    
    try:
        # 调用GLM
        response = client.call_api_simple(prompt, max_tokens=200, temperature=0.1)
        print(f"\n✅ GLM响应：{response}")
        
        # 解析结果
        import json
        result = json.loads(response)
        
        print("\n" + "=" * 60)
        print("📊 筛选结果")
        print("=" * 60)
        print(f"   相关性：{'✅ 相关' if result.get('relevant') else '❌ 不相关'}")
        print(f"   原因：{result.get('reason', '未知')}")
        
        if result.get('relevant'):
            print("\n✅ 测试通过！筛选功能正常工作")
        else:
            print("\n⚠️ 警告：岗位被判断为不相关，请检查判断逻辑")
            
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_glm_screening()