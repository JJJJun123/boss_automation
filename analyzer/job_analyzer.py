from .ai_client_factory import AIClientFactory
import os


class JobAnalyzer:
    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider or os.getenv('AI_PROVIDER', 'deepseek')
        self.ai_client = AIClientFactory.create_client(self.ai_provider)
        self.user_requirements = self.get_default_requirements()
        print(f"🤖 使用AI服务: {self.ai_provider.upper()}")
    
    def get_default_requirements(self):
        """获取默认的用户要求（从配置文件读取，若无则使用硬编码）"""
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            profile = config_manager.get_user_preference('personal_profile', {})
            
            # 从配置构建用户要求文本
            job_intentions = profile.get('job_intentions', [])
            skills = profile.get('skills', [])
            salary_range = profile.get('salary_range', {})
            excluded_types = profile.get('excluded_job_types', [])
            experience_years = profile.get('experience_years', 0)
            
            requirements = f"""
求职意向：
{chr(10).join(f'- {intention}' for intention in job_intentions)}

背景要求：
- 工作经验: {experience_years}年
- 技能专长: {', '.join(skills)}
- 希望在大中型公司发展

薪资期望：
- {salary_range.get('min', 15)}K-{salary_range.get('max', 35)}K/月（可接受范围）

不接受的岗位类型：
{chr(10).join(f'- {excluded}' for excluded in excluded_types)}
"""
            return requirements
            
        except Exception:
            # 如果配置读取失败，使用硬编码默认值
            return """
求职意向：
- 市场风险管理相关岗位
- 咨询相关岗位（战略咨询、管理咨询、行业分析）
- AI/人工智能相关岗位
- 金融相关岗位（银行、证券、基金、保险）

背景要求：
- 有金融行业经验优先
- 熟悉风险管理、数据分析
- 对AI/机器学习有一定了解
- 希望在大中型公司发展

薪资期望：
- 15K-35K/月（可接受范围）

地理位置：
- 深圳优先，其他一线城市可考虑

不接受的岗位类型：
- 纯销售岗位
- 客服岗位
- 纯技术开发（除非AI相关）
- 初级行政岗位
"""
    
    def analyze_jobs(self, jobs_list):
        """批量分析岗位"""
        analyzed_jobs = []
        
        print(f"🤖 开始AI分析 {len(jobs_list)} 个岗位...")
        
        for i, job in enumerate(jobs_list, 1):
            print(f"分析第 {i}/{len(jobs_list)} 个岗位: {job.get('title', '未知')}")
            
            try:
                analysis_result = self.ai_client.analyze_job_match(
                    job, 
                    self.user_requirements
                )
                
                # 将分析结果添加到岗位信息中
                job['analysis'] = analysis_result
                analyzed_jobs.append(job)
                
                print(f"✅ 分析完成 - 评分: {analysis_result['score']}/10")
                
            except Exception as e:
                print(f"❌ 分析失败: {e}")
                # 即使分析失败，也保留原始岗位信息
                job['analysis'] = {
                    "score": 0,
                    "recommendation": "分析失败",
                    "reason": f"分析过程中出错: {e}",
                    "summary": "无法分析此岗位"
                }
                analyzed_jobs.append(job)
        
        return analyzed_jobs
    
    def filter_and_sort_jobs(self, analyzed_jobs, min_score=6):
        """过滤和排序岗位"""
        # 过滤掉低分岗位
        filtered_jobs = [
            job for job in analyzed_jobs 
            if job.get('analysis', {}).get('score', 0) >= min_score
        ]
        
        # 按分数排序
        sorted_jobs = sorted(
            filtered_jobs, 
            key=lambda x: x.get('analysis', {}).get('score', 0), 
            reverse=True
        )
        
        print(f"🎯 过滤结果: {len(filtered_jobs)}/{len(analyzed_jobs)} 个岗位达到最低评分标准({min_score}分)")
        
        return sorted_jobs
    
    def set_user_requirements(self, requirements):
        """设置用户要求（后续版本使用）"""
        self.user_requirements = requirements