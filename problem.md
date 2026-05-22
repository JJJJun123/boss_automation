# 待解问题：Boss 直聘登录页被反爬关进"重定向死循环"，无法扫码登录

> 记录时间：2026-05-22。给外部同学求助用，尽量自包含。

---

## ✅ 已解决（2026-05-22 晚）

**根因确认**：Boss 检测 Playwright 的 `Runtime.enable` CDP 痕迹，导致 `security.html?code=37` JS 挑战不通过、无限重定向。`playwright_stealth` 只改 navigator 表面属性，挡不住这一层。

**解法**：把 `playwright` 换成 **`patchright`**（反检测分支，驱动层不再调用 `Runtime.enable`）。

```bash
pip install patchright && patchright install chrome
```

```python
from patchright.async_api import async_playwright   # drop-in，API 不变
# 启动用官方干净配置，删掉所有 stealth / 自定义 args / user_agent：
launch_persistent_context(channel="chrome", headless=False, no_viewport=True)
```

**实测**：登录阶段跳转从 17+ 次/6 秒降到 3 次，登录页稳定可扫，5 个岗位全部抓到真实 JD + 正确公司名，全流程 34 秒跑通。

> 下面是当时求助时的原始问题描述，保留备查。

---

## 一句话

用 Playwright 爬 Boss 直聘，需要扫码登录。但**登录页整页反复重载（约 2 次/秒），二维码一闪就被弹走，人根本来不及扫**。怀疑是 Boss 反爬把自动化浏览器关进了 `security.html` 安全校验的无限重定向。

## 项目背景（极简）

- Boss 直聘智能求职助手：Python + Playwright 爬岗位 → 多 AI 模型评分。
- 爬虫核心：`crawler/real_playwright_spider.py`（`launch_persistent_context` 持久化登录态 + `playwright_stealth` 反检测 + 真实 Chrome binary）。
- 入口/复现脚本：`tests/integration_test_crawl.py`（搜索"数据分析"，max_jobs=5）。

## 复现步骤

```bash
# conda 环境 boss_dev（python 3.12, playwright 1.60.0, playwright-stealth 2.0.3）
/opt/anaconda3/envs/boss_dev/bin/python tests/integration_test_crawl.py
```

1. 浏览器（有头）打开，导航到搜索页 `https://www.zhipin.com/web/geek/jobs?query=数据分析&city=101020100`
2. 立即被 302 到安全校验页 `https://www.zhipin.com/web/passport/zp/security.html?...&code=37`（标题"请稍候"）
3. 程序检测到未登录 → 跳登录页 `https://www.zhipin.com/web/user/?ka=header-login` 等待扫码
4. **登录页开始整页反复重载，无法扫码** ← 核心问题

## 关键证据（决定性）

给登录等待阶段挂了 `page.on('framenavigated')` 监听，记录每次主框架导航。实测 **6 秒内跳转 17+ 次**，在三个地址间疯狂循环：

```
[诊断] 🔄 第 1 次 → /web/geek/jobs?query=...&_security_check=1
[诊断] 🔄 第 2 次 → /web/user/?from=passport-zp&fromUrl=.../jobs?...&_security_check=1
[诊断] 🔄 第 3 次 → /web/geek/jobs?...&_security_check=1
[诊断] 🔄 第 5 次 → /web/user/?from=passport-zp...
[诊断] 🔄 第 8 次 → /web/passport/zp/security.html?...&code=37&seed=...
[诊断] 🔄 第 9 次 → /web/geek/jobs?...&_security_check=2     # 注意计数 1→2 自增
[诊断] 🔄 第 11 次 → /web/user/?from=passport-zp...
...（持续到被手动中止）
```

循环链路：`/web/geek/jobs?_security_check ⇄ /web/user/(登录) ⇄ security.html?code=37`，URL 里的 `_security_check=N` 计数会自增。

**重要：这些跳转期间我们的代码并没有发起任何导航**（`_ensure_logged_in` 只在开头 `goto` 登录页一次，之后纯 `sleep`+读 URL 轮询）。**17 次跳转全是 Boss 客户端 JS 自己发起的**，所以排除"我们代码反复刷新"的可能。

## 已确认 / 已排除

- ✅ 浏览器能正常启动（macOS 26 上 playwright 1.40 的旧 chromium 会段错误崩溃，已升到 1.60 修复，与本问题无关）。
- ✅ **不是 cookie 损坏**：把持久化 profile 目录（`~/Library/Application Support/boss_automation/browser_profile/boss_zhipin`，含旧 cookie）整个删掉重置，全新 profile 仍然循环。
- ✅ **不是固定的**：早些时候热度低时，**偶尔能成功登录并抓到 5 个岗位**（含详情页 JD）。但大多数时候、尤其密集运行后，就是死循环。→ 像是 Boss 按指纹/行为/频率动态决定要不要发 `code=37` 挑战。
- ✅ 登录检测逻辑本身没问题（`/web/geek/` 出现即判已登录），登录后能抓取（已验证）。问题纯粹卡在"登录页因反爬循环刷新、扫不了码"。

## 当前根因假设

Boss 反爬要一个 JS 算出来的 **`__zp_stoken__` cookie**，`security.html?code=37` 就是跑这段混淆 JS 来签发 token 的页面。我们的浏览器被判定为自动化、过不了 JS 挑战 → 拿不到有效 token → 在"要 token"和"没 token"之间无限重定向。

最可能的检测点：**`Runtime.enable` CDP 命令泄漏**——Playwright 驱动浏览器时会调用它，反爬可探测到异常执行上下文，从而识别自动化。`playwright_stealth` 只改 `navigator` 表面属性，**不修这个 CDP 层泄漏**。

## 待验证的解法（尚未实施）

把 `playwright` 换成 **`patchright`**（Playwright 的反检测分支，drop-in 替换，源码层面避免 `Runtime.enable`，改用隔离执行上下文）：

```bash
pip install patchright && patchright install chrome
```

```python
# from playwright.async_api import async_playwright
from patchright.async_api import async_playwright   # API 不变
```

官方还要求**配置尽量干净**：用 `channel="chrome"` + `no_viewport=True`，**删掉现有的 playwright_stealth 和所有自定义 args / user_agent / sec_ch_ua 覆盖**（这些"化妆"反而制造破绽）。

不确定性：这命中"最可能的元凶"，但 Boss 可能还有 TLS 指纹（JA3）、行为检测、GEETEST 滑块等其它防线，不保证一定通关。

## 想请教外部同学的问题

1. Boss 的 `security.html?code=37` + `_security_check` 自增重定向，是否就是 `__zp_stoken__` 签发失败导致的？有没有更准的判断方法？
2. patchright（或 rebrowser-patches / undetected-chromedriver）能否稳定通过 Boss 当前的反爬？有没有人近期实测过？
3. 除了换驱动，是否需要配合：住宅代理 IP、固定真实指纹、放慢操作节奏、或直接逆向 `__zp_stoken__` 的 JS？
4. 有没有更靠谱的路子（如接管用户自己已登录的真实 Chrome、或走官方/第三方数据源）？

## 环境

- 机器：Apple M4 Pro / arm64 / macOS 26.3.1
- Python 3.12（conda env `boss_dev`），playwright 1.60.0，playwright-stealth 2.0.3
- 关键代码：`crawler/real_playwright_spider.py`（`start()` 启动浏览器；`_ensure_logged_in()` 登录等待；`_recover_session_if_needed()` 会话恢复）
