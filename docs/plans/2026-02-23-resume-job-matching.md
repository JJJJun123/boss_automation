# Boss 直聘岗位匹配重构 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 删除市场分析旁路，重构为两阶段流水线（GLM 类型筛选 + 主力模型简历匹配），结果按 1-10 分排序展示。

**Architecture:** 复用现有 Flask + Playwright + AIClientFactory 骨架。`EnhancedJobAnalyzer.analyze_jobs()` 改为两阶段同步流水线：`_call_ai_for_screening()` 负责 GLM 类型过滤，`_call_ai_for_matching()` 负责主力模型简历匹配，两个方法均可通过 `unittest.mock.patch.object` 替换，保证测试不依赖真实 API。

**Tech Stack:** Python 3.x, Flask, Flask-SocketIO, Playwright, GLM-4.6, DeepSeek/Claude, pytest

---

## 关键文件速查

| 文件                                       | 操作                                                   |
| ------------------------------------------ | ------------------------------------------------------ |
| `analyzer/prompts/job_analysis_prompts.py` | 追加模块级常量 `RESUME_MATCH_PROMPT`                   |
| `analyzer/prompts/extraction_prompts.py`   | `get_job_relevance_screening_prompt` 确认无简历引用    |
| `analyzer/enhanced_job_analyzer.py`        | 替换 `analyze_jobs`，新增 3 个方法，注释掉市场认知阶段 |
| `backend/app.py`                           | 删除 474-491 行市场分析块                              |
| `backend/templates/index.html`             | 删除市场分析 HTML，更新岗位卡片                        |
| `backend/static/js/`                       | 删除 market_analysis WebSocket 监听                    |

**不动（保留）：**

- `crawler/unified_crawler_interface.py`
- `analyzer/ai_client_factory.py`
- `config/config_manager.py`
- `analyzer/prompts/extraction_prompts.py`（仅确认，不改）

---

### Task 1: 建立测试目录 + 添加 RESUME_MATCH_PROMPT

**Files:**

- Create: `tests/__init__.py`
- Create: `tests/test_prompts.py`
- Modify: `analyzer/prompts/job_analysis_prompts.py`（在文件末尾追加）

**Step 1: 创建空文件 `tests/__init__.py`**

```bash
touch tests/__init__.py
```

**Step 2: 写失败测试**

```python
# tests/test_prompts.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.prompts.job_analysis_prompts import RESUME_MATCH_PROMPT
from analyzer.prompts.extraction_prompts import ExtractionPrompts


def test_resume_match_prompt_has_required_placeholders():
    for field in ["{resume_text}", "{job_title}", "{company}", "{salary}",
                  "{description}", "{requirements}"]:
        assert field in RESUME_MATCH_PROMPT, f"Missing placeholder: {field}"


def test_resume_match_prompt_requests_json_output():
    for key in ["score", "match_highlights", "gaps", "summary"]:
        assert key in RESUME_MATCH_PROMPT, f"Missing JSON output key: {key}"


def test_screening_prompt_no_resume_reference():
    """筛选 prompt 只判断岗位类型与关键词的关系，不得引用简历。"""
    job_data = {
        "title": "数据分析师",
        "company": "测试公司",
        "job_description": "负责数据分析工作，要求熟悉Python和SQL"
    }
    prompt = ExtractionPrompts.get_job_relevance_screening_prompt(job_data, "数据分析")
    assert "简历" not in prompt, "Screening prompt must NOT reference resume"
```

**Step 3: 运行测试，确认失败**

```bash
pytest tests/test_prompts.py -v
```

预期：`FAILED` — `ImportError: cannot import name 'RESUME_MATCH_PROMPT'`

**Step 4: 在 `analyzer/prompts/job_analysis_prompts.py` 末尾追加模块级常量**

在文件最后一行（第 357 行）之后追加：

```python


# 模块级常量：简历匹配 prompt（供 EnhancedJobAnalyzer 两阶段流水线使用）
RESUME_MATCH_PROMPT = """你是一个严格的招聘评估专家。给你一份求职简历和一个招聘JD，请评估匹配程度。

【简历】
{resume_text}

【岗位】
职位：{job_title}
公司：{company}
薪资：{salary}
岗位描述：{description}
任职要求：{requirements}

请严格按以下JSON格式返回（不要包含其他内容）：
{{
  "score": <1-10的整数，10表示完美匹配>,
  "match_highlights": [<最多3条匹配亮点，字符串列表>],
  "gaps": [<最多3条关键差距，字符串列表>],
  "summary": "<一句话综合评价>"
}}

评分标准：
- 9-10: 完全符合，强烈推荐
- 7-8: 大部分符合，值得重点投递
- 5-6: 部分符合，可以投递但需补强
- 3-4: 匹配度低，建议低优先级
- 1-2: 基本不符合"""
```

