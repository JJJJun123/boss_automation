import json
import os
from datetime import datetime
from ..ai_client_factory import AIClientFactory


class ResumeAnalyzer:
    """简历AI分析器，使用LangGPT格式的专业HR角色进行结构化简历分析"""
    
    def __init__(self, ai_provider=None):
        # 从配置读取默认AI提供商
        if not ai_provider:
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                ai_provider = config_manager.get_app_config('ai.default_provider', 'claude')
            except Exception:
                ai_provider = 'claude'
        
        self.ai_provider = ai_provider
        print(f"🔍 [DEBUG] 正在创建AI客户端: {ai_provider}")
        self.ai_client = AIClientFactory.create_client(ai_provider)
        print(f"🔍 [DEBUG] AI客户端创建完成: {type(self.ai_client)}")
        
        print(f"📝 简历分析器初始化完成，使用AI: {self.ai_provider.upper()}")
    
    def analyze_resume(self, resume_text):
        """分析简历内容，返回完整的AI分析结果"""
        
        print(f"🔍 [DEBUG] analyze_resume开始，简历长度: {len(resume_text)}")
        print(f"🔍 [DEBUG] AI提供商: {self.ai_provider}")
        
        # 构建专业HR分析prompt
        system_prompt = self._build_hr_system_prompt()
        user_prompt = self._build_user_analysis_prompt(resume_text)
        
        print(f"🔍 [DEBUG] Prompt构建完成，system长度: {len(system_prompt)}, user长度: {len(user_prompt)}")
        
        try:
            print("开始调用AI分析...")
            
            # 调用AI分析 - 指定更大的max_tokens避免被截断
            analysis_response = self.ai_client.call_api(
                system_prompt, user_prompt, max_tokens=3000
            )
            
            print(f"AI调用完成，响应类型: {type(analysis_response)}")
            
            # 立即保存原始响应
            import os
            debug_file = os.path.join(os.getcwd(), "debug_ai_response.txt")
            try:
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write("=== 调试信息 ===\n")
                    f.write(f"工作目录: {os.getcwd()}\n")
                    f.write(f"时间: {__import__('datetime').datetime.now()}\n")
                    f.write(f"响应类型: {type(analysis_response)}\n")
                    f.write(f"响应长度: {len(str(analysis_response))}\n")
                    f.write("\n=== AI原始响应 ===\n")
                    f.write(str(analysis_response))
                    f.write("\n=== 响应结束 ===\n")
                print(f"✅ AI响应已保存到: {debug_file}")
            except Exception as save_e:
                print(f"❌ 保存文件失败: {save_e}")
                # 至少在控制台显示前1000个字符
                print(f"=== AI响应前1000字符 ===")
                print(str(analysis_response)[:1000])
            
            # 解析分析结果
            print("开始解析分析结果...")
            analysis_result = self._parse_analysis_response(analysis_response)
            print("✅ 解析完成")
            
            return analysis_result
            
        except Exception as e:
            print(f"简历分析失败: {e}")
            raise e
    
    def _build_hr_system_prompt(self):
        """构建LangGPT格式的HR系统prompt（优化版）"""
        return """# 角色身份
你是一位资深人才评估专家，拥有15年跨行业（金融、咨询、科技）招聘经验。你专长于运用STAR法则深度解析简历，从具体经历中提炼候选人的核心竞争力和发展潜力。

# 核心任务
基于STAR法则对简历进行结构化分析，输出四个部分：
1. **简历核心信息重构**：用STAR框架重新组织工作经历
2. **核心能力洞察**：从多个STAR案例中提炼4项核心能力模式
3. **客观差距分析**：识别4项相对于目标岗位的能力短板
4. **精准岗位匹配**：推荐3-5个最适合的岗位类型

# STAR分析方法论
对每段重要经历必须识别：
- **Situation**: 具体的工作/项目背景和挑战
- **Task**: 承担的具体责任和目标
- **Action**: 采取的关键行动和方法
- **Result**: 量化的成果和影响

然后从多个STAR案例中抽象出能力模式。

# 能力分析框架
## 四个维度评估
1. **专业技术能力**：具体技能的深度和广度
2. **问题解决能力**：分析问题、设计方案、执行落地的完整性
3. **团队协作能力**：沟通、领导、影响他人的具体表现
4. **学习适应能力**：面对新环境/新挑战的快速适应性

## 能力等级标准
- **专家级**：能独立设计解决方案，指导他人
- **熟练级**：能独立执行复杂任务，偶需指导
- **基础级**：能执行标准任务，需要指导
- **入门级**：需要大量指导和支持

# 分析原则
1. **证据驱动**：每个结论必须有简历中的具体证据支撑
2. **能力抽象**：从具体行为推断通用能力，不复述简历内容
3. **相对评估**：明确说明相对于什么标准（行业平均/岗位要求）
4. **发展视角**：考虑能力的成长轨迹和潜力空间
5. **市场导向**：基于当前热门岗位需求评估竞争力

# 输出质量要求
- 优势分析必须是能力总结，不是经历罗列
- 短板分析必须指出具体的能力差距，不是泛泛而谈
- 岗位推荐必须基于能力匹配度，给出匹配原因
- 所有结论必须有简历证据支撑，避免主观臆测

# 输出格式 (Output Format)
```json
{{
  "resume_core": {{
    "education": [
      {{
        "school": "具体学校名称",
        "degree": "学历层次（如：本科/硕士/博士）",
        "major": "专业名称",
        "honors": "荣誉奖项（如有）",
        "details": "其他重要教育信息"
      }}
    ],
    "work_experience": [
      {{
        "company": "公司全名",
        "position": "职位名称",
        "industry": "所在行业",
        "start_date": "YYYY-MM格式",
        "end_date": "YYYY-MM格式（在职则填current）",
        "responsibilities": ["详细职责描述1", "详细职责描述2", "..."]
      }}
    ],
    "skills": {{
      "hard_skills": ["Python", "Java", "机器学习", "数据分析", "..."],
      "soft_skills": ["团队协作", "项目管理", "沟通能力", "..."],
      "certifications": ["PMP", "AWS认证", "CPA", "..."],
      "tools": ["TensorFlow", "Docker", "Git", "Jira", "..."],
      "languages": ["英语（流利）", "日语（初级）", "..."]
    }},
    "projects": [
      {{
        "project_name": "项目名称",
        "role": "在项目中的角色",
        "duration": "项目周期",
        "description": "项目详细描述（背景、目标、规模）",
        "technologies": ["使用的技术栈"],
        "outcome": "项目成果（包含具体数据和影响）",
        "team_size": "团队规模"
      }}
    ]
  }},
  "strengths": [
    "系统性解决复杂问题能力：能在多变业务环境中构建完整解决方案，从问题识别到落地实施具备全链条思维",
    "跨领域知识整合能力：能将技术、业务、管理知识有机结合，在复合型岗位中发挥独特价值",
    "持续学习和适应能力：职业发展轨迹显示良好的技术敏感度，能快速掌握新领域并产生实际价值",
    "项目推动和协调能力：具备在复杂组织环境中推进工作的能力，能平衡多方利益达成目标"
  ],
  "weaknesses": [
    "技术深度的广度权衡：涉猎面广但单项技术深度有待提升，在专业技术岗位可能面临挑战",
    "长期专注度的市场认知：频繁的领域切换可能让雇主对其长期稳定性产生疑虑",
    "团队技术管理经验：缺乏大规模技术团队的管理经验，在技术管理岗位需要能力补强",
    "行业深度认知差距：跨行业经验丰富但单一行业深度积累不足，垂直领域竞争力有限"
  ],
  "recommended_positions": [
    "技术产品经理（金融科技方向） - 匹配度9分",
    "解决方案架构师（初级） - 匹配度8分", 
    "项目技术负责人（中小型团队） - 匹配度7分",
    "业务分析师（技术背景） - 匹配度7分"
  ]
}}
"""
    
    def _build_user_analysis_prompt(self, resume_text):
        """构建用户分析prompt - 基于STAR法则的洞察性分析（优化版）"""
        
        return f"""请基于STAR法则对以下简历进行深度分析。

## 分析步骤
### 第一步：STAR解构
对每段重要工作经历，识别：
- Situation（背景挑战）
- Task（承担责任）  
- Action（关键行动）
- Result（量化成果）

### 第二步：能力提炼
从多个STAR案例中总结4项核心能力：
- 专业技术能力（技能深度+应用广度）
- 问题解决能力（分析+设计+执行）
- 团队协作能力（沟通+领导+影响力）
- 学习适应能力（新环境+新挑战适应性）

每项能力必须：
1. 给出能力等级（专家/熟练/基础/入门）
2. 提供具体证据（来自哪个STAR案例）
3. 说明能力特点（相比同级别候选人的优势）

### 第三步：差距识别  
相对于目标岗位需求，识别4项客观短板：
1. 明确相对标准（什么岗位/什么水平）
2. 具体差距描述（缺什么/弱在哪）
3. 影响程度评估（是否影响岗位胜任）
4. 改进建议（如何弥补）

### 第四步：岗位匹配
推荐3-5个最适合岗位，每个岗位格式为字符串：
"岗位名称（具体方向） - 匹配度X分"

示例：
- "技术产品经理（金融科技方向） - 匹配度9分"
- "数据分析师（中级） - 匹配度8分"

## 质量检查清单
输出前请自检：
☐ 优势分析是能力总结，不是简历复述
☐ 每个结论都有具体的简历证据
☐ 能力等级评估有明确标准
☐ 短板分析指出了具体差距
☐ 岗位推荐基于能力匹配而非主观判断
☐ 整体分析客观平衡，既认可优势也直面短板

## 简历内容
{resume_text}

请严格按照JSON格式输出分析结果，确保优势和劣势都是**能力层面的洞察**，而不是简历内容的重复。"""
    
    def _parse_analysis_response(self, response_text):
        """解析AI分析响应"""
        from datetime import datetime
        
        try:
            # 提取JSON部分
            response_text = response_text.strip()
            
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end == -1:  # 如果没找到结束的```，使用整个剩余文本
                    json_text = response_text[start:].strip()
                    print(f"⚠️ 警告：JSON结束标记未找到，使用剩余全部文本")
                else:
                    json_text = response_text[start:end].strip()
            elif "{" in response_text and "}" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_text = response_text[start:end]
            else:
                json_text = response_text
            
            # 尝试修复常见的JSON问题
            json_text = self._fix_json_format(json_text)
            
            result = json.loads(json_text)
            
            # 验证和填充必要字段 - 新的JSON结构
            required_fields = [
                'resume_core', 'strengths', 'weaknesses', 'recommended_positions'
            ]
            
            # 验证resume_core的子字段
            if 'resume_core' in result:
                core_fields = ['education', 'work_experience', 'skills', 'projects']
                for field in core_fields:
                    if field not in result['resume_core']:
                        result['resume_core'][field] = []
            
            for field in required_fields:
                if field not in result:
                    result[field] = self._get_default_value(field)
            
            # 新的JSON结构不需要评分验证，但需要验证数据结构
            
            # 添加时间戳和原始输出
            result['analysis_time'] = datetime.now().isoformat()
            result['full_output'] = response_text
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            
            # 生成带时间戳的debug文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_file = f"debug_json_error_{timestamp}.txt"
            
            try:
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write("=== JSON解析错误调试信息 ===\n")
                    f.write(f"时间: {datetime.now()}\n")
                    f.write(f"错误: {e}\n\n")
                    f.write("=== 完整AI响应 ===\n")
                    f.write(response_text)
                    f.write("\n\n=== 提取的JSON文本（repr格式，显示所有字符） ===\n")
                    f.write(repr(json_text))
                    f.write("\n\n=== 提取的JSON文本（原始格式） ===\n")
                    f.write(json_text)
                    f.write("\n\n=== 字符级别分析 ===\n")
                    f.write(f"原始响应长度: {len(response_text)}\n")
                    f.write(f"提取的JSON长度: {len(json_text)}\n")
                    f.write(f"JSON第一个字符: {repr(json_text[0]) if json_text else 'EMPTY'}\n")
                    f.write(f"JSON第二个字符: {repr(json_text[1]) if len(json_text) > 1 else 'NOT EXISTS'}\n")
                    f.write(f"JSON前5个字符: {repr(json_text[:5])}\n")
                    f.write(f"是否包含```json: {'```json' in response_text}\n")
                    if '```json' in response_text:
                        start_pos = response_text.find("```json") + 7
                        end_pos = response_text.find("```", start_pos)
                        f.write(f"JSON开始位置: {start_pos}\n")
                        f.write(f"JSON结束位置: {end_pos}\n")
                        f.write(f"提取的原始片段: {repr(response_text[start_pos:end_pos])}\n")
                
                print(f"❌ JSON解析错误，详细信息已保存: {debug_file}")
                print(f"JSON第一个字符: {repr(json_text[0]) if json_text else 'EMPTY'}")
                print(f"JSON前5个字符: {repr(json_text[:5])}")
                
            except Exception as debug_e:
                print(f"调试输出失败: {debug_e}")
                # 至少打印基本信息
                print(f"JSON文本前50字符: {repr(json_text[:50])}")
            
            # 直接抛出异常，不使用fallback
            raise Exception(f"AI响应格式错误，无法解析JSON: {e}")
    
    def _get_default_value(self, field):
        """获取字段默认值 - 与当前prompt结构一致"""
        defaults = {
            'resume_core': {
                'education': [],
                'work_experience': [],
                'skills': {
                    'hard_skills': [],
                    'soft_skills': [],
                    'certifications': [],
                    'tools': [],
                    'languages': []
                },
                'projects': []
            },
            'strengths': ['待分析'],
            'weaknesses': ['待分析'],
            'recommended_positions': ['待推荐']
        }
        return defaults.get(field, [])
    
    def _fix_json_format(self, json_text):
        """修复常见的JSON格式问题"""
        try:
            # 首先尝试直接解析，如果成功就不需要修复
            import json
            try:
                json.loads(json_text)
                return json_text  # JSON是有效的，直接返回
            except json.JSONDecodeError:
                pass  # 需要修复，继续下面的逻辑
            
            # 简单修复：添加缺失的闭合括号
            open_braces = json_text.count('{') - json_text.count('}')
            open_brackets = json_text.count('[') - json_text.count(']')
            
            if open_braces > 0:
                json_text += '}' * open_braces
            if open_brackets > 0:
                json_text += ']' * open_brackets
            
            return json_text
            
        except Exception as e:
            print(f"JSON修复失败: {e}")
            return json_text
    
