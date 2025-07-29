#!/usr/bin/env python3
"""
大规模抓取优化测试脚本
验证50-100+岗位抓取能力、AI岗位要求总结和成本控制功能
"""

import os
import sys
import asyncio
import logging
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config_manager import ConfigManager
from crawler.unified_crawler_interface import unified_search_jobs
from analyzer.job_analyzer import JobAnalyzer
from analyzer.job_requirement_summarizer import JobRequirementSummarizer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/large_scale_test.log')
    ]
)
logger = logging.getLogger(__name__)


class LargeScaleOptimizationTester:
    """大规模优化功能测试器"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.test_results = {}
        
    async def run_comprehensive_test(self):
        """运行综合测试"""
        logger.info("🚀 开始大规模抓取优化综合测试")
        logger.info("=" * 60)
        
        # 测试配置
        test_scenarios = [
            {"keyword": "AI算法", "city": "shanghai", "max_jobs": 50, "description": "中等规模测试"},
            {"keyword": "数据分析", "city": "beijing", "max_jobs": 80, "description": "大规模测试"},
        ]
        
        for i, scenario in enumerate(test_scenarios, 1):
            logger.info(f"\n📋 测试场景 {i}/{len(test_scenarios)}: {scenario['description']}")
            logger.info(f"   关键词: {scenario['keyword']}")
            logger.info(f"   城市: {scenario['city']}")
            logger.info(f"   目标岗位数: {scenario['max_jobs']}")
            
            try:
                await self._test_scenario(f"scenario_{i}", scenario)
            except Exception as e:
                logger.error(f"❌ 测试场景 {i} 失败: {e}")
                self.test_results[f"scenario_{i}"] = {"status": "failed", "error": str(e)}
        
        # 生成测试报告
        self._generate_test_report()
    
    async def _test_scenario(self, scenario_id: str, scenario: dict):
        """测试单个场景"""
        start_time = time.time()
        
        # 第一阶段：大规模爬虫测试
        logger.info("🔍 阶段1: 大规模爬虫测试")
        crawl_start = time.time()
        
        jobs = await unified_search_jobs(
            keyword=scenario["keyword"],
            city=scenario["city"],
            max_jobs=scenario["max_jobs"],
            engine="real_playwright"
        )
        
        crawl_time = time.time() - crawl_start
        
        if not jobs:
            raise Exception("爬虫未获取到任何岗位")
        
        logger.info(f"✅ 爬虫完成: {len(jobs)} 个岗位，耗时 {crawl_time:.2f}s")
        logger.info(f"📊 爬虫效率: {len(jobs)/crawl_time:.1f} 岗位/秒")
        
        # 验证岗位数据质量
        valid_jobs = self._validate_job_data(jobs)
        logger.info(f"🔍 数据质量: {len(valid_jobs)}/{len(jobs)} 个有效岗位")
        
        # 第二阶段：AI岗位要求总结测试
        logger.info("\n🧠 阶段2: AI岗位要求总结测试")
        summarizer_start = time.time()
        
        summarizer = JobRequirementSummarizer()
        summaries = await summarizer.summarize_batch_jobs(jobs[:20])  # 测试前20个岗位
        
        summarizer_time = time.time() - summarizer_start
        
        logger.info(f"✅ AI总结完成: {len(summaries)} 个岗位，耗时 {summarizer_time:.2f}s")
        
        # 获取成本优化报告
        cost_report = summarizer.get_cost_savings_report()
        logger.info(f"💰 成本优化报告:")
        logger.info(f"   缓存命中率: {cost_report.get('cache_statistics', {}).get('cache_hit_rate', '0%')}")
        logger.info(f"   AI调用次数: {cost_report.get('cache_statistics', {}).get('ai_calls_made', 0)}")
        logger.info(f"   节省成本: {cost_report.get('cost_analysis', {}).get('total_savings', '¥0.00')}")
        
        # 第三阶段：端到端分析测试
        logger.info("\n🤖 阶段3: 端到端AI分析测试")
        analysis_start = time.time()
        
        analyzer = JobAnalyzer("deepseek")
        analyzed_jobs = analyzer.analyze_jobs(jobs[:15])  # 测试前15个岗位的完整分析
        
        analysis_time = time.time() - analysis_start
        
        logger.info(f"✅ 完整分析完成: {len(analyzed_jobs)} 个岗位，耗时 {analysis_time:.2f}s")
        
        # 验证分析结果质量
        analysis_quality = self._validate_analysis_quality(analyzed_jobs)
        
        total_time = time.time() - start_time
        
        # 记录测试结果
        self.test_results[scenario_id] = {
            "status": "completed",
            "scenario": scenario,
            "performance": {
                "total_time": total_time,
                "crawl_time": crawl_time,
                "summarizer_time": summarizer_time,
                "analysis_time": analysis_time,
                "jobs_found": len(jobs),
                "valid_jobs": len(valid_jobs),
                "analyzed_jobs": len(analyzed_jobs),
                "crawl_efficiency": len(jobs) / crawl_time,
                "overall_efficiency": len(analyzed_jobs) / total_time
            },
            "quality": {
                "data_validity_rate": len(valid_jobs) / len(jobs) if jobs else 0,
                "analysis_quality_score": analysis_quality
            },
            "ai_optimization": cost_report
        }
        
        logger.info(f"📈 场景总结:")
        logger.info(f"   总耗时: {total_time:.2f}s")
        logger.info(f"   整体效率: {len(analyzed_jobs)/total_time:.1f} 个完整分析/秒")
        logger.info(f"   数据有效率: {len(valid_jobs)/len(jobs)*100:.1f}%")
        logger.info(f"   分析质量: {analysis_quality:.1f}/10")
    
    def _validate_job_data(self, jobs: list) -> list:
        """验证岗位数据质量"""
        valid_jobs = []
        
        for job in jobs:
            # 检查必要字段
            if not job.get('title') or not job.get('company'):
                continue
            
            # 检查字段质量
            title = job.get('title', '').strip()
            company = job.get('company', '').strip()
            
            if len(title) < 2 or len(title) > 100:
                continue
                
            if len(company) < 2 or len(company) > 100:
                continue
            
            # 检查是否有岗位描述或要求
            has_description = (
                job.get('job_description') and 
                len(job.get('job_description', '').strip()) > 20
            )
            has_requirements = (
                job.get('job_requirements') and 
                len(job.get('job_requirements', '').strip()) > 20
            )
            
            if has_description or has_requirements:
                valid_jobs.append(job)
        
        return valid_jobs
    
    def _validate_analysis_quality(self, analyzed_jobs: list) -> float:
        """验证分析结果质量"""
        if not analyzed_jobs:
            return 0.0
        
        quality_scores = []
        
        for job in analyzed_jobs:
            score = 0
            
            # 检查是否有分析结果
            analysis = job.get('analysis', {})
            if analysis:
                score += 2
                
                # 检查评分是否合理
                job_score = analysis.get('score', 0)
                if 0 <= job_score <= 10:
                    score += 2
                
                # 检查是否有推荐理由
                if analysis.get('reason') and len(analysis.get('reason', '')) > 10:
                    score += 2
            
            # 检查是否有AI要求总结
            ai_summary = job.get('ai_requirement_summary', {})
            if ai_summary:
                score += 2
                
                # 检查总结质量
                if (ai_summary.get('core_responsibilities') and 
                    ai_summary.get('key_requirements')):
                    score += 2
            
            quality_scores.append(score)
        
        return sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    
    def _generate_test_report(self):
        """生成测试报告"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 大规模抓取优化测试报告")
        logger.info("=" * 60)
        
        if not self.test_results:
            logger.error("❌ 没有完成的测试结果")
            return
        
        # 统计总体性能
        total_jobs = sum(
            result.get('performance', {}).get('jobs_found', 0) 
            for result in self.test_results.values() 
            if result.get('status') == 'completed'
        )
        
        total_analyzed = sum(
            result.get('performance', {}).get('analyzed_jobs', 0) 
            for result in self.test_results.values() 
            if result.get('status') == 'completed'
        )
        
        avg_crawl_efficiency = sum(
            result.get('performance', {}).get('crawl_efficiency', 0) 
            for result in self.test_results.values() 
            if result.get('status') == 'completed'
        ) / len([r for r in self.test_results.values() if r.get('status') == 'completed'])
        
        avg_quality = sum(
            result.get('quality', {}).get('analysis_quality_score', 0) 
            for result in self.test_results.values() 
            if result.get('status') == 'completed'
        ) / len([r for r in self.test_results.values() if r.get('status') == 'completed'])
        
        logger.info(f"🎯 总体性能指标:")
        logger.info(f"   总抓取岗位数: {total_jobs}")
        logger.info(f"   总分析岗位数: {total_analyzed}")
        logger.info(f"   平均抓取效率: {avg_crawl_efficiency:.1f} 岗位/秒")
        logger.info(f"   平均分析质量: {avg_quality:.1f}/10")
        
        # 详细场景结果
        logger.info(f"\n📋 详细测试结果:")
        for scenario_id, result in self.test_results.items():
            if result.get('status') == 'completed':
                perf = result['performance']
                quality = result['quality']
                logger.info(f"\n   {scenario_id}: ✅ 成功")
                logger.info(f"     岗位数: {perf['jobs_found']} (有效: {perf['valid_jobs']})")
                logger.info(f"     总耗时: {perf['total_time']:.2f}s")
                logger.info(f"     抓取效率: {perf['crawl_efficiency']:.1f} 岗位/秒")
                logger.info(f"     分析质量: {quality['analysis_quality_score']:.1f}/10")
            else:
                logger.info(f"\n   {scenario_id}: ❌ 失败 - {result.get('error', '未知错误')}")
        
        # AI成本优化总结
        logger.info(f"\n💰 AI成本优化效果:")
        for scenario_id, result in self.test_results.items():
            if result.get('status') == 'completed':
                ai_opt = result.get('ai_optimization', {})
                cache_stats = ai_opt.get('cache_statistics', {})
                cost_analysis = ai_opt.get('cost_analysis', {})
                
                logger.info(f"   {scenario_id}:")
                logger.info(f"     缓存命中率: {cache_stats.get('cache_hit_rate', '0%')}")
                logger.info(f"     节省成本: {cost_analysis.get('total_savings', '¥0.00')}")
        
        # 保存详细报告到文件
        self._save_detailed_report()
        
        logger.info("\n✅ 大规模抓取优化测试完成!")
    
    def _save_detailed_report(self):
        """保存详细报告到文件"""
        try:
            import json
            report_file = Path("data/large_scale_test_report.json")
            report_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "test_timestamp": time.time(),
                    "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "results": self.test_results
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📄 详细报告已保存: {report_file}")
            
        except Exception as e:
            logger.error(f"保存报告失败: {e}")


async def main():
    """主测试函数"""
    # 确保日志目录存在
    Path("logs").mkdir(exist_ok=True)
    
    logger.info("🎯 Boss直聘大规模抓取优化测试")
    logger.info("测试目标:")
    logger.info("  1. 验证50-100+岗位大规模抓取能力")
    logger.info("  2. 测试AI岗位要求总结功能")
    logger.info("  3. 验证AI成本控制优化效果")
    logger.info("  4. 评估整体系统性能")
    
    tester = LargeScaleOptimizationTester()
    await tester.run_comprehensive_test()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹️ 测试被用户中断")
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()