**Step 5: 运行测试，确认 3 个 PASS**

```bash
pytest tests/test_prompts.py -v
```

预期：3 个 PASSED（`test_screening_prompt_no_resume_reference` 本来就通过，因为现有 prompt 没有"简历"字样）

**Step 6: Commit**

```bash
git add tests/__init__.py tests/test_prompts.py analyzer/prompts/job_analysis_prompts.py
git commit -m "feat: add RESUME_MATCH_PROMPT; establish test infrastructure"
```

---

### Task 2: 重构 EnhancedJobAnalyzer 为两阶段同步流水线

**Files:**

- Create: `tests/test_enhanced_job_analyzer.py`
- Modify: `analyzer/enhanced_job_analyzer.py`

**Step 1: 写失败测试**

```python
# tests/test_enhanced_job_analyzer.py
import sys, os, inspect
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer

SAMPLE_JOBS = [{
    "title": "数据分析师",
    "company": "测试公司",
    "salary": "15-25K",
    "job_description": "负责数据分析和报表制作，要求熟悉Python、SQL"
}]
SAMPLE_RESUME = "拥有3年数据分析经验，熟悉Python和SQL"


def test_analyze_jobs_accepts_resume_text():
    """analyze_jobs 必须接受 resume_text 参数。"""
    analyzer = EnhancedJobAnalyzer()
    sig = inspect.signature(analyzer.analyze_jobs)
    assert "resume_text" in sig.parameters


def test_analyze_jobs_returns_score_and_match_info():
    """每个结果必须包含 score, match_highlights, gaps, summary。"""
    screen_resp = '{"relevant": true, "reason": "类型匹配"}'
    match_resp = '{"score": 8, "match_highlights": ["Python经验匹配"], "gaps": ["缺乏大数据经验"], "summary": "整体匹配度较高"}'

    analyzer = EnhancedJobAnalyzer()
    with patch.object(analyzer, '_call_ai_for_screening', return_value=screen_resp), \
         patch.object(analyzer, '_call_ai_for_matching', return_value=match_resp):
        results = analyzer.analyze_jobs(SAMPLE_JOBS, resume_text=SAMPLE_RESUME)

    assert len(results) == 1
    assert results[0]["score"] == 8
    assert "match_highlights" in results[0]
    assert "gaps" in results[0]
    assert "summary" in results[0]


def test_analyze_jobs_filters_irrelevant():
    """relevant=false 的岗位必须被过滤掉。"""
    screen_resp = '{"relevant": false, "reason": "不相关"}'
    analyzer = EnhancedJobAnalyzer()
    with patch.object(analyzer, '_call_ai_for_screening', return_value=screen_resp):
        results = analyzer.analyze_jobs(SAMPLE_JOBS, resume_text=SAMPLE_RESUME)
    assert len(results) == 0


def test_analyze_jobs_sorted_by_score_descending():
    """结果必须按 score 降序排列。"""
    jobs = [
        {"title": "岗位A", "company": "A", "salary": "10K", "job_description": "A"},
        {"title": "岗位B", "company": "B", "salary": "20K", "job_description": "B"},
    ]
    screen_resp = '{"relevant": true, "reason": "相关"}'
    match_resps = iter([
        '{"score": 5, "match_highlights": [], "gaps": [], "summary": "一般"}',
        '{"score": 9, "match_highlights": [], "gaps": [], "summary": "优秀"}',
    ])

    analyzer = EnhancedJobAnalyzer()
    with patch.object(analyzer, '_call_ai_for_screening', return_value=screen_resp), \
         patch.object(analyzer, '_call_ai_for_matching', side_effect=lambda job, rt: next(match_resps)):
        results = analyzer.analyze_jobs(jobs, resume_text=SAMPLE_RESUME)

    assert len(results) == 2
    assert results[0]["score"] >= results[1]["score"]
```

**Step 2: 运行测试，确认失败**

```bash
pytest tests/test_enhanced_job_analyzer.py -v
```

预期：`FAILED` — `analyze_jobs` 签名不含 `resume_text`，或 `_call_ai_for_screening` / `_call_ai_for_matching` 不存在

