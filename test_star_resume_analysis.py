#!/usr/bin/env python3
"""
测试基于STAR法则的简历分析效果
"""

from analyzer.resume.resume_analyzer import ResumeAnalyzer

def test_star_analysis():
    """测试STAR法则简历分析"""
    
    print("="*70)
    print("测试基于STAR法则的简历分析")
    print("="*70)
    
    # 使用你提到的那种简历内容进行测试
    resume_text = """
    个人信息：
    姓名：张某某
    学历：圣路易斯华盛顿大学，数据分析与统计硕士
    
    工作经历：
    2021-2024  安永企业咨询有限公司  高级咨询顾问
    - 为国有大行和股份制银行提供市场/信用风险管理与内控咨询
    - 主导风险管理方案设计，涵盖风险指标监控、风险计量、机器学习应用
    - 精通各类金融产品估值模型，完成170+个财务估值验证项目
    - 基于IFRS9框架的预期信用损失模型建设与验证
    - 主导售前方案演示和技术标书撰写，完成20余份金融机构解决方案标书
    
    2024-现在  长亮科技股份有限公司  高级需求分析师
    - 主导平安银行风险管理/FICC系统优化解决方案
    - 带领12人小组进行项目管理和进度控制
    - 协调IT与业务部门，将复杂业务逻辑转化为技术方案
    - 主导智能问答/市场分析AI智能体设计与编排
    
    技能：
    Python、SQL、VBA、机器学习、风险管理、项目管理
    证书：FRM、CFA二级
    """
    
    try:
        print("🔍 创建简历分析器（使用Claude模型）...")
        analyzer = ResumeAnalyzer('claude')
        
        print("📝 开始STAR法则分析...")
        result = analyzer.analyze_resume(resume_text)
        
        print("\n" + "="*70)
        print("分析结果对比")
        print("="*70)
        
        print("\n🎯 优势分析（期望：洞察性总结 vs 避免照抄）:")
        for i, strength in enumerate(result.get('strengths', []), 1):
            print(f"\n{i}. {strength}")
            
            # 检查是否照抄了具体数字
            if any(keyword in strength for keyword in ['170+', '12人', '20余份']):
                print("   ⚠️  可能包含简历原文数字")
            elif any(keyword in strength for keyword in ['能力', '思维', '经验', '适应']):
                print("   ✅ 体现能力洞察")
            
        print("\n⚠️  劣势分析（期望：市场视角 vs 避免空泛）:")
        for i, weakness in enumerate(result.get('weaknesses', []), 1):
            print(f"\n{i}. {weakness}")
            
            if any(keyword in weakness for keyword in ['市场', '竞争', '深度', '挑战']):
                print("   ✅ 体现市场视角")
            elif weakness in ['学习能力有待提高', '经验不足']:
                print("   ⚠️  可能过于空泛")
        
        print("\n💼 岗位推荐（期望：基于能力水平的现实选择）:")
        for i, position in enumerate(result.get('recommended_positions', []), 1):
            print(f"{i}. {position}")
            
        print(f"\n📊 分析质量评估:")
        
        # 评估分析质量
        strengths = result.get('strengths', [])
        quality_score = 0
        
        # 检查是否避免了照抄
        avoid_copy = sum(1 for s in strengths if not any(num in s for num in ['170+', '12人', '20余份', '3年']))
        if avoid_copy >= len(strengths) * 0.8:
            quality_score += 25
            print("✅ 避免照抄简历内容: 良好")
        else:
            print("❌ 仍有照抄简历内容的情况")
            
        # 检查是否有能力洞察
        insight_count = sum(1 for s in strengths if any(word in s for word in ['能力', '思维', '整合', '适应', '解决']))
        if insight_count >= 2:
            quality_score += 25
            print("✅ 能力洞察分析: 良好")
        else:
            print("❌ 缺乏足够的能力洞察")
            
        # 检查劣势分析的市场视角
        weaknesses = result.get('weaknesses', [])
        market_perspective = sum(1 for w in weaknesses if any(word in w for word in ['市场', '竞争', '行业', '雇主']))
        if market_perspective >= 1:
            quality_score += 25
            print("✅ 市场视角分析: 良好")
        else:
            print("❌ 缺乏市场视角")
            
        # 检查岗位推荐的务实性
        positions = result.get('recommended_positions', [])
        if len(positions) >= 3:
            quality_score += 25
            print("✅ 岗位推荐数量: 充分")
        else:
            print("❌ 岗位推荐数量不足")
            
        print(f"\n总体质量得分: {quality_score}/100")
        
        if quality_score >= 75:
            print("🎉 分析质量优秀！符合STAR法则要求")
        elif quality_score >= 50:
            print("👍 分析质量良好，仍有改进空间")
        else:
            print("😐 分析质量待提升，需要进一步优化")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")

def compare_old_vs_new():
    """对比优化前后的分析效果"""
    print(f"\n" + "="*70)
    print("分析效果对比")
    print("="*70)
    
    print("\n📋 **优化前的问题（照抄式）:**")
    print("❌ '具有丰富的金融工具估值经验，完成170+个估值验证项目，精度控制在1%以内'")
    print("❌ '3年安永金融咨询经验，深度服务大型金融机构'")
    print("❌ '熟练掌握Python+多种AI工具链'")
    
    print("\n🎯 **优化后期望（洞察式）:**")
    print("✅ '系统性解决复杂问题能力：能在多变业务环境中构建完整解决方案'")
    print("✅ '跨领域知识整合能力：能将技术、业务、管理知识有机结合'")
    print("✅ '持续学习和适应能力：职业轨迹显示良好的技术敏感度'")
    
    print("\n🔍 **STAR法则应用:**")
    print("• Situation: 识别候选人面临的工作情境（如金融行业数字化转型）")
    print("• Task: 理解承担的核心任务（如风险管理体系建设）")
    print("• Action: 分析采取的具体行动（如方案设计、团队协调）")
    print("• Result: 评估成果背后的能力（如解决复杂问题的能力）")

if __name__ == "__main__":
    test_star_analysis()
    compare_old_vs_new()
    
    print(f"\n" + "="*70)
    print("STAR法则优化总结")
    print("="*70)
    print("主要改进:")
    print("1. ✅ 引入STAR法则分析框架")
    print("2. ✅ 强调能力洞察而非经历复述")
    print("3. ✅ 要求市场视角的短板分析")
    print("4. ✅ 明确禁止照抄简历内容")
    print("5. ✅ 提供洞察性的分析示例")
    print("\n预期效果:")
    print("• 📈 分析结果更有洞察价值")
    print("• 🎯 优势描述更具竞争力")
    print("• ⚡ 短板分析更具指导性")
    print("• 💼 岗位推荐更加务实精准")