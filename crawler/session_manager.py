#!/usr/bin/env python3
"""
会话管理器
处理登录状态、Cookie持久化和会话恢复
"""

import os
import json
import logging
import time
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from playwright.async_api import Page, BrowserContext

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器 - 负责登录状态和Cookie管理"""
    
    def __init__(self, cookie_dir: str = None):
        self.cookie_dir = cookie_dir or os.path.join(os.path.dirname(__file__), 'sessions')
        self.ensure_cookie_dir()
        self.current_session = None
        
    def ensure_cookie_dir(self):
        """确保Cookie目录存在"""
        os.makedirs(self.cookie_dir, exist_ok=True)
        
    def get_session_file_path(self, domain: str = "zhipin.com") -> str:
        """获取会话文件路径"""
        return os.path.join(self.cookie_dir, f"{domain}_session.json")
    
    async def load_session(self, context: BrowserContext, domain: str = "zhipin.com") -> bool:
        """
        加载保存的会话
        
        Args:
            context: Playwright浏览器上下文
            domain: 域名
            
        Returns:
            bool: 是否成功加载会话
        """
        session_file = self.get_session_file_path(domain)
        
        if not os.path.exists(session_file):
            logger.info(f"📄 会话文件不存在: {session_file}")
            return False
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # 检查会话是否过期
            if self._is_session_expired(session_data):
                logger.warning("⏰ 会话已过期，需要重新登录")
                os.remove(session_file)  # 删除过期会话
                return False
            
            # 加载cookies
            cookies = session_data.get('cookies', [])
            if cookies:
                await context.add_cookies(cookies)
                logger.info(f"✅ 已加载 {len(cookies)} 个cookies")
                
                # 加载其他会话数据
                self.current_session = session_data
                return True
            
        except Exception as e:
            logger.error(f"❌ 加载会话失败: {e}")
            # 删除损坏的会话文件
            try:
                os.remove(session_file)
            except:
                pass
        
        return False
    
    async def save_session(self, context: BrowserContext, page: Page, domain: str = "zhipin.com") -> bool:
        """
        保存当前会话
        
        Args:
            context: Playwright浏览器上下文
            page: 当前页面
            domain: 域名
            
        Returns:
            bool: 是否成功保存会话
        """
        try:
            # 获取cookies
            cookies = await context.cookies()
            
            # 过滤并清洗cookies
            cleaned_cookies = self._clean_cookies(cookies, domain)
            
            if not cleaned_cookies:
                logger.warning("⚠️ 没有有效的cookies可保存")
                return False
            
            # 获取用户信息（如果可用）
            user_info = await self._extract_user_info(page)
            
            # 构建会话数据
            session_data = {
                'domain': domain,
                'cookies': cleaned_cookies,
                'user_info': user_info,
                'save_time': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(days=7)).isoformat(),  # 7天后过期
                'page_url': page.url,
                'user_agent': await page.evaluate('navigator.userAgent'),
                'session_metadata': {
                    'browser_version': await self._get_browser_version(page),
                    'screen_resolution': await self._get_screen_info(page),
                    'login_method': 'auto_detected'
                }
            }
            
            # 保存到文件
            session_file = self.get_session_file_path(domain)
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            
            self.current_session = session_data
            logger.info(f"✅ 会话已保存: {session_file}")
            logger.info(f"   - {len(cleaned_cookies)} 个cookies")
            logger.info(f"   - 用户: {user_info.get('name', '未知')}")
            logger.info(f"   - 过期时间: {session_data['expires_at']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存会话失败: {e}")
            return False
    
    def _clean_cookies(self, cookies: List[Dict], domain: str) -> List[Dict]:
        """清洗和过滤cookies"""
        cleaned_cookies = []
        
        for cookie in cookies:
            # 只保留相关域名的cookies
            if domain in cookie.get('domain', ''):
                # 清理无效字段
                cleaned_cookie = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie['domain'],
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', False),
                    'httpOnly': cookie.get('httpOnly', False),
                    'sameSite': cookie.get('sameSite', 'Lax')
                }
                
                # 添加过期时间（如果有）
                if 'expires' in cookie and cookie['expires'] > 0:
                    cleaned_cookie['expires'] = cookie['expires']
                
                # 过滤掉一些无用的cookies
                if not self._is_useful_cookie(cookie['name']):
                    continue
                
                cleaned_cookies.append(cleaned_cookie)
        
        return cleaned_cookies
    
    def _is_useful_cookie(self, cookie_name: str) -> bool:
        """判断cookie是否有用"""
        # 保留的关键cookies
        useful_patterns = [
            'login', 'session', 'token', 'auth', 'user', 'uid', 'sid',
            'boss', 'zhipin', 'geek', 'wt2', 'suc', '__zp_stoken__'
        ]
        
        # 过滤掉的无用cookies
        useless_patterns = [
            'ga', 'gtm', 'utm', 'track', 'analytics', 'advertisement',
            'ads', '_gid', '_gat', '__utma', '__utmb', '__utmc', '__utmz'
        ]
        
        cookie_lower = cookie_name.lower()
        
        # 检查是否是有用的cookie
        for pattern in useful_patterns:
            if pattern in cookie_lower:
                return True
        
        # 检查是否是无用的cookie
        for pattern in useless_patterns:
            if pattern in cookie_lower:
                return False
        
        # 默认保留未知的cookie
        return True
    
    async def _extract_user_info(self, page: Page) -> Dict[str, Any]:
        """从页面提取用户信息"""
        user_info = {'name': '', 'avatar': '', 'company': ''}
        
        try:
            # 尝试多种用户信息选择器
            user_selectors = [
                '.nav-figure img',  # 用户头像
                '.user-name',       # 用户名
                '.geek-name',       # Boss直聘求职者名称
                '.dropdown-avatar', # 下拉头像
                '[class*="avatar"]' # 包含avatar的元素
            ]
            
            for selector in user_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        if 'img' in selector:
                            # 获取头像URL
                            src = await element.get_attribute('src')
                            if src:
                                user_info['avatar'] = src
                        else:
                            # 获取用户名
                            text = await element.inner_text()
                            if text and text.strip():
                                user_info['name'] = text.strip()
                        
                        if user_info['name'] or user_info['avatar']:
                            break
                except:
                    continue
            
            # 尝试从页面标题或其他位置获取用户信息
            if not user_info['name']:
                title = await page.title()
                if '的个人主页' in title:
                    user_info['name'] = title.replace('的个人主页', '').strip()
            
        except Exception as e:
            logger.debug(f"提取用户信息失败: {e}")
        
        return user_info
    
    async def _get_browser_version(self, page: Page) -> str:
        """获取浏览器版本信息"""
        try:
            return await page.evaluate('navigator.userAgent')
        except:
            return 'unknown'
    
    async def _get_screen_info(self, page: Page) -> Dict[str, int]:
        """获取屏幕信息"""
        try:
            return await page.evaluate('''() => ({
                width: screen.width,
                height: screen.height,
                viewport_width: window.innerWidth,
                viewport_height: window.innerHeight
            })''')
        except:
            return {'width': 1920, 'height': 1080, 'viewport_width': 1280, 'viewport_height': 800}
    
    def _is_session_expired(self, session_data: Dict) -> bool:
        """检查会话是否过期"""
        try:
            expires_at = session_data.get('expires_at')
            if not expires_at:
                return True
            
            expire_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            return datetime.now() > expire_time
            
        except Exception as e:
            logger.debug(f"检查会话过期时间失败: {e}")
            return True
    
    async def check_login_status(self, page: Page, domain: str = "zhipin.com") -> bool:
        """
        检查登录状态
        
        Args:
            page: 当前页面
            domain: 域名
            
        Returns:
            bool: 是否已登录
        """
        try:
            # 等待页面加载
            await asyncio.sleep(2)
            
            # Boss直聘特定的登录状态检查
            if domain == "zhipin.com":
                return await self._check_zhipin_login_status(page)
            
            # 通用登录状态检查
            return await self._check_generic_login_status(page)
            
        except Exception as e:
            logger.error(f"❌ 检查登录状态失败: {e}")
            return False
    
    async def _check_zhipin_login_status(self, page: Page) -> bool:
        """检查Boss直聘登录状态"""
        try:
            # 检查用户相关元素
            user_selectors = [
                '.nav-figure img[src*="avatar"]',  # 用户头像
                '.geek-nav .figure img',           # 求职者导航头像
                '.dropdown-avatar',                # 下拉头像
                '[class*="avatar"][src]',          # 任何有src的头像元素
                '.user-name'                       # 用户名元素
            ]
            
            for selector in user_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        # 进一步验证元素内容
                        if 'img' in selector:
                            src = await element.get_attribute('src')
                            if src and ('avatar' in src or 'head' in src):
                                logger.info(f"✓ 检测到用户头像: {selector}")
                                return True
                        else:
                            text = await element.inner_text()
                            if text and len(text.strip()) > 0:
                                logger.info(f"✓ 检测到用户信息: {text[:20]}...")
                                return True
                except:
                    continue
            
            # 检查是否有登录按钮（反向验证）
            login_selectors = [
                'a[href*="login"]',
                'button:has-text("登录")',
                '.login-btn',
                '.sign-in-btn'
            ]
            
            for selector in login_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.info(f"✗ 检测到登录按钮: {selector}")
                        return False
                except:
                    continue
            
            # 检查URL是否包含登录相关路径
            current_url = page.url
            if any(path in current_url for path in ['/login', '/signin', '/register']):
                logger.info(f"✗ 当前在登录页面: {current_url}")
                return False
            
            # 如果没有找到登录按钮，且URL不是登录页，认为已登录
            logger.info("? 无法明确判断登录状态，假设已登录")
            return True
            
        except Exception as e:
            logger.error(f"检查Boss直聘登录状态失败: {e}")
            return False
    
    async def _check_generic_login_status(self, page: Page) -> bool:
        """通用登录状态检查"""
        try:
            # 通用的已登录指示器
            logged_in_selectors = [
                '[class*="user"]', '[class*="profile"]', '[class*="avatar"]',
                '[class*="logout"]', '[class*="account"]', '[class*="dashboard"]'
            ]
            
            for selector in logged_in_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        for element in elements:
                            if await element.is_visible():
                                return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"通用登录状态检查失败: {e}")
            return False
    
    async def wait_for_login(self, page: Page, timeout: int = 300, domain: str = "zhipin.com") -> bool:
        """
        等待用户完成登录
        
        Args:
            page: 当前页面
            timeout: 超时时间（秒）
            domain: 域名
            
        Returns:
            bool: 是否登录成功
        """
        logger.info("=" * 50)
        logger.info("🔐 等待用户登录")
        logger.info("请在浏览器窗口中完成以下操作：")
        logger.info("1. 点击页面右上角的 '登录' 按钮")
        logger.info("2. 使用扫码或账号密码登录")
        logger.info("3. 登录成功后，系统会自动继续")
        logger.info("=" * 50)
        
        start_time = time.time()
        check_interval = 3  # 每3秒检查一次
        
        while time.time() - start_time < timeout:
            try:
                # 检查登录状态
                if await self.check_login_status(page, domain):
                    logger.info("✅ 检测到登录成功!")
                    return True
                
                # 显示剩余时间
                elapsed = time.time() - start_time
                remaining = int(timeout - elapsed)
                logger.info(f"⏳ 等待登录中... (剩余 {remaining} 秒)")
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.debug(f"等待登录时出错: {e}")
                await asyncio.sleep(check_interval)
        
        logger.error(f"❌ 登录等待超时 ({timeout}秒)")
        return False
    
    def get_session_info(self) -> Dict[str, Any]:
        """获取当前会话信息"""
        if not self.current_session:
            return {'status': 'no_session'}
        
        return {
            'status': 'active',
            'domain': self.current_session.get('domain'),
            'user_info': self.current_session.get('user_info', {}),
            'save_time': self.current_session.get('save_time'),
            'expires_at': self.current_session.get('expires_at'),
            'cookies_count': len(self.current_session.get('cookies', [])),
            'is_expired': self._is_session_expired(self.current_session)
        }
    
    def clear_session(self, domain: str = "zhipin.com") -> bool:
        """清除保存的会话"""
        try:
            session_file = self.get_session_file_path(domain)
            if os.path.exists(session_file):
                os.remove(session_file)
                logger.info(f"🗑️ 已清除会话文件: {session_file}")
            
            self.current_session = None
            return True
            
        except Exception as e:
            logger.error(f"❌ 清除会话失败: {e}")
            return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有保存的会话"""
        sessions = []
        
        try:
            for filename in os.listdir(self.cookie_dir):
                if filename.endswith('_session.json'):
                    session_file = os.path.join(self.cookie_dir, filename)
                    try:
                        with open(session_file, 'r', encoding='utf-8') as f:
                            session_data = json.load(f)
                        
                        sessions.append({
                            'file': filename,
                            'domain': session_data.get('domain'),
                            'user_name': session_data.get('user_info', {}).get('name', 'Unknown'),
                            'save_time': session_data.get('save_time'),
                            'expires_at': session_data.get('expires_at'),
                            'is_expired': self._is_session_expired(session_data),
                            'cookies_count': len(session_data.get('cookies', []))
                        })
                    except Exception as e:
                        logger.debug(f"读取会话文件失败 {filename}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"列出会话失败: {e}")
        
        return sessions