**Step 3: 修改 `analyzer/enhanced_job_analyzer.py`**

_3a. 在顶部 import 区（第 21 行附近）添加：_

```python
from .prompts.job_analysis_prompts import RESUME_MATCH_PROMPT
```

_3b. 替换 `analyze_jobs` 方法（第 129-147 行）：_

将原方法整体替换为：

```python
def analyze_jobs(self, jobs_list: List[Dict[str, Any]], resume_text: str = "", keyword: str = "") -> List[Dict[str, Any]]:
    """
    两阶段流水线：GLM 类型筛选 → 主力模型简历匹配，按分数降序返回。

    Args:
        jobs_list: 岗位列表
        resume_text: 简历全文（直接传入，不做额外结构化）
        keyword: 搜索关键词（用于类型筛选）
    """
    self._search_keyword = keyword

    # 阶段1：GLM 类型过滤（判断岗位类型是否与搜索关键词相关，不比对简历）
    screened = []
    for i, job in enumerate(jobs_list, 1):
        if i % 10 == 0:
            print(f"   筛选进度: {i}/{len(jobs_list)}")
        response = self._call_ai_for_screening(job)
        result = self._parse_screening_result(response)
        if result.get("relevant", False):
            screened.append(job)

    print(f"✅ 筛选出 {len(screened)}/{len(jobs_list)} 个相关岗位")

    # 阶段2：主力模型简历匹配
    results = []
    for i, job in enumerate(screened, 1):
        if i % 10 == 0:
            print(f"   匹配进度: {i}/{len(screened)}")
        response = self._call_ai_for_matching(job, resume_text)
        match = self._parse_match_result(response)
        results.append({**job, **match})

    return sorted(results, key=lambda x: x.get("score", 0), reverse=True)
```

_3c. 在 `analyze_jobs` 方法之后、`analyze_jobs_three_stages` 之前，插入三个新方法：_

````python
def _call_ai_for_screening(self, job: Dict[str, Any]) -> str:
    """调用 GLM 判断岗位类型与搜索关键词的相关性。可被测试 mock 替换。"""
    keyword = getattr(self, '_search_keyword', '')
    prompt = ExtractionPrompts.get_job_relevance_screening_prompt(job, keyword)
    return self.extraction_service.call_api_simple(prompt, max_tokens=200, temperature=0.1)

def _call_ai_for_matching(self, job: Dict[str, Any], resume_text: str) -> str:
    """调用主力模型进行简历×JD深度匹配。可被测试 mock 替换。"""
    prompt = RESUME_MATCH_PROMPT.format(
        resume_text=resume_text[:2000] if resume_text else "（未提供简历）",
        job_title=job.get('title', ''),
        company=job.get('company', ''),
        salary=job.get('salary', '未提供'),
        description=job.get('job_description', '')[:800],
        requirements=job.get('job_description', '')[:800],
    )
    return self.job_analyzer.ai_client.call_api_simple(prompt)

