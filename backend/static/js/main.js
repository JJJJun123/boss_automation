// 等待DOM加载完成
document.addEventListener("DOMContentLoaded", function () {
  const DEBUG_CONSOLE = false;
  const debugLog = (...args) => {
    if (DEBUG_CONSOLE) debugLog(...args);
  };

  // ========== 工具函数 ==========
  // 清理Markdown格式
  function cleanMarkdown(text) {
    if (!text) return text;
    // 使用简单的字符串替换避免复杂的正则表达式
    return text
      .replace(/\\*\\*([^*]+?)\\*\\*/g, "$1") // 移除粗体**text**
      .replace(/\\*([^*]+?)\\*/g, "$1") // 移除斜体*text*
      .replace(/__([^_]+?)__/g, "$1") // 移除粗体__text__
      .replace(/_([^_]+?)_/g, "$1") // 移除斜体_text_
      .replace(/`([^`]+?)`/g, "$1") // 移除代码`text`
      .replace(/#{1,6}\\s+/g, "") // 移除标题# text
      .trim();
  }

  // ========== 初始化核心变量 ==========
  debugLog("🔌 初始化Socket.IO连接...");
  const socket = io();

  let isSearching = false;
  let allJobs = [];
  let qualifiedJobs = [];
  let currentView = "qualified";
  let currentTaskId = null;

  // ========== 初始化所有DOM元素 ==========
  debugLog("📋 初始化DOM元素...");

  // WebSocket状态元素
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");

  // 简历上传相关元素
  const resumeFileInput = document.getElementById("resume-file-input");
  const uploadArea = document.getElementById("upload-area");
  const uploadProgress = document.getElementById("upload-progress");
  const uploadBar = document.getElementById("upload-bar");
  const uploadPercentage = document.getElementById("upload-percentage");
  // 移除分析相关元素

  // 岗位搜索相关元素
  const startBtn = document.getElementById("start-search-btn");
  const progressBar = document.getElementById("progress-bar");
  const progressFill = document.getElementById("progress-fill");
  const progressMessage = document.getElementById("progress-message");
  const progressLogs = document.getElementById("progress-logs");
  const statsCard = document.getElementById("stats-card");
  const jobsList = document.getElementById("jobs-list");
  const emptyState = document.getElementById("empty-state");
  const qrPane = document.getElementById("qr-pane");
  const qrImage = document.getElementById("qr-image");
  const qrState = document.getElementById("qr-state");
  const apiProvider = document.getElementById("api-provider");
  const apiKeyInput = document.getElementById("api-key-input");
  const apiKeyStatus = document.getElementById("api-key-status");
  const saveApiKeyBtn = document.getElementById("btn-save-api-key");
  const deleteApiKeyBtn = document.getElementById("btn-delete-api-key");
  const trialStatus = document.getElementById("trial-status");
  const byokModal = document.getElementById("byok-required-modal");

  // ========== 单页面应用，移除页面切换功能 ==========

  // ========== WebSocket连接处理 ==========
  socket.on("connect", () => {
    debugLog("✅ WebSocket已连接, ID:", socket.id);
    if (statusDot) statusDot.className = "status-pill__dot live";
    if (statusText) statusText.textContent = "Live";
  });

  socket.on("disconnect", () => {
    debugLog("❌ WebSocket断开连接");
    if (statusDot) statusDot.className = "status-pill__dot";
    if (statusText) statusText.textContent = "断开";
  });

  socket.on("connect_error", (error) => {
    console.error("❌ WebSocket连接错误:", error.message);
  });

  socket.on("progress_update", (data) => {
    if (currentTaskId && data.task_id !== currentTaskId) return;
    updateProgress(data);
  });

  socket.on("search_complete", (data) => {
    if (currentTaskId && data.task_id !== currentTaskId) return;
    debugLog("🎉 搜索完成");
    isSearching = false;
    if (startBtn) {
      startBtn.textContent = "Begin search";
      startBtn.disabled = false;
      startBtn.classList.remove("searching");
    }
    if ((data.message || "").includes("API Key")) {
      loadApiKeyStatus();
      byokModal?.classList.add("open");
    }
    currentTaskId = null;
  });

  socket.on("qr_update", (data) => {
    // QR 图本质上是临时登录凭据，只接收当前页面刚启动任务的事件。
    if (!currentTaskId || data.task_id !== currentTaskId) return;
    if (!qrPane || !qrImage || !qrState) return;

    const state = data.state;
    qrState.dataset.state = state || "";
    if (state === "qr_ready") {
      qrPane.classList.add("open");
      if (data.image_b64) {
        const image = document.createElement("img");
        image.alt = "Boss 直聘登录二维码";
        image.src = "data:image/png;base64," + data.image_b64;
        qrImage.replaceChildren(image);
      }
      qrState.textContent =
        "QR READY · 打开 Boss 直聘 App → 首页「+」→ 扫一扫（微信扫码无效）";
    } else if (state === "scanned") {
      qrPane.classList.add("open");
      qrState.textContent = "SCANNED · 已扫描，请在手机上确认";
    } else if (state === "logged_in") {
      qrState.textContent = "LOGGED IN · 登录成功，继续搜索";
      qrPane.classList.remove("open");
      progressBar?.classList.add("active");
    } else if (state === "login_timeout") {
      qrPane.classList.add("open");
      qrImage.textContent = "二维码已失效";
      qrState.textContent = "LOGIN TIMEOUT · 扫码超时，请重新发起搜索";
    } else if (state === "qr_capture_failed") {
      qrPane.classList.add("open");
      qrImage.textContent = "暂时无法获取二维码";
      qrState.textContent = "CAPTURE FAILED · 请稍后重新发起搜索";
    }
  });

  // ========== 文件上传功能 ==========
  // 注意：文件上传事件监听器已在后面的代码中设置，避免重复绑定

  if (uploadArea) {
    // 新版 UI 整个卡片即点击区（旧版的"选择文件"按钮已移除）
    uploadArea.addEventListener("click", function () {
      resumeFileInput?.click();
    });

    // 拖拽上传
    uploadArea.addEventListener("dragover", function (e) {
      e.preventDefault();
      uploadArea.classList.add("dragover");
    });

    uploadArea.addEventListener("dragleave", function (e) {
      e.preventDefault();
      uploadArea.classList.remove("dragover");
    });

    uploadArea.addEventListener("drop", function (e) {
      e.preventDefault();
      uploadArea.classList.remove("dragover");

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        uploadResume(files[0]);
      }
    });
  }

  // 上传简历函数在后面定义

  // 更新上传进度
  function updateUploadProgress(percentage) {
    if (uploadBar) uploadBar.style.width = percentage + "%";
    if (uploadPercentage)
      uploadPercentage.textContent = Math.round(percentage) + "%";
  }

  // 显示AI分析结果 - 适配新的LangGPT格式
  // 移除复杂的AI分析显示功能，改为简单的简历状态更新

  // 重置上传区域
  function resetUploadArea() {
    if (uploadProgress) uploadProgress.style.display = "none";
    if (uploadArea) uploadArea.style.display = "block";
    // 移除分析结果相关元素的处理
  }

  // 更新简历状态（editorial design）
  function updateResumeStatus(resumeData) {
    const slot = document.getElementById("upload-area");
    const title = document.getElementById("resume-title");
    const hint = document.getElementById("resume-hint");
    if (!slot) return;
    if (resumeData) {
      slot.classList.add("uploaded");
      if (title)
        title.textContent =
          resumeData.name || resumeData.filename || "简历已加载";
      if (hint) hint.textContent = `${resumeData.length || ""} 字符 · TTL 24h`;
    }
  }

  // 重置简历状态
  function resetResumeStatus() {
    const slot = document.getElementById("upload-area");
    const title = document.getElementById("resume-title");
    const hint = document.getElementById("resume-hint");
    if (slot) slot.classList.remove("uploaded");
    if (title) title.textContent = "拖拽或点击上传";
    if (hint) hint.textContent = "PDF / DOCX · ≤ 5MB";
  }

  // ========== 全局函数导出 ==========
  window.showAIDetails = function (type, output) {
    debugLog("👁️ 显示AI详情:", type);
    const modal = document.getElementById("ai-details-modal");
    const title = document.getElementById("ai-details-title");
    const content = document.getElementById("ai-details-content");

    if (modal && title && content) {
      switch (type) {
        case "resume":
          title.textContent = "简历AI分析完整输出";
          content.textContent = window.resumeAIOutput || "暂无AI输出记录";
          break;
        case "job":
          title.textContent = "岗位匹配AI分析输出";
          content.textContent = output || "暂无AI输出记录";
          break;
        default:
          title.textContent = "AI分析输出";
          content.textContent = output || "暂无AI输出记录";
      }
      modal.classList.add("open");
    }
  };

  window.hideAIDetails = function () {
    const modal = document.getElementById("ai-details-modal");
    if (modal) modal.classList.remove("open");
  };

  // 清理和格式化文本
  window.cleanJobText = function (text) {
    if (!text) return "";

    // 首先处理所有类型的空白字符
    // 包括：普通空格、全角空格(　)、不间断空格(&nbsp;)、制表符等
    let cleaned = text
      .replace(/[\u3000\u00A0]/g, " ") // 全角空格和不间断空格转为普通空格
      .replace(/&nbsp;/g, " ") // HTML实体空格
      .replace(/\t/g, " ") // 制表符转为空格
      .trim();

    // 移除每行开头的所有空白字符（包括全角空格）
    cleaned = cleaned.replace(/^[\\s\u3000\u00A0\t]+/gm, "");

    // 移除重复的标题（如"工作职责:"后面又有"工作职责:"）
    cleaned = cleaned.replace(
      /^(工作职责|任职资格|岗位职责|任职要求)[:：]\\s*(工作职责|任职资格|岗位职责|任职要求)[:：]/g,
      "$1：",
    );

    // 移除开头的冒号和空白字符
    cleaned = cleaned.replace(/^[:：]\\s*/, "");

    // 使用cleanMarkdown函数清理Markdown格式
    cleaned = cleanMarkdown(cleaned);

    // 彻底清理所有多余空格
    // 1. 将多个连续空格替换为单个空格
    cleaned = cleaned.replace(/[ ]+/g, " ");

    // 2. 移除换行前后的空格
    cleaned = cleaned.replace(/\\s*\\n\\s*/g, "\\n");

    // 3. 确保数字列表格式整齐
    cleaned = cleaned.replace(/\\n?(\\d+[、.)）])/g, "\\n$1");

    // 4. 移除行首行尾的空格（对每行单独处理）
    cleaned = cleaned
      .split("\\n")
      .map((line) => line.trim())
      .join("\\n");

    // 5. 合并多个连续换行
    cleaned = cleaned.replace(/\\n{3,}/g, "\\n\\n");

    // 6. 移除开头和结尾的换行
    cleaned = cleaned.replace(/^\\n+|\\n+$/g, "");

    // 7. 特殊处理：如果整个文本以大量空格开头（常见于爬取数据）
    cleaned = cleaned.replace(/^\\s{10,}/g, "");

    return cleaned;
  };

  // 切换岗位详情显示（展开/收起）- 原版本
  window.toggleJobDetail = function (elementId, fullText, buttonElement) {
    const element = document.getElementById(elementId);
    if (!element || !buttonElement) return;

    const isExpanded = buttonElement.textContent === "收起";

    // 清理文本格式
    const cleanedText = window.cleanJobText(fullText);

    if (isExpanded) {
      // 收起：显示截断文本
      const truncatedText =
        cleanedText.length > 800
          ? cleanedText.substring(0, 800) + "..."
          : cleanedText;
      element.innerHTML = truncatedText;
      buttonElement.textContent = "展开全文";
    } else {
      // 展开：显示完整文本
      element.innerHTML = cleanedText;
      buttonElement.textContent = "收起";
    }
  };

  // 安全版本的岗位详情切换（使用data属性避免特殊字符问题）
  window.toggleJobDetailSafe = function (buttonElement) {
    if (!buttonElement) return;

    const elementId = buttonElement.getAttribute("data-detail-id");
    const encodedFullText = buttonElement.getAttribute("data-full-text");
    const element = document.getElementById(elementId);

    if (!element || !encodedFullText) {
      console.error("❌ 展开功能参数缺失:", {
        elementId,
        encodedFullText: !!encodedFullText,
      });
      return;
    }

    const isExpanded = buttonElement.textContent.trim() === "收起";

    try {
      // 解码文本内容
      const fullText = decodeURIComponent(encodedFullText);
      const cleanedText = window.cleanJobText(fullText);

      if (isExpanded) {
        // 收起：显示截断文本
        const truncatedText =
          cleanedText.length > 800
            ? cleanedText.substring(0, 800) + "..."
            : cleanedText;
        element.innerHTML = truncatedText;
        buttonElement.textContent = "展开全文";
        debugLog("✅ 文本已收起");
      } else {
        // 展开：显示完整文本
        element.innerHTML = cleanedText;
        buttonElement.textContent = "收起";
        debugLog("✅ 文本已展开，完整长度:", cleanedText.length);
      }
    } catch (error) {
      console.error("❌ 展开文本失败:", error);
      buttonElement.textContent = "展开失败";
    }
  };

  window.deleteResume = async function () {
    if (!confirm("确定要删除当前简历吗？此操作无法撤销。")) {
      return;
    }

    try {
      const response = await axios.post("/api/delete_resume");
      if (response.data.success) {
        resetUploadArea();
        resetResumeStatus();
        debugLog("🗑️ 简历已删除");
      } else {
        alert("删除失败: " + response.data.error);
      }
    } catch (error) {
      console.error("❌ 删除失败:", error);
      alert("删除失败: " + (error.response?.data?.error || error.message));
    }
  };

  window.showAllJobs = function () {
    debugLog("📋 显示所有岗位");
    currentView = "all";
    const q = document.getElementById("btn-view-qualified");
    const a = document.getElementById("btn-view-all");
    if (q) q.classList.remove("active");
    if (a) a.classList.add("active");
    if (allJobs && allJobs.length > 0) {
      renderJobsList(allJobs);
    } else {
      fetchAllJobs();
    }
  };

  window.showQualifiedJobs = function () {
    debugLog("⭐ 显示合格岗位");
    currentView = "qualified";
    const q = document.getElementById("btn-view-qualified");
    const a = document.getElementById("btn-view-all");
    if (q) q.classList.add("active");
    if (a) a.classList.remove("active");

    if (qualifiedJobs && qualifiedJobs.length > 0) {
      renderJobsList(qualifiedJobs);
    } else {
      // 没有合格岗位时显示提示
      const jobsList = document.getElementById("jobs-list");
      if (jobsList) {
        jobsList.innerHTML = `
          <section class="empty-state">
              <div class="empty-state__icon">⌗</div>
              <h3 class="empty-state__title">暂无合格岗位</h3>
              <p class="empty-state__hint">点上方"全部岗位"查看逐个评分，或调整关键词重搜。</p>
          </section>
        `;
      }
    }
  };

  // ========== 加载配置 ==========
  async function loadConfig() {
    try {
      const response = await axios.get("/api/config");
      const config = response.data;

      // 设置其他默认值
      if (config.search) {
        if (config.search.keyword) {
          document.getElementById("keyword").value = config.search.keyword;
        }
        if (config.search.max_jobs) {
          document.getElementById("max_jobs").value = config.search.max_jobs;
        }
      }
    } catch (error) {
      console.error("❌ 加载配置失败:", error);
    }
  }

  function updateTrialStatus(status) {
    if (!trialStatus || status.trial_remaining === undefined) return;
    const remaining = Number(status.trial_remaining) || 0;
    const limit = Number(status.trial_limit) || 3;
    trialStatus.textContent = `免费试用剩余 ${remaining} / ${limit} 次`;
    trialStatus.classList.toggle("exhausted", remaining <= 0);
  }

  async function loadApiKeyStatus() {
    try {
      const response = await fetch("/api/settings/api-key", {
        credentials: "include",
      });
      const body = await response.json().catch(() => ({}));
      if (response.status === 401) return;
      updateTrialStatus(body);

      if (response.ok) {
        if (apiProvider) apiProvider.value = body.provider;
        if (apiKeyStatus) {
          apiKeyStatus.textContent = `已配置 ${body.masked} · ${body.provider}`;
          apiKeyStatus.className = "key-card__status configured";
        }
        if (deleteApiKeyBtn) deleteApiKeyBtn.hidden = false;
        if (trialStatus) {
          trialStatus.textContent = `已使用自有 ${body.provider} Key · 不消耗试用次数`;
          trialStatus.classList.remove("exhausted");
        }
      } else {
        if (apiKeyStatus) {
          apiKeyStatus.textContent =
            body.code === "key_reconfigure_required"
              ? "原 Key 已无法解密，请重新配置"
              : "尚未配置 · 可先免费试用";
          apiKeyStatus.className =
            body.code === "key_reconfigure_required"
              ? "key-card__status error"
              : "key-card__status";
        }
        if (deleteApiKeyBtn) deleteApiKeyBtn.hidden = true;
      }
    } catch (error) {
      if (apiKeyStatus) {
        apiKeyStatus.textContent = "暂时无法读取 Key 状态";
        apiKeyStatus.className = "key-card__status error";
      }
    }
  }

  function showByokRequired() {
    byokModal?.classList.add("open");
  }

  saveApiKeyBtn?.addEventListener("click", async () => {
    const apiKey = apiKeyInput?.value.trim() || "";
    if (!apiKey) {
      if (apiKeyStatus) {
        apiKeyStatus.textContent = "请先输入 API Key";
        apiKeyStatus.className = "key-card__status error";
      }
      return;
    }

    saveApiKeyBtn.disabled = true;
    saveApiKeyBtn.textContent = "验证中…";
    try {
      const response = await fetch("/api/settings/api-key", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: apiProvider?.value || "deepseek",
          api_key: apiKey,
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error || "Key 验证失败");
      if (apiKeyInput) apiKeyInput.value = "";
      byokModal?.classList.remove("open");
      await loadApiKeyStatus();
    } catch (error) {
      if (apiKeyStatus) {
        apiKeyStatus.textContent = error.message;
        apiKeyStatus.className = "key-card__status error";
      }
    } finally {
      saveApiKeyBtn.disabled = false;
      saveApiKeyBtn.textContent = "验证并保存";
    }
  });

  deleteApiKeyBtn?.addEventListener("click", async () => {
    if (!confirm("删除已保存的 API Key？之后将继续消耗免费试用次数。")) return;
    try {
      const response = await fetch("/api/settings/api-key", {
        method: "DELETE",
        credentials: "include",
      });
      if (!response.ok) throw new Error("删除失败");
      await loadApiKeyStatus();
    } catch (error) {
      if (apiKeyStatus) {
        apiKeyStatus.textContent = error.message;
        apiKeyStatus.className = "key-card__status error";
      }
    }
  });

  document.getElementById("byok-modal-close")?.addEventListener("click", () => {
    byokModal?.classList.remove("open");
  });
  document.getElementById("byok-go-settings")?.addEventListener("click", () => {
    byokModal?.classList.remove("open");
    apiKeyInput?.scrollIntoView({ behavior: "smooth", block: "center" });
    apiKeyInput?.focus();
  });
  byokModal?.addEventListener("click", (event) => {
    if (event.target === byokModal) byokModal.classList.remove("open");
  });

  window.addEventListener("auth-ready", () => {
    loadConfig();
    loadApiKeyStatus();
  });

  // 页面加载时获取配置
  loadConfig();
  loadApiKeyStatus();

  // ========== 岗位搜索功能 ==========
  if (startBtn) {
    startBtn.addEventListener("click", async () => {
      if (isSearching) return;

      const keyword = document.getElementById("keyword").value.trim();
      const city = document.getElementById("city").value;

      if (!keyword) {
        alert("请输入搜索关键词");
        return;
      }
      if (!city) {
        alert("请选择目标城市");
        return;
      }

      isSearching = true;
      startBtn.textContent = "搜索中…";
      startBtn.disabled = true;
      startBtn.classList.add("searching");

      debugLog("🔍 开始搜索:", { keyword, city });

      try {
        const response = await axios.post("/api/jobs/search", {
          keyword,
          city,
          max_jobs: parseInt(document.getElementById("max_jobs").value) || 5,
        });

        debugLog("✅ 搜索任务已启动:", response.data);
        currentTaskId = response.data.task_id;
        qrPane?.classList.remove("open");
      } catch (error) {
        console.error("❌ 启动搜索失败:", error);
        if (
          error.response?.status === 402 &&
          error.response?.data?.code === "byok_required"
        ) {
          showByokRequired();
          loadApiKeyStatus();
        } else {
          alert(
            "启动搜索失败: " + (error.response?.data?.error || error.message),
          );
        }
        isSearching = false;
        startBtn.textContent = "Begin search";
        startBtn.disabled = false;
        startBtn.classList.remove("searching");
      }
    });
  }

  // 更新进度
  function updateProgress(data) {
    debugLog("🔄 更新进度:", data);

    // 更新主要状态消息
    if (progressMessage) {
      progressMessage.textContent = data.message;
    }

    // 更新进度条和百分比
    if (data.progress !== undefined) {
      const progressBar = document.getElementById("progress-bar");
      const progressFill = document.getElementById("progress-fill");
      const progressPercentage = document.getElementById("progress-percentage");
      const stageIndicators = document.getElementById("stage-indicators");

      if (progressBar && progressFill) {
        progressBar.classList.add("active");
        progressFill.style.width = data.progress + "%";

        if (progressPercentage) {
          progressPercentage.style.display = "block";
          progressPercentage.textContent = Math.round(data.progress) + "%";
        }

        // 显示阶段指示器
        if (stageIndicators) {
          stageIndicators.style.display = "grid";
          updateStageIndicators(data.progress, data.message);
        }

        // 当进度达到100%时，重置搜索按钮状态（双重保险）
        if (data.progress >= 100) {
          isSearching = false;
          const startBtn = document.getElementById("start-search-btn");
          if (startBtn) {
            startBtn.textContent = "Begin search";
            startBtn.disabled = false;
          }
        }
      }
    }

    // 添加到详细日志
    const progressLogs = document.getElementById("progress-logs");
    if (progressLogs) {
      const logItem = document.createElement("div");
      logItem.className =
        "flex items-start py-1 px-2 hover:bg-gray-50 rounded text-xs";

      // 检查消息是否已包含emoji，如果有就不添加额外图标
      let icon = "•";
      const hasEmoji =
        /[\u{1F600}-\u{1F64F}]|[\u{1F300}-\u{1F5FF}]|[\u{1F680}-\u{1F6FF}]|[\u{1F1E0}-\u{1F1FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]/u.test(
          data.message,
        );

      if (!hasEmoji) {
        if (data.message.includes("开始") || data.message.includes("初始化"))
          icon = "🚀";
        else if (data.message.includes("搜索") || data.message.includes("设置"))
          icon = "🔍";
        else if (data.message.includes("AI") || data.message.includes("智能"))
          icon = "🧠";
        else if (data.message.includes("分析") || data.message.includes("市场"))
          icon = "📊";
        else if (data.message.includes("完成") || data.message.includes("成功"))
          icon = "✅";
        else if (
          data.message.includes("警告") ||
          data.message.includes("未检测")
        )
          icon = "⚠️";
        else if (data.message.includes("失败") || data.message.includes("错误"))
          icon = "❌";
      } else {
        icon = ""; // 如果消息已有emoji就不显示额外图标
      }

      logItem.innerHTML = `
                <span class="mr-2 flex-shrink-0">${icon}</span>
                <div class="flex-1">
                    <span class="text-gray-700">${data.message}</span>
                    <span class="text-gray-400 ml-2">${data.timestamp}</span>
                </div>
            `;
      progressLogs.appendChild(logItem);
      progressLogs.scrollTop = progressLogs.scrollHeight;
    }

    // 处理结果数据
    if (data.data) {
      debugLog("📦 收到数据:", Object.keys(data.data));

      // 检查是否需要简历
      if (data.data.requires_resume) {
        displayResumeRequiredMessage(data.data);
      } else {
        displayResults(data.data.results, data.data.stats);
      }

      // 总是存储所有岗位数据
      if (data.data.all_jobs) {
        allJobs = data.data.all_jobs;
      }
    }
  }

  // 更新阶段指示器
  function updateStageIndicators(progress, message) {
    const stageItems = document.querySelectorAll(".stage-item");

    // 重置所有阶段
    stageItems.forEach((item) => {
      const circle = item.querySelector("div");
      const text = item.querySelector("div:last-child");
      circle.className =
        "w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-xs font-bold mx-auto mb-1";
      text.className = "text-xs text-center text-gray-500";
    });

    // 根据进度和消息内容更准确地判断阶段
    let currentStage = "";

    if (progress >= 5 && progress <= 50) {
      currentStage = "search";
    } else if (
      progress > 50 &&
      (message.includes("AI") ||
        message.includes("智能") ||
        message.includes("分析") ||
        progress <= 80)
    ) {
      currentStage = "extract"; // 实际上是AI分析阶段
    } else if (progress > 80 && progress < 100) {
      currentStage = "analysis"; // 实际上是保存和整理阶段
    } else if (progress >= 100) {
      currentStage = "complete";
    }

    // 阶段1：搜索岗位 (5-50%)
    const searchStage = document.querySelector('[data-stage="search"]');
    if (searchStage) {
      const circle = searchStage.querySelector("div");
      const text = searchStage.querySelector("div:last-child");
      if (currentStage === "search") {
        circle.className =
          "w-8 h-8 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1 animate-pulse";
        circle.innerHTML = "1";
        text.className = "text-xs text-center text-blue-600 font-medium";
      } else if (progress > 50) {
        circle.className =
          "w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1";
        circle.innerHTML = "✓";
        text.className = "text-xs text-center text-green-600";
      }
    }

    // 阶段2：AI分析 (50-80%) - 重新标记为AI分析
    const extractStage = document.querySelector('[data-stage="extract"]');
    if (extractStage) {
      const circle = extractStage.querySelector("div");
      const text = extractStage.querySelector("div:last-child");
      // 更新标签文本
      text.textContent = "AI分析";

      if (currentStage === "extract") {
        circle.className =
          "w-8 h-8 rounded-full bg-purple-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1 animate-pulse";
        circle.innerHTML = "2";
        text.className = "text-xs text-center text-purple-600 font-medium";
      } else if (progress > 80) {
        circle.className =
          "w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1";
        circle.innerHTML = "✓";
        text.className = "text-xs text-center text-green-600";
      }
    }

    // 阶段3：整理结果 (80-95%)
    const analysisStage = document.querySelector('[data-stage="analysis"]');
    if (analysisStage) {
      const circle = analysisStage.querySelector("div");
      const text = analysisStage.querySelector("div:last-child");
      // 更新标签文本
      text.textContent = "整理结果";

      if (currentStage === "analysis") {
        circle.className =
          "w-8 h-8 rounded-full bg-orange-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1 animate-pulse";
        circle.innerHTML = "3";
        text.className = "text-xs text-center text-orange-600 font-medium";
      } else if (progress >= 100) {
        circle.className =
          "w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1";
        circle.innerHTML = "✓";
        text.className = "text-xs text-center text-green-600";
      }
    }

    if (progress >= 100) {
      // 阶段4：完成
      const completeStage = document.querySelector('[data-stage="complete"]');
      if (completeStage) {
        const circle = completeStage.querySelector("div");
        const text = completeStage.querySelector("div:last-child");
        circle.className =
          "w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center text-xs font-bold mx-auto mb-1";
        circle.innerHTML = "🎉";
        text.className = "text-xs text-center text-green-600 font-medium";
      }
    }
  }

  // 切换日志显示
  window.toggleProgressLogs = function () {
    const logs = document.getElementById("progress-logs");
    const toggleBtn = document.getElementById("toggle-logs");

    if (logs && toggleBtn) {
      if (logs.style.display === "none" || logs.style.display === "") {
        logs.style.display = "block";
        toggleBtn.textContent = "收起";
      } else {
        logs.style.display = "none";
        toggleBtn.textContent = "展开";
      }
    }
  };

  // 显示需要简历的提示消息
  function displayResumeRequiredMessage(data) {
    debugLog("📋 显示需要简历的提示");

    // 显示统计信息（搜索到的岗位数量）
    if (data.stats) {
      const totalEl = document.getElementById("total-jobs");
      const qualifiedEl = document.getElementById("qualified-jobs");
      if (totalEl) totalEl.textContent = data.stats.total;
      if (qualifiedEl) qualifiedEl.textContent = "需要简历";
      if (statsCard) statsCard.style.display = "block";
    }

    // 显示提示消息
    const jobsList = document.getElementById("jobs-list");
    if (jobsList) {
      jobsList.innerHTML = `
        <section class="empty-state">
            <div class="empty-state__icon">¶</div>
            <h3 class="empty-state__title">需要先上传简历</h3>
            <p class="empty-state__hint">
                已抓到 <strong>${data.stats?.total || 0}</strong> 个岗位。
                上传简历后才能跑 AI 评分。
            </p>
            <div style="margin-top: 18px;">
                <button class="btn-secondary" onclick="document.getElementById('resume-file-input').click()" type="button">
                    上传简历 ↑
                </button>
            </div>
        </section>
      `;
    }

    if (emptyState) emptyState.style.display = "none";
  }

  // 显示结果
  function setViewToggle(view) {
    const q = document.getElementById("btn-view-qualified");
    const a = document.getElementById("btn-view-all");
    if (q) q.classList.toggle("active", view === "qualified");
    if (a) a.classList.toggle("active", view === "all");
  }

  function displayResults(results, stats) {
    debugLog("📊 显示结果:", { results: results?.length, stats });

    if (stats) {
      const totalEl = document.getElementById("stat-total");
      const qualifiedEl = document.getElementById("stat-qualified");
      if (totalEl) totalEl.textContent = stats.total || 0;
      if (qualifiedEl) qualifiedEl.textContent = stats.qualified || 0;
      if (statsCard) statsCard.style.display = "block";
    }

    // 有结果就显示"达标/全部"切换入口
    const viewToggle = document.getElementById("view-toggle");
    if (viewToggle && (stats?.total || 0) > 0) {
      viewToggle.style.display = "flex";
    }

    if (results && results.length > 0) {
      if (emptyState) emptyState.style.display = "none";
      qualifiedJobs = results;
      currentView = "qualified";
      setViewToggle("qualified");
      renderJobsList(results);
    } else if (allJobs && allJobs.length > 0) {
      // 没有达标岗位但有分析结果：自动切到"全部"视图，别让用户面对空白
      qualifiedJobs = [];
      if (emptyState) emptyState.style.display = "none";
      currentView = "all";
      setViewToggle("all");
      renderJobsList(allJobs);
    } else {
      qualifiedJobs = [];
      const jobsList = document.getElementById("jobs-list");
      if (jobsList) {
        jobsList.innerHTML = `
          <section class="empty-state">
              <div class="empty-state__icon">⌗</div>
              <h3 class="empty-state__title">暂无合格岗位</h3>
              <p class="empty-state__hint">
                  搜索到 <strong>${stats?.total || 0}</strong> 个岗位，没有评分达标的。可点上方"全部岗位"查看逐个评分。
              </p>
          </section>
        `;
      }
      if (emptyState) emptyState.style.display = "none";
    }
  }

  // 渲染岗位列表
  function renderJobsList(jobs) {
    debugLog("🎨 渲染岗位列表:", jobs.length);
    if (!jobsList) return;
    jobsList.innerHTML = "";
    // 添加岗位卡片
    jobs.forEach((job, index) => {
      const jobCard = createJobCard(job, index + 1);
      if (jobCard) {
        jobsList.appendChild(jobCard);
      }
    });
  }

  // 创建岗位卡片（editorial design）
  function createJobCard(job, index) {
    const div = document.createElement("div");
    div.className = "job-card";

    const score = Number(job.score) || 0;
    const tier = score >= 8 ? "high" : score >= 5 ? "mid" : "low";
    div.setAttribute("data-score-tier", tier);

    const highlights = (job.match_highlights || []).filter(Boolean);
    const gaps = (job.gaps || []).filter(Boolean);
    const escape = (s) =>
      (s || "")
        .toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");

    div.innerHTML = `
        <div class="job-card__score">
            ${score}
            <span class="job-card__score-out">/ 10</span>
        </div>
        <div class="job-card__body">
            <h3 class="job-card__title">${escape(cleanMarkdown(job.title)) || "未知岗位"}</h3>
            <div class="job-card__meta">
                <span>${escape(cleanMarkdown(job.company)) || "未知公司"}</span>
                <span class="job-card__meta-divider">·</span>
                <span>${escape(cleanMarkdown(job.salary)) || "薪资面议"}</span>
                <span class="job-card__meta-divider">·</span>
                <span>${escape(job.work_location) || "未知地点"}</span>
                ${job.url ? `<span class="job-card__meta-divider">·</span><a href="${escape(job.url)}" target="_blank" rel="noopener">原文链接 ↗</a>` : ""}
            </div>
            ${job.summary ? `<div class="job-card__summary">"${escape(job.summary)}"</div>` : ""}
            ${
              highlights.length
                ? `
                <div class="job-card__highlights">
                    <span class="point-label point-label--match">Highlights · 亮点</span>
                    <ul class="job-card__pointlist job-card__pointlist--match">
                        ${highlights.map((h) => `<li>${escape(h)}</li>`).join("")}
                    </ul>
                </div>
            `
                : ""
            }
            ${
              gaps.length
                ? `
                <div class="job-card__gaps">
                    <span class="point-label point-label--gap">Gaps · 差距</span>
                    <ul class="job-card__pointlist job-card__pointlist--gap">
                        ${gaps.map((g) => `<li>${escape(g)}</li>`).join("")}
                    </ul>
                </div>
            `
                : ""
            }
            <div class="job-card__actions">
                <button class="btn-secondary" onclick="toggleJobDetails(${index})" id="toggle-details-${index}" type="button">
                    岗位 JD 全文
                </button>
                <button class="btn-secondary" onclick="toggleJobAnalysis(${index})" id="toggle-analysis-${index}" type="button">
                    AI 完整分析
                </button>
            </div>
        </div>
    `;

    // 准备岗位详情内容（隐藏状态，等待展开）
    const hasJobDetails =
      (job.job_description &&
        job.job_description !== "具体要求请查看岗位详情" &&
        !job.job_description.includes("基于文本解析的岗位描述")) ||
      (job.job_requirements &&
        job.job_requirements !== "具体要求请查看岗位详情");

    if (hasJobDetails) {
      // 合并工作职责和任职资格内容
      let combinedContent = "";

      // 添加工作职责内容
      if (job.job_description && job.job_description.length > 20) {
        combinedContent += job.job_description;
      }

      // 添加任职资格内容（如果存在且不重复）
      if (job.job_requirements && job.job_requirements.length > 20) {
        // 如果工作职责中没有包含任职资格内容，则添加
        if (!combinedContent.includes(job.job_requirements.substring(0, 50))) {
          if (combinedContent) {
            combinedContent += "\\n\\n";
          }
          combinedContent += job.job_requirements;
        }
      }

      if (combinedContent) {
        // 清理文本格式
        const cleanedContent = window.cleanJobText(combinedContent);
        const isLong = cleanedContent.length > 800;
        const displayText = isLong
          ? cleanedContent.substring(0, 800)
          : cleanedContent;
        const detailId = "detail_" + Math.random().toString(36).substr(2, 9);

        const jobDetailsDiv = document.createElement("div");
        jobDetailsDiv.id = `job-details-${index}`;
        jobDetailsDiv.className = "job-details-panel hidden mt-4";
        jobDetailsDiv.style.display = "none";

        jobDetailsDiv.innerHTML = `
                    <div class="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <div class="text-sm font-medium text-gray-900 mb-3">📋 岗位详情</div>
                        <div class="text-xs text-gray-700 whitespace-pre-wrap" id="${detailId}_desc">
                            ${displayText}${isLong ? "..." : ""}
                        </div>
                        ${
                          isLong
                            ? `
                            <button data-detail-id="${detailId}_desc" data-full-text="${encodeURIComponent(cleanedContent)}" 
                                    onclick="toggleJobDetailSafe(this)" 
                                    class="text-xs text-blue-600 hover:text-blue-800 mt-2 underline">
                                展开全文
                            </button>
                        `
                            : ""
                        }
                    </div>
                `;

        div.appendChild(jobDetailsDiv);
      }
    }

    // 准备匹配分析面板（隐藏状态）
    {
      const analysisDiv = document.createElement("div");
      analysisDiv.id = `job-analysis-${index}`;
      analysisDiv.className = "job-analysis-panel hidden mt-4";
      analysisDiv.style.display = "none";

      const highlights = (job.match_highlights || [])
        .map((h) => `<li class="text-xs text-gray-600">• ${h}</li>`)
        .join("");
      const gaps = (job.gaps || [])
        .map((g) => `<li class="text-xs text-gray-600">• ${g}</li>`)
        .join("");

      analysisDiv.innerHTML = `
                <div class="bg-gradient-to-br from-green-50 to-blue-50 border border-green-200 rounded-lg p-4">
                    <div class="text-sm font-semibold text-gray-900 mb-4">📊 匹配度详情（${score}/10）</div>
                    <div class="grid grid-cols-2 gap-4 mb-4">
                        <div>
                            <div class="text-xs font-medium text-green-700 mb-2">✅ 匹配亮点</div>
                            <ul class="space-y-1">${highlights || '<li class="text-xs text-gray-500">暂无</li>'}</ul>
                        </div>
                        <div>
                            <div class="text-xs font-medium text-orange-700 mb-2">⚠️ 待补强</div>
                            <ul class="space-y-1">${gaps || '<li class="text-xs text-gray-500">暂无</li>'}</ul>
                        </div>
                    </div>
                </div>
            `;

      div.appendChild(analysisDiv);
    }

    return div;
  }

  // 切换岗位详情展示
  window.toggleJobDetails = function (index) {
    const detailsPanel = document.getElementById(`job-details-${index}`);
    const toggleBtn = document.getElementById(`toggle-details-${index}`);

    if (detailsPanel && toggleBtn) {
      const isHidden =
        detailsPanel.style.display === "none" ||
        detailsPanel.style.display === "";

      if (isHidden) {
        detailsPanel.style.display = "block";
        detailsPanel.classList.remove("hidden");
        toggleBtn.innerHTML = "📋 收起岗位详情 ↑";
        toggleBtn.className = toggleBtn.className.replace(
          "bg-blue-50 hover:bg-blue-100 text-blue-700",
          "bg-gray-100 hover:bg-gray-200 text-gray-700",
        );
      } else {
        detailsPanel.style.display = "none";
        detailsPanel.classList.add("hidden");
        toggleBtn.innerHTML = "📋 查看岗位详情 ↓";
        toggleBtn.className = toggleBtn.className.replace(
          "bg-gray-100 hover:bg-gray-200 text-gray-700",
          "bg-blue-50 hover:bg-blue-100 text-blue-700",
        );
      }
    }
  };

  // 切换匹配分析展示
  window.toggleJobAnalysis = function (index) {
    const analysisPanel = document.getElementById(`job-analysis-${index}`);
    const toggleBtn = document.getElementById(`toggle-analysis-${index}`);

    if (analysisPanel && toggleBtn) {
      const isHidden =
        analysisPanel.style.display === "none" ||
        analysisPanel.style.display === "";

      if (isHidden) {
        analysisPanel.style.display = "block";
        analysisPanel.classList.remove("hidden");
        toggleBtn.innerHTML = "📊 收起匹配分析 ↑";
        toggleBtn.className = toggleBtn.className.replace(
          "bg-green-50 hover:bg-green-100 text-green-700",
          "bg-gray-100 hover:bg-gray-200 text-gray-700",
        );
      } else {
        analysisPanel.style.display = "none";
        analysisPanel.classList.add("hidden");
        toggleBtn.innerHTML = "📊 查看匹配分析 ↓";
        toggleBtn.className = toggleBtn.className.replace(
          "bg-gray-100 hover:bg-gray-200 text-gray-700",
          "bg-green-50 hover:bg-green-100 text-green-700",
        );
      }
    }
  };

  // 获取所有岗位
  async function fetchAllJobs() {
    try {
      const response = await axios.get("/api/jobs/all");
      if (response.data && response.data.jobs) {
        allJobs = response.data.jobs;
        if (currentView === "all") {
          renderJobsList(allJobs);
        }
      }
    } catch (error) {
      console.error("❌ 获取所有岗位失败:", error);
      alert("获取数据失败: " + error.message);
    }
  }

  // ========== 初始化完成 ==========
  debugLog("✅ 系统初始化完成！");
  debugLog("📊 初始化状态:", {
    socket: socket.connected ? "已连接" : "未连接",
    resumeFileInput: resumeFileInput ? "已找到" : "未找到",
    uploadArea: uploadArea ? "已找到" : "未找到",
    startBtn: startBtn ? "已找到" : "未找到",
  });

  // ========== 简历上传功能 ==========
  debugLog("📎 设置简历上传功能...");

  // 文件上传事件
  if (resumeFileInput) {
    resumeFileInput.addEventListener("change", function (e) {
      if (e.target.files.length > 0) {
        uploadResume(e.target.files[0]);
      }
    });
  }

  // 拖拽上传支持
  if (uploadArea) {
    uploadArea.addEventListener("dragover", function (e) {
      e.preventDefault();
      uploadArea.classList.add("dragover");
    });

    uploadArea.addEventListener("dragleave", function (e) {
      e.preventDefault();
      uploadArea.classList.remove("dragover");
    });

    uploadArea.addEventListener("drop", function (e) {
      e.preventDefault();
      uploadArea.classList.remove("dragover");

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        const file = files[0];
        if (
          file.type === "application/pdf" ||
          file.type ===
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
          file.type === "text/plain"
        ) {
          uploadResume(file);
        } else {
          alert("请上传PDF、DOCX或TXT格式的文件");
        }
      }
    });
  }

  // 上传简历函数
  async function uploadResume(file) {
    debugLog("📤 开始上传简历:", file.name);

    // 显示上传进度
    if (uploadProgress) uploadProgress.style.display = "block";
    if (uploadArea) uploadArea.style.display = "none";

    const formData = new FormData();
    formData.append("resume", file);

    try {
      // 模拟上传进度
      let progress = 0;
      const progressInterval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress >= 90) {
          clearInterval(progressInterval);
          progress = 90;
        }
        updateUploadProgress(progress);
      }, 200);

      // 发送到后端
      const response = await axios.post("/api/upload_resume", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      clearInterval(progressInterval);
      updateUploadProgress(100);

      setTimeout(() => {
        if (response.data.success) {
          // 隐藏上传进度
          if (uploadProgress) uploadProgress.style.display = "none";

          // 更新简历状态 - 简化版本，不再显示AI分析
          updateResumeStatus(response.data.resume_data);

          debugLog("✅ 简历上传成功:", response.data.resume_data.name);
        } else {
          alert("简历上传失败: " + response.data.error);
          resetUploadArea();
        }
      }, 500);
    } catch (error) {
      console.error("❌ 上传失败:", error);
      alert("上传失败: " + (error.response?.data?.error || error.message));
      resetUploadArea();
    }
  }
}); // DOMContentLoaded结束
