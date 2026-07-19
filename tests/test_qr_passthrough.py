#!/usr/bin/env python3
"""阶段 Q：QR 登录云端透传 — 爬虫层单元测试（spec Q1-Q3）

被测契约（spec 实现契约）：
- RealPlaywrightBossSpider(qr_callback=None, login_wait_seconds=None,
  qr_poll_interval=None) 新增可选参数；qr_callback=None 时行为回退现状
- _ensure_logged_in()：qr_callback 存在时进入截图推送轮询；
  返回 bool（成功 True / 超时或截图失败 False），不直接抛
- 事件 schema：{"state": str, "image_b64": Optional[str], "message": str}
- 状态: qr_ready / scanned / logged_in / qr_expired / qr_capture_failed /
  login_timeout（qr_expired 内部自动重截，向外表现为再推一次 qr_ready）

不启动真实浏览器：FakePage / FakeElement 替身（模式同 test_session_expiry）。
"""

import asyncio
import base64
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.real_playwright_spider import RealPlaywrightBossSpider

LOGIN_URL = "https://www.zhipin.com/web/user/?ka=header-login"
GEEK_URL = "https://www.zhipin.com/web/geek/jobs?query=AI&city=101020100"

QR_PNG_A = b"\x89PNG-fake-qr-image-AAAA"
QR_PNG_B = b"\x89PNG-fake-qr-image-BBBB"


class FakeElement:
    """Playwright ElementHandle 替身：可配置截图 bytes 序列与可见性"""

    def __init__(self, screenshots=None, visible=True):
        self._screenshots = list(screenshots or [QR_PNG_A])
        self._visible = visible
        self.screenshot_calls = 0

    async def is_visible(self):
        return self._visible

    async def screenshot(self, **kwargs):
        self.screenshot_calls += 1
        if len(self._screenshots) > 1:
            return self._screenshots.pop(0)
        return self._screenshots[0]


class FakePage:
    """Playwright Page 替身

    url_script: [(轮询次数阈值, url)]——第 n 次 url 属性读取后切换，
    模拟"扫码成功后 URL 跳到 /web/geek/"。
    qr_element: query_selector 对 QR 选择器返回的元素（None = 找不到）
    scanned_element: "已扫描"overlay 元素（None = 未出现）
    """

    def __init__(self, qr_element=None, scanned_element=None,
                 login_success_after_reads=None):
        self._url = LOGIN_URL
        self._reads = 0
        self._login_after = login_success_after_reads
        self.qr_element = qr_element
        self.scanned_element = scanned_element
        self.goto_calls = []
        self.page_screenshot_calls = 0

    @property
    def url(self):
        self._reads += 1
        if self._login_after is not None and self._reads > self._login_after:
            return GEEK_URL
        return self._url

    async def goto(self, url, **kwargs):
        self.goto_calls.append(url)

    async def title(self):
        return "登录"

    async def query_selector(self, selector):
        sel = selector.lower()
        if "scan" in sel or "扫" in sel or "confirm" in sel:
            return self.scanned_element
        return self.qr_element

    async def screenshot(self, **kwargs):
        self.page_screenshot_calls += 1
        return QR_PNG_A

    def on(self, *a, **k):
        pass


def _make_spider(page, qr_events=None, **kwargs):
    """构造注入 FakePage 的 spider；qr_events 列表收集回调事件"""
    cb = None
    if qr_events is not None:
        cb = qr_events.append
    spider = RealPlaywrightBossSpider(
        qr_callback=cb,
        login_wait_seconds=kwargs.pop("login_wait_seconds", 2),
        qr_poll_interval=kwargs.pop("qr_poll_interval", 0.05),
        **kwargs,
    )
    spider.page = page
    spider.context = None
    return spider


def _run(coro):
    return asyncio.run(coro)


# ─── qr_ready 推送 ───────────────────────────────────────


