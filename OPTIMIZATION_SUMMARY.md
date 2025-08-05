# AI成本优化方案总结

## 当前架构分析

### 现有三阶段流程
1. **GLM-4.5 信息提取**：逐个岗位提取结构化信息（100次调用）
2. **DeepSeek 市场分析**：批量分析所有岗位生成市场洞察（1次调用）
3. **DeepSeek 个人匹配**：逐个岗位进行匹配评分（100次调用）

**总成本**：约30元/100岗位

## 优化方案实现

### 新的四阶段流程（已实现）
1. **GLM-4.5 快速筛选**：判断岗位相关性（100次调用，极低成本）
2. **GLM-4.5 信息提取**：只提取相关岗位信息（约30次调用）
3. **DeepSeek 市场分析**：只分析相关岗位（1次调用）
4. **DeepSeek 个人匹配**：只匹配相关岗位（约30次调用）

**预期成本**：约6-8元/100岗位（节省70-75%）

## 实现细节

### 1. 新增快速筛选提示词
```python
# analyzer/prompts/extraction_prompts.py
def get_job_relevance_screening_prompt():
    # 返回简单的相关性判断提示词
    # 输出格式：{"relevant": true/false, "reason": "原因"}
```

### 2. 增强版分析器支持筛选模式
```python
# analyzer/enhanced_job_analyzer.py
class EnhancedJobAnalyzer:
    def __init__(self, screening_mode=True):
        # screening_mode: 是否启用快速筛选
```

### 3. GLM客户端优化
- 支持从reasoning_content提取筛选结果
- 处理相关性判断的特殊响应格式

## 使用方式

```python
# 启用筛选模式（推荐）
analyzer = EnhancedJobAnalyzer(
    extraction_provider="glm",
    analysis_provider="deepseek",
    screening_mode=True  # 启用快速筛选
)

# 传统全量分析模式
analyzer = EnhancedJobAnalyzer(
    extraction_provider="glm",
    analysis_provider="deepseek",
    screening_mode=False  # 禁用筛选，分析所有岗位
)
```

## 成本对比

| 模式 | GLM调用 | DeepSeek调用 | 总成本 | 节省 |
|-----|---------|------------|--------|------|
| 原始（全DeepSeek） | 0 | 201 | ¥58 | - |
| 当前（GLM+DeepSeek） | 100 | 101 | ¥30 | 48% |
| 优化（筛选模式） | 130 | 31 | ¥7 | 88% |

## 注意事项

1. **筛选准确性**：GLM的筛选可能有误判，建议定期抽查
2. **响应时间**：GLM-4.5深度思考模式可能较慢，已优化超时设置
3. **配置依赖**：筛选基于用户的求职意向配置，需确保配置准确

## 后续优化建议

1. **批量处理**：将单个岗位调用改为5-10个岗位批量处理
2. **缓存机制**：对相似岗位复用分析结果
3. **动态调整**：根据筛选率动态选择是否启用筛选模式
4. **本地模型**：考虑使用本地小模型进行初筛