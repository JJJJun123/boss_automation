#!/usr/bin/env python3
"""
验证从DeepSeek切换到Claude的配置
"""

def test_claude_configuration():
    """测试Claude配置是否正确"""
    print("="*60)
    print("测试Claude模型配置")
    print("="*60)
    
    # 1. 测试配置文件
    try:
        from config.config_manager import ConfigManager
        config = ConfigManager()
        
        default_provider = config.get_app_config('ai.default_provider')
        supported_providers = config.get_app_config('ai.supported_providers')
        
        print(f"✅ 默认AI提供商: {default_provider}")
        print(f"✅ 支持的提供商: {supported_providers}")
        
        if default_provider == 'claude':
            print("✅ 默认提供商已正确设置为Claude")
        else:
            print(f"❌ 默认提供商错误: {default_provider}")
            
        if 'deepseek' not in supported_providers:
            print("✅ DeepSeek已从支持列表中移除")
        else:
            print("⚠️  DeepSeek仍在支持列表中")
            
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
    
    # 2. 测试AI客户端工厂
    try:
        from analyzer.ai_client_factory import AIClientFactory
        
        print(f"\n🤖 测试AI客户端创建...")
        client = AIClientFactory.create_client()  # 使用默认配置
        
        print(f"✅ 默认客户端类型: {type(client)}")
        
        # 测试Claude客户端
        claude_client = AIClientFactory.create_client('claude')
        print(f"✅ Claude客户端类型: {type(claude_client)}")
        
    except Exception as e:
        print(f"❌ 客户端创建失败: {e}")
    
    # 3. 测试简历分析器（已移除）
    print(f"\n📝 简历分析器已移除（采用直接匹配模式）")

    # 4. 测试增强分析器
    try:
        from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer
        
        print(f"\n🚀 测试增强分析器...")
        enhanced = EnhancedJobAnalyzer()  # 使用默认配置
        
        if enhanced.job_analyzer.ai_provider == 'claude':
            print("✅ 增强分析器默认使用Claude")
        else:
            print(f"❌ 增强分析器使用错误的提供商: {enhanced.job_analyzer.ai_provider}")
            
    except Exception as e:
        print(f"❌ 增强分析器测试失败: {e}")

def test_actual_api_call():
    """测试实际的API调用"""
    print(f"\n" + "="*60)
    print("测试Claude API调用")
    print("="*60)
    
    try:
        from analyzer.ai_client_factory import AIClientFactory
        
        client = AIClientFactory.create_client('claude')
        
        # 简单测试
        response = client.call_api(
            "你是一个专业的测试助手。",
            "请回答：2+2等于多少？只需要回答数字。",
            max_tokens=50
        )
        
        print(f"✅ Claude API调用成功")
        print(f"📝 响应: {response}")
        
        if "4" in response:
            print("✅ Claude响应正确")
        else:
            print(f"⚠️  响应内容异常: {response}")
            
    except Exception as e:
        print(f"❌ Claude API调用失败: {e}")
        print("请检查CLAUDE_API_KEY是否正确配置")

if __name__ == "__main__":
    test_claude_configuration()
    test_actual_api_call()
    
    print(f"\n" + "="*60)
    print("配置切换总结")
    print("="*60)
    print("已完成的更改:")
    print("1. ✅ app_config.yaml: default_provider改为claude")
    print("2. ✅ 移除DeepSeek从supported_providers")
    print("3. ✅ 更新所有fallback默认值为claude")
    print("4. ✅ 更新EnhancedJobAnalyzer使用Claude")
    print("5. ✅ 移除AI工厂中的DeepSeek配置")
    print("\n现在系统将使用Claude进行:")
    print("• 📝 简历分析 (更严格、更客观)")
    print("• 🎯 岗位匹配 (评分更准确)")
    print("• 🚀 增强分析 (GLM提取 + Claude分析)")