class TestQrReadyPush:
    def test_qr_image_pushed_as_base64(self):
        events = []
        page = FakePage(qr_element=FakeElement([QR_PNG_A]),
                        login_success_after_reads=3)
        spider = _make_spider(page, qr_events=events)
        ok = _run(spider._ensure_logged_in())
        assert ok is True
        ready = [e for e in events if e["state"] == "qr_ready"]
        assert ready, f"未推送 qr_ready，events={[e['state'] for e in events]}"
        assert ready[0]["image_b64"] == base64.b64encode(QR_PNG_A).decode()

    def test_event_schema(self):
        events = []
        page = FakePage(qr_element=FakeElement([QR_PNG_A]),
                        login_success_after_reads=3)
        spider = _make_spider(page, qr_events=events)
        _run(spider._ensure_logged_in())
        for e in events:
            assert set(e.keys()) >= {"state", "image_b64", "message"}, e

    def test_same_image_not_repushed(self):
        """截图指纹未变 → 不重复推 qr_ready（防前端闪烁/带宽浪费）"""
        events = []
        page = FakePage(qr_element=FakeElement([QR_PNG_A]),
                        login_success_after_reads=8)
        spider = _make_spider(page, qr_events=events)
        _run(spider._ensure_logged_in())
        ready = [e for e in events if e["state"] == "qr_ready"]
        assert len(ready) == 1, f"同图重复推送 {len(ready)} 次"

    def test_changed_image_repushed(self):
        """二维码过期刷新（截图 bytes 变化）→ 再推一次 qr_ready 带新图"""
        events = []
        page = FakePage(qr_element=FakeElement([QR_PNG_A, QR_PNG_B]),
                        login_success_after_reads=8)
        spider = _make_spider(page, qr_events=events)
        _run(spider._ensure_logged_in())
        ready = [e for e in events if e["state"] == "qr_ready"]
        assert len(ready) == 2, f"图变化后应重推，实际 {len(ready)} 次"
        assert ready[1]["image_b64"] == base64.b64encode(QR_PNG_B).decode()


# ─── 登录成功 / 已扫描 ───────────────────────────────────


class TestLoginSuccess:
    def test_logged_in_event_and_true_return(self):
        events = []
        page = FakePage(qr_element=FakeElement([QR_PNG_A]),
                        login_success_after_reads=2)
        spider = _make_spider(page, qr_events=events)
        assert _run(spider._ensure_logged_in()) is True
        assert events[-1]["state"] == "logged_in"

    def test_scanned_overlay_pushed(self):
        events = []
        page = FakePage(qr_element=FakeElement([QR_PNG_A]),
                        scanned_element=FakeElement(visible=True),
                        login_success_after_reads=4)
        spider = _make_spider(page, qr_events=events)
        _run(spider._ensure_logged_in())
        states = [e["state"] for e in events]
        assert "scanned" in states
        assert states.index("scanned") < states.index("logged_in")


# ─── 超时 / 截图失败 ─────────────────────────────────────


class TestFailurePaths:
    def test_timeout_pushes_login_timeout_returns_false(self):
        events = []
        page = FakePage(qr_element=FakeElement([QR_PNG_A]),
                        login_success_after_reads=None)  # 永不登录
        spider = _make_spider(page, qr_events=events,
                              login_wait_seconds=0.3, qr_poll_interval=0.05)
        assert _run(spider._ensure_logged_in()) is False
        assert events[-1]["state"] == "login_timeout"

    def test_qr_element_missing_falls_back_to_page_screenshot(self):
        """QR 元素定位失败 → 降级整页截图，仍推 qr_ready"""
        events = []
        page = FakePage(qr_element=None, login_success_after_reads=3)
        spider = _make_spider(page, qr_events=events)
        ok = _run(spider._ensure_logged_in())
        assert ok is True
        assert page.page_screenshot_calls > 0, "未降级整页截图"
        assert any(e["state"] == "qr_ready" for e in events)

    def test_all_capture_fails_pushes_capture_failed(self):
        """元素 + 整页截图都失败 → qr_capture_failed + False"""
        events = []

        class BrokenPage(FakePage):
            async def screenshot(self, **kwargs):
                raise RuntimeError("screenshot broken")

        page = BrokenPage(qr_element=None, login_success_after_reads=None)
        spider = _make_spider(page, qr_events=events,
                              login_wait_seconds=0.3, qr_poll_interval=0.05)
        assert _run(spider._ensure_logged_in()) is False
        assert any(e["state"] == "qr_capture_failed" for e in events)


