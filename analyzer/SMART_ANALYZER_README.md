# 智能分层岗位分析器 (SmartJobAnalyzer)

## 概述

SmartJobAnalyzer 是一个创新的AI分析系统，通过智能分层处理策略，将100个岗位的AI分析成本从$1-2降低到$0.65，同时保持高质量的分析结果。

## 核心特性

### 三层智能处理架构

1. **批量提取层（GLM-4.5）** - $0.0005/岗位
   - 批量处理10个岗位/次
   - 提取关键信息：技能要求、经验、学历等
   - 智能缓存，避免重复处理

2. **批量评分层（DeepSeek）** - $0.001/岗位  
   - 批量评分，快速筛选
   - 多维度评分系统
   - 识别TOP候选岗位

3. **深度分析层（Claude/DeepSeek）** - $0.05/岗位
   - 仅分析TOP 10岗位
   - 个性化匹配分析
   - 面试准备建议

### 成本优化策略

```
传统方案：100个岗位 × $0.02/岗位 = $2.00
智能分层：
  - 批量提取：100个岗位 × $0.0005 = $0.05
  - 批量评分：100个岗位 × $0.001 = $0.10
  - 深度分析：10个岗位 × $0.05 = $0.50
  总成本：$0.65（节省67.5%）
```

## 使用方法

### 1. 基本使用

```python
from analyzer.smart_job_analyzer import SmartJobAnalyzer

# 创建分析器
analyzer = SmartJobAnalyzer()

# 分析岗位
jobs = [...]  # 岗位列表
resume = {...}  # 用户简历（可选）

result = analyzer.analyze_jobs_smart(jobs, resume)
```

### 2. 启用智能分析器

在 `config/app_config.yaml` 中配置：

```yaml
ai:
  use_smart_analyzer: true  # 启用智能分层分析
  smart_batch_size: 10      # 批处理大小
  smart_top_n: 10          # TOP岗位数量
  smart_cache_days: 30     # 缓存有效期
```

### 3. 在Web应用中使用

智能分析器已集成到backend，会根据配置自动选择：

- `use_smart_analyzer: true` - 使用智能分层分析器
- `use_enhanced_analyzer: true` - 使用增强分析器（GLM+DeepSeek）
- 两者都为false - 使用传统分析器

## 返回结果格式

```python
{
    "total_jobs": 100,                    # 总岗位数
    "analysis_time": "2024-01-20T10:30:00",
    "all_jobs_with_scores": [...],        # 所有岗位及评分
    "top_jobs_detailed": [...],           # TOP岗位深度分析
    "statistics": {
        "average_score": 6.5,
        "high_match_count": 10,
        "medium_match_count": 30,
        "low_match_count": 60
    },
    "cost_analysis": {
        "total_api_calls": 22,
        "cache_hits": 20,
        "estimated_cost": "$0.65"
    }
}
```

## 缓存系统

- **位置**：`data/cache/extracted/` 
- **格式**：JSON文件，以岗位ID命名
- **有效期**：30天（可配置）
- **命中率**：典型场景下70-85%

## 性能优化建议

1. **批处理大小**：建议10个岗位/批，平衡延迟和成本
2. **TOP数量**：建议10-15个，覆盖主要候选岗位
3. **缓存策略**：定期清理过期缓存，使用 `cleanup_old_cache()`

## 错误处理

- GLM不可用时自动降级到DeepSeek
- Claude不可用时使用DeepSeek进行深度分析
- API调用失败时使用默认值，不中断流程

## 测试

```bash
# 简单功能测试
python test_smart_simple.py

# 完整测试（需要配置API密钥）
python test_smart_analyzer.py
```

## 注意事项

1. 需要配置相应的API密钥（GLM、DeepSeek、Claude）
2. Claude为可选，不配置时会使用DeepSeek替代
3. 首次运行会较慢，后续运行会利用缓存加速
4. 建议定期清理缓存以节省磁盘空间

## 成本对比

| 方案 | 100个岗位成本 | 处理时间 | 分析质量 |
|------|--------------|----------|----------|
| 传统单个分析 | $2.00 | 10-15分钟 | ★★★☆☆ |
| 智能分层分析 | $0.65 | 5-8分钟 | ★★★★☆ |
| 带缓存的智能分析 | $0.20 | 2-3分钟 | ★★★★☆ |

## 未来优化方向

1. 支持更多AI模型（如本地模型）
2. 智能调整批处理大小
3. 基于用户反馈的动态评分优化
4. 分布式处理支持