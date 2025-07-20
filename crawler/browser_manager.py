import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import os
import json


class BrowserManager:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.cookies_file = "data/cookies.json"
        
    def setup_browser(self):
        """初始化浏览器"""
        try:
            # 简化配置，提高兼容性
            options = uc.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")
            
            # 随机User-Agent
            user_agents = [
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
            options.add_argument(f"--user-agent={random.choice(user_agents)}")
            
            print("正在启动Chrome浏览器...")
            self.driver = uc.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 10)
            
            print("浏览器初始化成功")
            return True
        except Exception as e:
            print(f"浏览器初始化失败: {e}")
            print("尝试简化模式...")
            
            # 如果失败，尝试最简配置
            try:
                self.driver = uc.Chrome()
                self.wait = WebDriverWait(self.driver, 10)
                print("浏览器初始化成功（简化模式）")
                return True
            except Exception as e2:
                print(f"简化模式也失败: {e2}")
                return False
    
    def save_cookies(self):
        """保存cookies"""
        try:
            os.makedirs(os.path.dirname(self.cookies_file), exist_ok=True)
            with open(self.cookies_file, 'w') as f:
                json.dump(self.driver.get_cookies(), f)
            print("Cookies保存成功")
        except Exception as e:
            print(f"保存cookies失败: {e}")
    
    def load_cookies(self):
        """加载cookies"""
        try:
            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, 'r') as f:
                    cookies = json.load(f)
                for cookie in cookies:
                    self.driver.add_cookie(cookie)
                print("Cookies加载成功")
                return True
        except Exception as e:
            print(f"加载cookies失败: {e}")
        return False
    
    def random_delay(self, min_seconds=1, max_seconds=3):
        """随机延迟"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def simulate_human_behavior(self):
        """模拟人类行为"""
        # 随机滚动
        scroll_height = random.randint(300, 800)
        self.driver.execute_script(f"window.scrollBy(0, {scroll_height});")
        self.random_delay(0.5, 1.5)
        
        # 随机小幅度滚动
        small_scroll = random.randint(-100, 100)
        self.driver.execute_script(f"window.scrollBy(0, {small_scroll});")
        self.random_delay(0.3, 0.8)
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            print("浏览器已关闭")