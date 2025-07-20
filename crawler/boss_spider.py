from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import urllib.parse
import time
from .browser_manager import BrowserManager


class BossSpider:
    def __init__(self):
        self.browser = BrowserManager()
        self.base_url = "https://www.zhipin.com"
        
    def start(self):
        """启动爬虫"""
        if not self.browser.setup_browser():
            return False
        return True
    
    def login_with_manual_help(self):
        """手动登录辅助"""
        print("=== 手动登录流程 ===")
        print("1. 正在打开Boss直聘登录页面...")
        
        # 访问首页
        self.browser.driver.get(f"{self.base_url}/shenzhen/")
        self.browser.random_delay(2, 4)
        
        # 尝试加载已保存的cookies
        if self.browser.load_cookies():
            self.browser.driver.refresh()
            self.browser.random_delay(3, 5)
            
            # 检查是否已登录
            if self.check_login_status():
                print("✅ 使用保存的cookies登录成功!")
                return True
            else:
                print("⚠️ 保存的cookies已失效，需要重新登录")
        
        print("2. 请在浏览器中手动完成登录（建议使用扫码登录）")
        print("3. 登录完成后，按回车键继续...")
        input()
        
        # 验证登录状态
        if self.check_login_status():
            print("✅ 登录成功!")
            self.browser.save_cookies()
            return True
        else:
            print("❌ 登录验证失败，请检查登录状态")
            return False
    
    def check_login_status(self):
        """检查登录状态"""
        try:
            # 查找登录后的用户相关元素
            # Boss直聘登录后通常会有用户头像或者用户名显示
            user_elements = [
                "//img[contains(@class, 'avatar')]",
                "//span[contains(@class, 'name')]",
                "//div[contains(@class, 'user')]"
            ]
            
            for xpath in user_elements:
                try:
                    element = self.browser.driver.find_element(By.XPATH, xpath)
                    if element.is_displayed():
                        return True
                except NoSuchElementException:
                    continue
            
            # 如果找不到用户元素，检查是否有登录按钮
            login_buttons = [
                "//a[contains(text(), '登录')]",
                "//button[contains(text(), '登录')]"
            ]
            
            for xpath in login_buttons:
                try:
                    element = self.browser.driver.find_element(By.XPATH, xpath)
                    if element.is_displayed():
                        return False  # 有登录按钮说明未登录
                except NoSuchElementException:
                    continue
                    
            return True  # 既没有用户元素也没有登录按钮，假设已登录
            
        except Exception as e:
            print(f"检查登录状态时出错: {e}")
            return False
    
    def search_jobs(self, keyword, city_code="101280600", max_jobs=20, fetch_details=False):
        """搜索岗位"""
        print(f"🔍 开始搜索岗位: {keyword}")
        
        # 构造搜索URL
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"{self.base_url}/web/geek/jobs?query={encoded_keyword}&city={city_code}"
        
        print(f"访问搜索页面: {search_url}")
        self.browser.driver.get(search_url)
        self.browser.random_delay(3, 5)
        
        # 模拟人类行为
        self.browser.simulate_human_behavior()
        
        jobs = []
        try:
            # 等待页面加载完成
            print("等待岗位列表加载...")
            self.browser.random_delay(5, 8)  # 增加等待时间
            
            # 滚动加载更多岗位
            print("滚动页面加载更多岗位...")
            for i in range(3):  # 滚动3次
                self.browser.driver.execute_script("window.scrollBy(0, 1000);")
                self.browser.random_delay(2, 3)
                print(f"第{i+1}次滚动完成")
            
            # 滚动到页面底部
            self.browser.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.browser.random_delay(3, 5)
            
            # 尝试多种可能的岗位列表选择器
            possible_selectors = [
                ".job-list-box",
                ".job-card-wrapper", 
                ".job-list",
                ".search-job-result",
                "[ka='search-job-result']",
                ".job-primary"
            ]
            
            job_elements = []
            for selector in possible_selectors:
                try:
                    elements = self.browser.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"✅ 使用选择器 '{selector}' 找到 {len(elements)} 个元素")
                        job_elements = elements
                        break
                except:
                    continue
            
            # 如果还是找不到，尝试通过XPath查找
            if not job_elements:
                xpath_selectors = [
                    "//li[contains(@class, 'job')]",
                    "//div[contains(@class, 'job')]",
                    "//a[contains(@href, '/job_detail/')]"
                ]
                
                for xpath in xpath_selectors:
                    try:
                        elements = self.browser.driver.find_elements(By.XPATH, xpath)
                        if elements:
                            print(f"✅ 使用XPath '{xpath}' 找到 {len(elements)} 个元素")
                            job_elements = elements
                            break
                    except:
                        continue
            
            print(f"找到 {len(job_elements)} 个岗位")
            
            for i, job_element in enumerate(job_elements[:max_jobs]):
                try:
                    job_info = self.extract_job_info(job_element)
                    if job_info:
                        # 如果需要获取详情，并且有URL
                        if fetch_details and job_info.get('url'):
                            print(f"🔍 获取第{i+1}个岗位的详细信息...")
                            job_details = self.get_job_detail(job_info['url'])
                            # 将详细信息合并到基本信息中
                            job_info.update(job_details)
                            # 获取详情后需要更长的延迟
                            self.browser.random_delay(2, 4)
                        
                        jobs.append(job_info)
                        print(f"✅ 第{i+1}个岗位: {job_info['title']} - {job_info['company']}")
                    
                    # 随机延迟
                    self.browser.random_delay(0.5, 1.5)
                    
                except Exception as e:
                    print(f"❌ 提取第{i+1}个岗位信息失败: {e}")
                    continue
        
        except TimeoutException:
            print("❌ 页面加载超时，可能需要验证登录状态或网站结构已变化")
        except Exception as e:
            print(f"❌ 搜索过程中出错: {e}")
        
        print(f"🎯 成功获取 {len(jobs)} 个岗位信息")
        return jobs
    
    def extract_job_info(self, job_element):
        """提取岗位信息"""
        try:
            job_info = {}
            
            # 岗位标题 - 尝试多种选择器
            title_selectors = [
                ".job-title a", ".job-name a", "a[ka='search-job-title']", 
                ".job-name", ".title", "h3 a", ".job-title"
            ]
            title_element = None
            for selector in title_selectors:
                try:
                    title_element = job_element.find_element(By.CSS_SELECTOR, selector)
                    if title_element.text.strip():
                        break
                except:
                    continue
            
            if title_element:
                job_info['title'] = title_element.text.strip()
                job_info['url'] = title_element.get_attribute('href') or ""
            else:
                job_info['title'] = "标题获取失败"
                job_info['url'] = ""
            
            # 公司名称 - 尝试多种选择器
            company_selectors = [
                ".company-name a", ".company-name", ".company a", 
                "[ka='search-job-company']", ".company-text", 
                ".company-info a", ".info-company", ".job-company a",
                "a[href*='/company/']", ".name", ".text"
            ]
            company_element = None
            for selector in company_selectors:
                try:
                    company_element = job_element.find_element(By.CSS_SELECTOR, selector)
                    if company_element.text.strip():
                        print(f"✅ 使用选择器 '{selector}' 找到公司: {company_element.text.strip()}")
                        break
                except:
                    continue
            
            # 如果CSS选择器都失败，尝试XPath
            if not company_element:
                xpath_selectors = [
                    ".//a[contains(@href, '/company/')]",
                    ".//div[contains(@class, 'company')]//a",
                    ".//span[contains(@class, 'name')]"
                ]
                for xpath in xpath_selectors:
                    try:
                        company_element = job_element.find_element(By.XPATH, xpath)
                        if company_element.text.strip():
                            print(f"✅ 使用XPath '{xpath}' 找到公司: {company_element.text.strip()}")
                            break
                    except:
                        continue
            
            if not company_element:
                # 调试: 输出元素的HTML内容
                print(f"⚠️ 公司信息获取失败，元素内容: {job_element.get_attribute('innerHTML')[:200]}...")
            
            job_info['company'] = company_element.text.strip() if company_element else "公司信息获取失败"
            
            # 薪资 - 尝试多种选择器
            salary_selectors = [
                ".salary", ".red", ".job-limit .red", "[ka='search-job-salary']",
                ".job-salary", ".pay", ".price", ".money", 
                "span[class*='salary']", "span[class*='pay']", "em"
            ]
            salary_element = None
            for selector in salary_selectors:
                try:
                    salary_element = job_element.find_element(By.CSS_SELECTOR, selector)
                    if salary_element.text.strip() and any(char in salary_element.text for char in ['K', 'k', '万', '千', '元', '¥', '$']):
                        print(f"✅ 使用选择器 '{selector}' 找到薪资: {salary_element.text.strip()}")
                        break
                except:
                    continue
            
            # 如果CSS选择器失败，尝试XPath
            if not salary_element:
                xpath_selectors = [
                    ".//span[contains(text(), 'K') or contains(text(), 'k') or contains(text(), '万')]",
                    ".//em[contains(text(), 'K') or contains(text(), 'k') or contains(text(), '万')]",
                    ".//*[contains(@class, 'red')]"
                ]
                for xpath in xpath_selectors:
                    try:
                        salary_element = job_element.find_element(By.XPATH, xpath)
                        if salary_element.text.strip() and any(char in salary_element.text for char in ['K', 'k', '万', '千', '元', '¥', '$']):
                            print(f"✅ 使用XPath '{xpath}' 找到薪资: {salary_element.text.strip()}")
                            break
                    except:
                        continue
            
            if not salary_element:
                # 调试: 输出元素内容寻找薪资
                element_text = job_element.text
                print(f"⚠️ 薪资获取失败，元素文本片段: {element_text[:100]}...")
            
            job_info['salary'] = salary_element.text.strip() if salary_element else "薪资信息获取失败"
            
            # 岗位标签/要求
            tag_selectors = [
                ".tag-list .tag", ".job-tags .tag", ".info-desc span", ".job-limit span"
            ]
            job_info['tags'] = []
            for selector in tag_selectors:
                try:
                    tags_elements = job_element.find_elements(By.CSS_SELECTOR, selector)
                    if tags_elements:
                        job_info['tags'] = [tag.text.strip() for tag in tags_elements if tag.text.strip()]
                        break
                except:
                    continue
            
            # 公司信息
            company_info_selectors = [
                ".company-tag-list", ".company-info", ".company-text"
            ]
            job_info['company_info'] = ""
            for selector in company_info_selectors:
                try:
                    company_info_element = job_element.find_element(By.CSS_SELECTOR, selector)
                    if company_info_element.text.strip():
                        job_info['company_info'] = company_info_element.text.strip()
                        break
                except:
                    continue
            
            # 如果获取到了基本信息，认为提取成功
            if job_info['title'] != "标题获取失败":
                return job_info
            else:
                print(f"⚠️ 岗位信息提取不完整: {job_info}")
                return job_info  # 即使不完整也返回，让AI去判断
                
        except Exception as e:
            print(f"提取岗位信息失败: {e}")
            # 返回基础信息，至少能看到元素内容
            try:
                return {
                    'title': job_element.text[:50] + "..." if len(job_element.text) > 50 else job_element.text,
                    'company': "信息提取失败",
                    'salary': "未知",
                    'tags': [],
                    'company_info': "",
                    'url': ""
                }
            except:
                return None
    
    def get_job_detail(self, job_url):
        """获取岗位详情 - 增强版本"""
        try:
            print(f"📄 获取岗位详情: {job_url}")
            self.browser.driver.get(job_url)
            self.browser.random_delay(3, 5)
            
            job_detail = {
                'url': job_url,
                'job_description': '',
                'job_requirements': '',
                'company_details': '',
                'benefits': '',
                'department': '',
                'work_location': '',
                'experience_required': '',
                'education_required': ''
            }
            
            # 1. 获取职位描述 - 多种选择器
            description_selectors = [
                ".job-sec-text",
                ".job-detail-text", 
                ".job-detail-section .text",
                ".job-desc .detail-content",
                ".job-content .text",
                "[data-ka='job-detail-desc']"
            ]
            
            for selector in description_selectors:
                try:
                    desc_element = self.browser.driver.find_element(By.CSS_SELECTOR, selector)
                    if desc_element.text.strip():
                        job_detail['job_description'] = desc_element.text.strip()
                        print(f"✅ 使用选择器 '{selector}' 获取到职位描述")
                        break
                except:
                    continue
            
            # 2. 获取岗位要求 - 通常在描述的特定部分
            requirements_keywords = ["任职要求", "岗位要求", "职位要求", "要求", "Requirement"]
            description_text = job_detail['job_description']
            
            for keyword in requirements_keywords:
                if keyword in description_text:
                    # 提取关键词后的内容作为要求
                    idx = description_text.find(keyword)
                    if idx != -1:
                        # 获取关键词后的内容，限制长度
                        requirements_part = description_text[idx:idx+500]
                        job_detail['job_requirements'] = requirements_part
                        break
            
            # 3. 获取公司详细信息
            company_selectors = [
                ".company-info .intro",
                ".company-detail .text", 
                ".company-content",
                ".company-desc",
                "[data-ka='company-intro']"
            ]
            
            for selector in company_selectors:
                try:
                    company_element = self.browser.driver.find_element(By.CSS_SELECTOR, selector)
                    if company_element.text.strip():
                        job_detail['company_details'] = company_element.text.strip()
                        print(f"✅ 获取到公司详情")
                        break
                except:
                    continue
            
            # 4. 获取福利待遇信息
            benefits_selectors = [
                ".job-tags .tag",
                ".welfare-list .welfare-item",
                ".benefits .benefit-item",
                ".job-benefit .item"
            ]
            
            benefits_list = []
            for selector in benefits_selectors:
                try:
                    benefit_elements = self.browser.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in benefit_elements:
                        benefit_text = element.text.strip()
                        if benefit_text and len(benefit_text) > 1:
                            benefits_list.append(benefit_text)
                    if benefits_list:
                        job_detail['benefits'] = ', '.join(benefits_list)
                        print(f"✅ 获取到福利信息: {len(benefits_list)}项")
                        break
                except:
                    continue
            
            # 5. 获取其他详细信息
            try:
                # 工作地点
                location_selectors = [".location-detail", ".work-addr", ".job-location"]
                for selector in location_selectors:
                    try:
                        location_element = self.browser.driver.find_element(By.CSS_SELECTOR, selector)
                        if location_element.text.strip():
                            job_detail['work_location'] = location_element.text.strip()
                            break
                    except:
                        continue
                
                # 经验要求
                exp_selectors = [".job-primary .red:contains('经验')", ".experience-require"]
                for selector in exp_selectors:
                    try:
                        exp_element = self.browser.driver.find_element(By.CSS_SELECTOR, selector)
                        if exp_element.text.strip():
                            job_detail['experience_required'] = exp_element.text.strip()
                            break
                    except:
                        continue
                        
            except Exception as e:
                print(f"⚠️ 获取额外信息时出错: {e}")
            
            # 输出获取情况统计
            filled_fields = sum(1 for v in job_detail.values() if v)
            print(f"📊 详情获取完成: {filled_fields}/{len(job_detail)} 个字段有内容")
            
            return job_detail
            
        except Exception as e:
            print(f"❌ 获取岗位详情失败: {e}")
            return {
                'url': job_url,
                'job_description': '',
                'job_requirements': '',
                'company_details': '',
                'benefits': '',
                'department': '',
                'work_location': '',
                'experience_required': '',
                'education_required': ''
            }
    
    def close(self):
        """关闭爬虫"""
        self.browser.close()