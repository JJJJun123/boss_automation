#!/usr/bin/env python3
"""
MCP (Model Context Protocol) 客户端
用于连接和控制Playwright MCP服务器
"""

import json
import asyncio
import subprocess
import logging
import time
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MCPResponse:
    """MCP响应数据结构"""
    success: bool
    data: Any = None
    error: str = None


class PlaywrightMCPClient:
    """Playwright MCP客户端"""
    
    def __init__(self, headless: bool = False, browser: str = "chrome"):
        self.headless = headless
        self.browser = browser
        self.process = None
        self.session_active = False
        
    async def start_server(self) -> bool:
        """启动Playwright MCP服务器"""
        try:
            logger.info("🎭 启动Playwright MCP服务器...")
            
            # 构建启动命令
            cmd = ["npx", "@playwright/mcp@latest"]
            
            # 添加参数
            if self.headless:
                cmd.append("--headless")
            
            cmd.extend([
                "--browser", self.browser,
                "--port", "3000",  # 指定端口
                "--host", "localhost"
            ])
            
            logger.info(f"🚀 执行命令: {' '.join(cmd)}")
            
            # 启动进程
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE
            )
            
            # 等待服务器启动
            await asyncio.sleep(3)
            
            if self.process.returncode is None:
                self.session_active = True
                logger.info("✅ Playwright MCP服务器启动成功")
                return True
            else:
                logger.error("❌ Playwright MCP服务器启动失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 启动MCP服务器失败: {e}")
            return False
    
    async def send_command(self, command: str, params: Dict[str, Any] = None) -> MCPResponse:
        """发送命令到MCP服务器"""
        if not self.session_active or not self.process:
            return MCPResponse(success=False, error="MCP服务器未启动")
        
        try:
            # 构建MCP消息
            message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": command,
                "params": params or {}
            }
            
            # 发送消息
            message_json = json.dumps(message) + "\n"
            self.process.stdin.write(message_json.encode())
            await self.process.stdin.drain()
            
            # 等待响应
            response_line = await asyncio.wait_for(
                self.process.stdout.readline(), 
                timeout=30.0
            )
            
            if response_line:
                response_data = json.loads(response_line.decode().strip())
                if "result" in response_data:
                    return MCPResponse(success=True, data=response_data["result"])
                elif "error" in response_data:
                    return MCPResponse(success=False, error=response_data["error"])
            
            return MCPResponse(success=False, error="无响应")
            
        except asyncio.TimeoutError:
            return MCPResponse(success=False, error="命令超时")
        except Exception as e:
            logger.error(f"❌ 发送命令失败: {e}")
            return MCPResponse(success=False, error=str(e))
    
    async def navigate_to_page(self, url: str) -> MCPResponse:
        """导航到指定页面"""
        logger.info(f"🌐 导航到: {url}")
        return await self.send_command("navigate", {"url": url})
    
    async def search_jobs(self, keyword: str, city_code: str = "101280600") -> MCPResponse:
        """在Boss直聘搜索岗位"""
        logger.info(f"🔍 搜索岗位: {keyword}")
        
        # 构建搜索URL
        search_url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}"
        
        # 导航到搜索页面
        nav_result = await self.navigate_to_page(search_url)
        if not nav_result.success:
            return nav_result
        
        # 等待页面加载
        await asyncio.sleep(2)
        
        # 提取岗位信息
        return await self.extract_job_listings()
    
    async def extract_job_listings(self) -> MCPResponse:
        """提取岗位列表"""
        logger.info("📋 提取岗位信息...")
        
        # 使用自然语言指令提取岗位
        extract_command = {
            "action": "extract_data",
            "selector": ".job-list-item, .job-card-wrapper",
            "fields": {
                "title": ".job-name, .job-title",
                "company": ".company-name",
                "salary": ".salary",
                "location": ".job-area",
                "tags": ".tag-list .tag",
                "url": "a[href]"
            }
        }
        
        return await self.send_command("extract", extract_command)
    
    async def take_screenshot(self, filename: str = None) -> MCPResponse:
        """截取页面截图"""
        if not filename:
            filename = f"screenshot_{asyncio.get_event_loop().time()}.png"
        
        logger.info(f"📸 截取截图: {filename}")
        return await self.send_command("screenshot", {"path": filename})
    
    async def close(self):
        """关闭MCP客户端"""
        try:
            if self.process and self.process.returncode is None:
                logger.info("🔚 关闭Playwright MCP服务器")
                self.process.terminate()
                await self.process.wait()
            
            self.session_active = False
            
        except Exception as e:
            logger.error(f"❌ 关闭MCP客户端失败: {e}")


# 同步包装器，用于兼容现有代码
class PlaywrightMCPSync:
    """Playwright MCP同步包装器 - 简化版本"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.process = None
        self.browser_started = False
    
    def start(self) -> bool:
        """启动MCP服务器并打开浏览器"""
        try:
            logger.info("🎭 启动Playwright MCP服务器...")
            
            # 构建启动命令
            cmd = ["npx", "@playwright/mcp@latest"]
            
            # 添加参数 - 确保浏览器可见
            if not self.headless:
                # 不添加--headless参数，默认就是有头模式
                pass
            else:
                cmd.append("--headless")
            
            cmd.extend([
                "--browser", "chrome",
                "--port", "3000"
            ])
            
            logger.info(f"🚀 执行命令: {' '.join(cmd)}")
            
            # 启动进程
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE
            )
            
            # 等待服务器启动
            logger.info("⏳ 等待MCP服务器启动...")
            time.sleep(5)  # 给更多时间启动
            
            # 检查进程是否仍在运行
            if self.process.poll() is None:
                self.browser_started = True
                logger.info("✅ Playwright MCP服务器启动成功！")
                logger.info("👀 你应该能看到Chrome浏览器窗口打开")
                return True
            else:
                # 获取错误信息
                stdout, stderr = self.process.communicate()
                logger.error(f"❌ MCP服务器启动失败")
                if stderr:
                    logger.error(f"错误信息: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 启动MCP服务器失败: {e}")
            return False
    
    def search_jobs(self, keyword: str, city_code: str = "101280600", max_jobs: int = 20) -> List[Dict]:
        """搜索岗位（当前为演示版本）"""
        if not self.browser_started:
            logger.error("❌ MCP客户端未启动")
            return []
        
        logger.info(f"🔍 MCP浏览器已启动，模拟搜索: {keyword}")
        logger.info("💡 用户可以在打开的浏览器中手动导航到Boss直聘进行搜索")
        
        # 等待一段时间，让用户看到浏览器
        time.sleep(2)
        
        # 返回空结果，触发备用数据
        return []
    
    def close(self):
        """关闭客户端"""
        try:
            if self.process and self.process.poll() is None:
                logger.info("🔚 关闭Playwright MCP服务器")
                self.process.terminate()
                self.process.wait(timeout=5)
            self.browser_started = False
        except Exception as e:
            logger.error(f"❌ 关闭MCP客户端失败: {e}")


if __name__ == "__main__":
    # 测试MCP客户端
    async def test_mcp():
        client = PlaywrightMCPClient(headless=False)
        
        if await client.start_server():
            print("✅ MCP服务器启动成功")
            
            # 测试搜索
            result = await client.search_jobs("数据分析")
            print(f"搜索结果: {result}")
            
            await client.close()
        else:
            print("❌ MCP服务器启动失败")
    
    # 运行测试
    asyncio.run(test_mcp())