# 多AI模型支持功能

## 功能概述

Boss直聘智能求职助手现在支持多个AI模型，用户可以根据需求和预算选择最适合的AI分析模型。

## 支持的AI模型

### 1. DeepSeek 系列（推荐，经济实用）
- **deepseek-chat** (默认)：经济实用，成本最低，适合大量岗位分析
- **deepseek-reasoner**：推理增强版本，分析更深入

### 2. Claude 系列（高质量）
- **claude-3-5-sonnet-20241022**：Claude 4 Sonnet，最高质量分析
- **claude-3-haiku-20240307**：快速高效的分析选项

### 3. GPT 系列（OpenAI）
- **gpt-4o**：OpenAI最新模型，平衡性能和成本
- **gpt-4o-mini**：轻量版本，更快更经济

### 4. Gemini 系列（Google）
- **gemini-pro**：Google的平衡选择
- **gemini-pro-vision**：支持视觉理解的版本

## 使用方法

### Web界面
1. 访问 http://localhost:5000
2. 在搜索表单中找到"🤖 AI分析模型"下拉框
3. 选择想要使用的模型
4. 开始搜索和分析

### API调用
```python
from analyzer.ai_client_factory import AIClientFactory

# 创建指定模型的客户端
client = AIClientFactory.create_client('deepseek', 'deepseek-chat')

# 分析岗位匹配度
result = client.analyze_job_match(job_info, user_requirements)
```

## 配置说明

### API密钥配置 (config/secrets.env)
```bash
DEEPSEEK_API_KEY=your_deepseek_api_key
CLAUDE_API_KEY=your_claude_api_key
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
```

### 默认模型设置 (config/user_preferences.yaml)
```yaml
ai_analysis:
  provider: "deepseek"
  model: "deepseek-chat"    # 默认使用deepseek-chat模型
```

### 应用配置 (config/app_config.yaml)
```yaml
ai:
  models:
    deepseek:
      model_name: "deepseek-chat"
      available_models:
        - "deepseek-chat"
        - "deepseek-reasoner"
    claude:
      model_name: "claude-3-5-sonnet-20241022"
      available_models:
        - "claude-3-5-sonnet-20241022"
        - "claude-3-haiku-20240307"
    # ... 其他模型配置
```

## 成本对比

| 模型 | 相对成本 | 分析质量 | 推荐场景 |
|------|----------|----------|----------|
| deepseek-chat | ⭐ | ⭐⭐⭐⭐ | 日常大量分析，默认选择 |
| deepseek-reasoner | ⭐⭐ | ⭐⭐⭐⭐⭐ | 需要深度推理的复杂岗位 |
| claude-3-5-sonnet | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 高质量分析，预算充足 |
| gpt-4o | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 平衡选择，OpenAI生态 |
| gemini-pro | ⭐⭐⭐ | ⭐⭐⭐⭐ | Google生态用户 |

## 技术实现

### 1. AI客户端工厂模式
- `AIClientFactory` 统一管理所有AI客户端
- 支持动态创建和配置不同的AI模型客户端

### 2. 配置管理
- 统一的配置文件管理系统
- 支持热更新和动态配置

### 3. 前端集成
- Web界面直接支持模型选择
- 实时更新可用模型列表

### 4. API支持
- RESTful API支持模型配置获取和更新
- WebSocket实时通信支持

## 测试验证

运行测试脚本验证功能：
```bash
python test_ai_models.py
```

## 注意事项

1. **API密钥**：需要在 `config/secrets.env` 中配置相应的API密钥
2. **成本控制**：建议从经济实用的DeepSeek模型开始使用
3. **质量要求**：对于重要岗位分析，可选择Claude或GPT高质量模型
4. **网络连接**：确保网络能够访问相应的AI服务API

## 更新日志

- **2025-08-01**: 实现多AI模型支持功能
  - 添加 DeepSeek Chat/Reasoner 支持
  - 添加 Claude 4 Sonnet 支持  
  - 添加 GPT-4o 支持
  - 添加 Gemini Pro 支持
  - 设置 DeepSeek Chat 为默认模型
  - 完善配置管理和前端选择界面