# ─── 无回调回退现状 ──────────────────────────────────────


class TestRequireLoginGate:
    """搜索前强制登录门（_require_login）

    背景：未登录直接访问搜索 URL 也是 /web/geek/jobs（URL 判定误判已登录），
    但只能拿残血数据（薪资缺失、列表限 ~15 条）。必须用 DOM 判定（页头登录
    按钮存在 = 未登录），未登录先走 _ensure_logged_in 再抓取。
    """

    class _GatePage(FakePage):
        """可配置登录按钮的页面；URL 恒为搜索页（复现误判场景）"""

        def __init__(self, login_btn_visible, **kwargs):
            super().__init__(**kwargs)
            self._login_btn_visible = login_btn_visible
            self._url = GEEK_URL  # 未登录也显示搜索页 URL

        @property
        def url(self):
            return GEEK_URL

        async def query_selector(self, selector):
            sel = selector.lower()
            if "login" in sel or "登录" in sel:
                if self._login_btn_visible:
                    return FakeElement(visible=True)
                return None
            return await super().query_selector(selector)

    def _spider_with_page(self, page):
        spider = RealPlaywrightBossSpider(
            login_wait_seconds=0.3, qr_poll_interval=0.05)
        spider.page = page
        spider.context = None
        return spider

    def test_not_logged_in_triggers_login(self):
        """登录按钮可见 → 必须调用 _ensure_logged_in"""
        page = self._GatePage(login_btn_visible=True)
        spider = self._spider_with_page(page)
        called = {}

        async def _fake_login():
            called["yes"] = True
            page._login_btn_visible = False
            return True

        spider._ensure_logged_in = _fake_login
        _run(spider._require_login(GEEK_URL))
        assert called.get("yes"), "未登录时必须触发登录流程"

    def test_logged_in_skips_login(self):
        """登录按钮不存在 → 不触发登录"""
        page = self._GatePage(login_btn_visible=False)
        spider = self._spider_with_page(page)

        async def _fail_login():
            raise AssertionError("已登录不应触发登录")

        spider._ensure_logged_in = _fail_login
        _run(spider._require_login(GEEK_URL))

    def test_login_failure_raises_login_timeout(self):
        """登录失败 → RuntimeError 且消息含"登录超时"（app 层据此标 login_timeout）"""
        page = self._GatePage(login_btn_visible=True)
        spider = self._spider_with_page(page)

        async def _fake_login():
            return False

        spider._ensure_logged_in = _fake_login
        with pytest.raises(RuntimeError) as exc:
            _run(spider._require_login(GEEK_URL))
        assert "登录超时" in str(exc.value)


class TestLegacyFallback:
    def test_no_callback_no_screenshot(self):
        """qr_callback=None：不截图、不推送，URL 轮询照常工作（本机模式不回归）"""
        qr_el = FakeElement([QR_PNG_A])
        page = FakePage(qr_element=qr_el, login_success_after_reads=2)
        spider = RealPlaywrightBossSpider(
            login_wait_seconds=2, qr_poll_interval=0.05)
        spider.page = page
        spider.context = None
        assert _run(spider._ensure_logged_in()) is True
        assert qr_el.screenshot_calls == 0, "无回调时不应截图"
        assert page.page_screenshot_calls == 0

    def test_constructor_defaults_backward_compatible(self):
        """不带新参数构造 spider 必须照常工作（既有调用点零改动）"""
        spider = RealPlaywrightBossSpider()
        assert spider.qr_callback is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