def _parse_match_result(self, response_text: str) -> Dict[str, Any]:
    """解析主力模型返回的匹配结果 JSON。"""
    import re
    try:
        m = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        m = re.search(r'\{.*\}', response_text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        logger.error(f"解析匹配结果失败: {e}")
    return {"score": 0, "match_highlights": [], "gaps": [], "summary": "解析失败"}
````

_3d. 注释掉 `_stage2_market_cognition_analysis` 方法体（保留方法签名，第 297 行）：_

```python
async def _stage2_market_cognition_analysis(self, extracted_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    # 已停用：市场认知分析已从核心流程中移除（见 design.md 超出范围章节）
    return self._get_default_market_report()
```

**Step 4: 运行新测试，确认通过**

```bash
pytest tests/test_enhanced_job_analyzer.py -v
```

预期：4 个 PASSED

**Step 5: 运行全部测试**

```bash
pytest tests/ -v
```

**Step 6: Commit**

```bash
git add tests/test_enhanced_job_analyzer.py analyzer/enhanced_job_analyzer.py
git commit -m "refactor: EnhancedJobAnalyzer → 2-stage sync pipeline (GLM screen + resume match)"
```

---

### Task 3: 精简 backend/app.py

**Files:**

- Create: `tests/test_app_no_market.py`
- Modify: `backend/app.py`

**Step 1: 写失败测试**

```python
# tests/test_app_no_market.py
import os


def test_no_market_analysis_calls_in_app():
    """backend/app.py 不得包含市场分析相关调用。"""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backend", "app.py"
    )
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    assert "generate_market_analysis" not in source, \
        "Must remove generate_market_analysis call"
    assert "get_market_analysis" not in source, \
        "Must remove get_market_analysis call"
```

**Step 2: 运行测试，确认失败**

```bash
pytest tests/test_app_no_market.py -v
```

预期：`FAILED` — `generate_market_analysis` found in source

**Step 3: 修改 `backend/app.py`**

找到第 471-491 行的市场分析块（`# 9. 生成并获取市场分析` 开头），将整块替换为一行：

```python
        # 9. 市场分析已停用（见 design.md 超出范围章节）
        market_analysis = None
```

然后在 `current_job.update({...})` 里（约第 494-503 行），删除：

```python
            'market_analysis': market_analysis
```

在 `emit_progress(...)` 调用的数据字典里（约第 505-514 行），删除：

```python
            'market_analysis': market_analysis,
```

**Step 4: 运行全部测试**

```bash
pytest tests/ -v
```

预期：全部 PASSED

**Step 5: Commit**

```bash
git add tests/test_app_no_market.py backend/app.py
git commit -m "refactor: remove market analysis from backend/app.py"
```

---

### Task 4: 前端 UI 清理（手动验证）

**Files:**

- Modify: `backend/templates/index.html`
- Modify: `backend/static/js/` 相关文件

注意：前端无自动化测试，依赖手动验证。

**Step 1: 删除 `index.html` 中市场分析相关 HTML**

搜索并删除包含以下关键字的 HTML 块：

- `market_analysis` / `market-analysis`
- `keyword_cloud` / 词云
- `skill_requirements` / 技能热度

**Step 2: 在 JS 中找到岗位卡片渲染函数，更新结构**

卡片必须展示：

- 评分徽章（`score/10`），色阶：9-10=绿色、7-8=蓝色、5-6=黄色、1-4=灰色
- `match_highlights` 列表（绿色）
- `gaps` 列表（橙色）
- `summary` 一句话总结

参考结构：

```javascript
function renderJobCard(job) {
  const scoreClass =
    job.score >= 9
      ? "green"
      : job.score >= 7
        ? "blue"
        : job.score >= 5
          ? "yellow"
          : "gray";
  const highlights = (job.match_highlights || [])
    .map((h) => `<li>${h}</li>`)
    .join("");
  const gaps = (job.gaps || []).map((g) => `<li>${g}</li>`).join("");
  return `
        <div class="job-card">
            <div class="score-badge score-${scoreClass}">${job.score}/10</div>
            <h3>${job.title} · ${job.company}</h3>
            <p class="salary">${job.salary}</p>
            <div class="match-highlights"><b>匹配亮点</b><ul>${highlights}</ul></div>
            <div class="gaps"><b>待补强</b><ul>${gaps}</ul></div>
            <p class="summary">${job.summary}</p>
        </div>`;
}
```

**Step 3: 删除 JS 中 market_analysis WebSocket 事件处理**

搜索 `socket.on('market_analysis'` 相关代码并删除。

**Step 4: 手动验证**

```bash
python backend/app.py
```

访问 http://localhost:5000，检查：

- [ ] 页面无市场分析板块（无词云、无技能热度图）
- [ ] 岗位卡片显示评分 + 亮点（绿色）+ 差距（橙色）+ 总结
- [ ] 结果默认按分数降序排列

**Step 5: Commit**

```bash
git add backend/templates/index.html backend/static/
git commit -m "feat: score-focused job cards; remove market analysis UI"
```

---

### Task 5: 端到端验证

**Step 1: 启动服务**

```bash
python backend/app.py
```

**Step 2: 验证核心流程**

1. 上传简历（PDF/DOCX）
2. 输入关键词（如"数据分析"）、城市（上海）、数量（50）
3. 点击搜索

**Step 3: 验证 Checklist**

- [ ] WebSocket 进度正常：爬取中 → 类型筛选中 → 匹配评分中 → 完成
- [ ] 每个岗位卡片显示 `score`（1-10）、`match_highlights`、`gaps`、`summary`
- [ ] 结果按分数降序排列
- [ ] 页面无市场分析板块

**Step 4: 边界测试**

- 不上传简历直接搜索 → 应有错误提示
- 搜索结果为 0 → 应有空结果提示

---

## 先决条件

- `config/secrets.env` 配置：GLM API Key（筛选用）+ 主力模型 Key（DeepSeek/Claude）
- `playwright install chromium`
- `pip install -r requirements.txt`
- `pip install pytest`
