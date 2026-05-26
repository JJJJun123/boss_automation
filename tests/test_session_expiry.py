#!/usr/bin/env python3
"""
会话失效检测单元测试

验证爬虫在被 Boss 直聘弹回登录/安全验证页时，能正确识别
（_is_on_login_page），从而触发重新登录流程，而非默默抓取失败。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.real_playwright_spider import RealPlaywrightBossSpider


class FakePage:
    """
    最小化的 Playwright Page 替身

    用途：在不启动真实浏览器的前提下，给被测方法提供 url 属性和
    异步 title() 方法。
    参数：
        url   - 当前页面 URL
        title - 当前页面标题（默认空串）
    """

    def __init__(self, url: str, title: str = ""):
        self.url = url
        self._title = title

    async def title(self) -> str:
        return self._title


# ─── _is_logged_in_by_url 登录成功判定 ───
# 关键：URL 含 /web/geek/ 但仍带 _security_check 时，说明 Boss 安全校验未完成，
# 此时若误判已登录会导致导航后又被弹回登录页。

def _is_logged_in(url: str) -> bool:
    """辅助函数：构造 spider + FakePage，运行 _is_logged_in_by_url() 返回结果

    参数：url - 模拟当前页面 URL
    返回：bool - 被测方法判定是否已登录成功
    """
    spider = RealPlaywrightBossSpider()
    spider.page = FakePage(url)
    return asyncio.run(spider._is_logged_in_by_url())


def test_logged_in_when_clean_geek_url():
    """干净的 /web/geek/ 结果页（无 _security_check）应判定为已登录"""
    url = "https://www.zhipin.com/web/geek/jobs?query=%E6%95%B0%E6%8D%AE&city=101020100"
    assert _is_logged_in(url) is True


def test_logged_in_even_with_security_check_param():
    """登录后 URL 常残留 _security_check（Boss 不会自清），仍应判定为已登录。

    实测：扫码后 URL 长时间停在 /web/geek/jobs?...&_security_check=2，
    Boss 不会自行去掉该参数。若要求其消失会导致登录轮询永远超时。
    """
    url = "https://www.zhipin.com/web/geek/jobs?query=%E6%95%B0%E6%8D%AE&city=101020100&_security_check=2_1779417468860"
    assert _is_logged_in(url) is True


def test_not_logged_in_on_login_page():
    """登录页（/web/user/）不应判定为已登录"""
    url = "https://www.zhipin.com/web/user/?from=passport-zp"
    assert _is_logged_in(url) is False


# ─── _classify_page_state 页面状态判定（settle 轮询的基础）───
# Boss 反爬重定向异步进行，页面会在数秒内经历 security.html / about:blank 等
# 中间态，故需按"状态"而非"瞬时 URL 标记"来判断。

def _classify(url: str) -> str:
    """辅助：构造 spider + FakePage，运行 _classify_page_state() 返回状态串"""
    spider = RealPlaywrightBossSpider()
    spider.page = FakePage(url)
    return asyncio.run(spider._classify_page_state())


def test_classify_login_page():
    assert _classify("https://www.zhipin.com/web/user/?from=passport-zp") == 'login'


def test_classify_security_challenge_is_transitional():
    assert _classify("https://www.zhipin.com/web/passport/zp/security.html?code=37") == 'security'


def test_classify_blank_is_transitional():
    assert _classify("about:blank") == 'blank'


def test_classify_clean_results_page():
    assert _classify("https://www.zhipin.com/web/geek/jobs?query=x&city=101020100") == 'results'


def test_classify_results_with_security_check_param_is_results():
    """/web/geek/jobs 即使残留 _security_check 仍是结果页（按路径判定）"""
    url = "https://www.zhipin.com/web/geek/jobs?query=x&city=101020100&_security_check=2_123"
    assert _classify(url) == 'results'


# ─── _wait_until_page_settled 轮询直到稳定 ───
# 把 security/blank/other 视为"继续等"，稳定到 login 或 results 才返回。

from unittest.mock import AsyncMock


def _spider_with_states(states):
    """构造一个 _classify_page_state 按 states 序列依次返回的 spider"""
    spider = RealPlaywrightBossSpider()
    spider._classify_page_state = AsyncMock(side_effect=list(states))
    return spider


def test_settle_returns_login_after_transition():
    """security→security→login：应等到 login"""
    spider = _spider_with_states(['security', 'security', 'login'])
    state = asyncio.run(spider._wait_until_page_settled(timeout=1.0, interval=0.01))
    assert state == 'login'


def test_settle_returns_results_after_transition():
    """blank→results：应等到 results"""
    spider = _spider_with_states(['blank', 'results'])
    state = asyncio.run(spider._wait_until_page_settled(timeout=1.0, interval=0.01))
    assert state == 'results'


def test_settle_times_out_when_never_stable():
    """一直 transitional：应超时返回 timeout"""
    spider = RealPlaywrightBossSpider()
    spider._classify_page_state = AsyncMock(return_value='security')
    state = asyncio.run(spider._wait_until_page_settled(timeout=0.2, interval=0.05))
    assert state == 'timeout'


# ─── _recover_session_if_needed 编排逻辑 ───
# 提取为空后调用：先 settle，再按稳定结果决定动作。
# 返回 True 表示调用方应重新准备+重新抓取（无论是登录后还是页面刚稳定到结果页）；
# 返回 False 仅当 settle 超时（无可恢复）。

SEARCH_URL = "https://www.zhipin.com/web/geek/jobs?query=x&city=101020100"


def _make_spider(settled, login_success: bool = True,
                 post_login_url: str = "https://www.zhipin.com/web/geek/recommend"):
    """
    构造带 mock 依赖的 spider，用于测试 _recover_session_if_needed

    参数：
        settled        - _wait_until_page_settled 的返回值。传 str 用 return_value；
                         传 list/tuple 用 side_effect（settle 会被调用多次：首次判断 +
                         登录后再判断）
        login_success  - _ensure_logged_in 的返回值（重新登录是否成功）
        post_login_url - self.page 所在 URL（仅用于日志）
    返回：
        spider 实例，相关方法已替换为可断言的 AsyncMock，self.page 指向 post_login_url
    """
    spider = RealPlaywrightBossSpider()
    if isinstance(settled, (list, tuple)):
        spider._wait_until_page_settled = AsyncMock(side_effect=list(settled))
    else:
        spider._wait_until_page_settled = AsyncMock(return_value=settled)
    spider._ensure_logged_in = AsyncMock(return_value=login_success)
    spider._navigate_to_search_page = AsyncMock()
    spider.page = FakePage(post_login_url)
    return spider


def test_recover_returns_false_on_timeout():
    """settle 超时：不登录、不导航，返回 False"""
    spider = _make_spider(settled='timeout')
    recovered = asyncio.run(spider._recover_session_if_needed(SEARCH_URL))
    assert recovered is False
    spider._ensure_logged_in.assert_not_called()
    spider._navigate_to_search_page.assert_not_called()


def test_recover_reextracts_on_results_without_login():
    """页面稳定到 *目标关键词的* 结果页（首次提取过早）：无需登录、无需导航，返回 True 让调用方重抓"""
    spider = _make_spider(
        settled='results',
        post_login_url="https://www.zhipin.com/web/geek/jobs?query=x&city=101020100",
    )
    recovered = asyncio.run(spider._recover_session_if_needed(SEARCH_URL))
    assert recovered is True
    spider._ensure_logged_in.assert_not_called()
    spider._navigate_to_search_page.assert_not_called()


def test_recover_renavigates_when_results_page_has_wrong_query():
    """settled=results 但 page.url 的 query 与 SEARCH_URL 不匹配（残留旧关键词）：
    若直接 return True 让调用方重抓，会抓到错关键词的结果。必须重新导航到目标 search_url。
    Codex review 指出：原代码该分支只判 'results' 状态、未校验 query 匹配。
    """
    spider = _make_spider(
        settled='results',
        post_login_url="https://www.zhipin.com/web/geek/jobs?query=old_keyword&city=101020100",
    )
    recovered = asyncio.run(spider._recover_session_if_needed(SEARCH_URL))
    assert recovered is True
    spider._ensure_logged_in.assert_not_called()
    spider._navigate_to_search_page.assert_called_once_with(SEARCH_URL), \
        "结果页但 query 错的情况，必须强制 goto 目标 search_url，否则前端拿到上次的搜索结果"


def test_recover_logs_in_and_renavigates_when_not_on_results():
    """稳定到登录页、登录成功但落点非结果页：需重新导航"""
    spider = _make_spider(settled='login', login_success=True,
                          post_login_url="https://www.zhipin.com/web/geek/recommend")
    recovered = asyncio.run(spider._recover_session_if_needed(SEARCH_URL))
    assert recovered is True
    spider._ensure_logged_in.assert_called_once()
    spider._navigate_to_search_page.assert_called_once_with(SEARCH_URL)


def test_recover_logs_in_skips_navigation_when_already_on_results():
    """稳定到登录页、登录成功且已在 *目标关键词的* 结果页：不重新导航（再导航会触发反爬弹回）"""
    spider = _make_spider(
        settled='login', login_success=True,
        # query=x 与 SEARCH_URL 的 query=x 匹配 → 已在目标结果页
        post_login_url="https://www.zhipin.com/web/geek/jobs?query=x&city=101020100&_security_check=2_123",
    )
    recovered = asyncio.run(spider._recover_session_if_needed(SEARCH_URL))
    assert recovered is True
    spider._ensure_logged_in.assert_called_once()
    spider._navigate_to_search_page.assert_not_called()


def test_recover_renavigates_when_query_mismatch_on_results():
    """稳定到登录页、登录成功但落在 /web/geek/jobs *错误关键词* 页：
    必须重新导航到目标 search_url，否则会拿到 Boss 推荐 feed / 上次搜索的旧关键词结果。

    实测场景：搜 'AI算法工程师'，Boss 反爬登录后把 fromUrl 落到 'ai产品经理' 的页面，
    URL path 是 /web/geek/jobs 但 query 参数完全不是用户想要的。
    """
    spider = _make_spider(
        settled='login', login_success=True,
        # 路径在 /web/geek/jobs 但 query=ai产品经理 ≠ SEARCH_URL 的 query=x
        post_login_url="https://www.zhipin.com/web/geek/jobs?query=ai%E4%BA%A7%E5%93%81%E7%BB%8F%E7%90%86&city=101020100",
    )
    recovered = asyncio.run(spider._recover_session_if_needed(SEARCH_URL))
    assert recovered is True
    spider._ensure_logged_in.assert_called_once()
    spider._navigate_to_search_page.assert_called_once_with(SEARCH_URL), \
        "落点 /web/geek/jobs 但 query 与目标不匹配时，必须重导航；否则用户拿到错关键词的结果"


def test_recover_skips_navigation_when_query_param_present_but_path_differs():
    """落在 /web/geek/recommend 一类非结果页时仍应导航（行为不变，回归保障）"""
    spider = _make_spider(
        settled='login', login_success=True,
        post_login_url="https://www.zhipin.com/web/geek/recommend",
    )
    recovered = asyncio.run(spider._recover_session_if_needed(SEARCH_URL))
    assert recovered is True
    spider._navigate_to_search_page.assert_called_once_with(SEARCH_URL)


# ─── _url_matches_search_target 边界 ───
# Codex review 指出：原实现 path 用 substring 判定（'/web/geek/jobs' in path），
# 'jobs-old' 这类后缀路径会被误判为目标搜索页；host 也没校验。补回归测试。

def _url_match(current_url: str, search_url: str) -> bool:
    """辅助：直接跑 static method"""
    return RealPlaywrightBossSpider._url_matches_search_target(current_url, search_url)


def test_url_match_accepts_exact_target():
    assert _url_match(
        "https://www.zhipin.com/web/geek/jobs?query=x&city=101020100",
        "https://www.zhipin.com/web/geek/jobs?query=x&city=101020100",
    ) is True


def test_url_match_ignores_security_check_residual():
    """Boss 登录后 URL 常残留 _security_check，不应影响匹配判定"""
    assert _url_match(
        "https://www.zhipin.com/web/geek/jobs?query=x&city=101020100&_security_check=2_123",
        "https://www.zhipin.com/web/geek/jobs?query=x&city=101020100",
    ) is True


def test_url_match_rejects_query_mismatch():
    assert _url_match(
        "https://www.zhipin.com/web/geek/jobs?query=other&city=101020100",
        "https://www.zhipin.com/web/geek/jobs?query=x&city=101020100",
    ) is False


def test_url_match_rejects_path_suffix_lookalike():
    """path 'jobs-old' 不能被 'jobs' substring 误判匹配（Codex review P2）"""
    assert _url_match(
        "https://www.zhipin.com/web/geek/jobs-old?query=x&city=101020100",
        "https://www.zhipin.com/web/geek/jobs?query=x&city=101020100",
    ) is False


def test_url_match_rejects_nested_path():
    """非根挂载的 path 也不能误命中"""
    assert _url_match(
        "https://www.zhipin.com/foo/web/geek/jobs?query=x&city=101020100",
        "https://www.zhipin.com/web/geek/jobs?query=x&city=101020100",
    ) is False


def test_url_match_rejects_different_host():
    """跨域 URL 不能匹配（即便 path/query 一致也可能是钓鱼/代理页）"""
    assert _url_match(
        "https://evil.example.com/web/geek/jobs?query=x&city=101020100",
        "https://www.zhipin.com/web/geek/jobs?query=x&city=101020100",
    ) is False


def test_url_match_handles_empty_input():
    assert _url_match("", "https://www.zhipin.com/web/geek/jobs?query=x") is False
    assert _url_match("https://www.zhipin.com/web/geek/jobs?query=x", "") is False


def test_recover_raises_when_relogin_fails():
    """稳定到登录页但登录超时/失败：抛出异常，不再重新导航"""
    spider = _make_spider(settled='login', login_success=False)
    try:
        asyncio.run(spider._recover_session_if_needed(SEARCH_URL))
        assert False, "应抛出异常"
    except RuntimeError:
        pass
    spider._navigate_to_search_page.assert_not_called()


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
