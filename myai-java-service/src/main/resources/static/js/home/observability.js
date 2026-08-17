async function loadObservabilityWorkbench() {
    const summaryDiv = document.getElementById("observability-summary");
    const reportsDiv = document.getElementById("observability-reports");
    const eventsDiv = document.getElementById("observability-events");
    if (summaryDiv) summaryDiv.innerText = "正在加载观测摘要...";
    if (reportsDiv) reportsDiv.innerText = "正在加载报告...";
    if (eventsDiv) eventsDiv.innerText = "正在加载事件...";
    try {
        const [summaryResponse, reportsResponse, runsResponse, eventsResponse] = await Promise.all([
            fetch("/observability/summary", { method: "GET", headers: { ...csrfHeaders() } }),
            fetch("/eval/reports", { method: "GET", headers: { ...csrfHeaders() } }),
            fetch("/eval/runs?limit=5", { method: "GET", headers: { ...csrfHeaders() } }),
            fetch("/observability/events?limit=30", { method: "GET", headers: { ...csrfHeaders() } })
        ]);
        if (!summaryResponse.ok || !reportsResponse.ok || !runsResponse.ok || !eventsResponse.ok) {
            throw new Error("observability request failed");
        }
        const summary = await summaryResponse.json();
        const reports = await reportsResponse.json();
        const runs = await runsResponse.json();
        const events = await eventsResponse.json();
        summaryDiv.innerHTML = renderObservabilitySummary(summary, runs);
        reportsDiv.innerHTML = renderObservabilityReports(reports, runs);
        eventsDiv.innerHTML = renderObservabilityEvents(events.events || []);
    } catch (error) {
        console.error(error);
        if (summaryDiv) summaryDiv.innerText = "观测摘要加载失败";
        if (reportsDiv) reportsDiv.innerText = "报告列表加载失败";
        if (eventsDiv) eventsDiv.innerText = "事件加载失败";
    }
}

async function runEvalSuite(suite) {
    const summaryDiv = document.getElementById("observability-summary");
    if (summaryDiv) summaryDiv.innerText = `正在运行 ${suite} eval...`;
    try {
        const response = await fetch(`/eval/runs?suite=${encodeURIComponent(suite)}`, {
            method: "POST",
            headers: { ...csrfHeaders() }
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        await loadObservabilityWorkbench();
    } catch (error) {
        console.error(error);
        if (summaryDiv) summaryDiv.innerText = "运行 eval 失败";
    }
}

function healthPill(status) {
    const normalized = String(status || "unknown").toLowerCase();
    const css = normalized === "ok" || normalized === "healthy" || normalized === "passed" || normalized === "ready"
        ? "ok"
        : (normalized === "warn" || normalized === "degraded" || normalized === "unknown" ? "warn" : "fail");
    const label = {
        ok: "正常",
        healthy: "正常",
        passed: "通过",
        ready: "就绪",
        warn: "注意",
        degraded: "降级",
        unknown: "未知",
        failed: "失败",
        error: "错误",
        offline: "离线"
    }[normalized] || status || "未知";
    return `<span class="health-pill ${css}">${escapeHtml(String(label))}</span>`;
}

function renderHealthCard(title, status, detail, extraHtml = "") {
    return `
        <div class="health-card">
            <div class="health-card-title">
                <span>${escapeHtml(title)}</span>
                ${healthPill(status)}
            </div>
            <div class="health-detail">${detail}</div>
            ${extraHtml}
        </div>
    `;
}

function summarizeKnowledgeFiles(filesPayload) {
    const files = Array.isArray(filesPayload) ? filesPayload : [];
    const unhealthy = files.filter(file => {
        const health = String(file.health || "healthy");
        const stored = String(file.stored_file_status || "available");
        return health !== "healthy" || stored !== "available";
    });
    return {
        total: files.length,
        unhealthy: unhealthy.length,
        status: unhealthy.length > 0 ? "warn" : "ok",
        latest: files[0] || null
    };
}

function modelModeLabel(mode) {
    const labels = {
        stub: "Stub 模式",
        real: "真实模型",
        real_with_fallback: "真实模型优先，可回退 Stub",
        stub_fallback: "配置不完整，当前会回退 Stub",
        misconfigured: "配置不完整，且未启用回退"
    };
    return labels[mode] || (mode || "未知");
}

function modelModeHealth(model) {
    const roles = Object.values(model?.roles || {});
    if (roles.length === 0) {
        return "warn";
    }
    const probe = model?.last_probe;
    if (probe?.status === "degraded") {
        return "warn";
    }
    if (probe?.status === "healthy") {
        return "ok";
    }
    if (roles.some(role => role.effective_mode === "misconfigured")) {
        return "fail";
    }
    if (roles.some(role => ["stub", "stub_fallback", "real_with_fallback"].includes(role.effective_mode))) {
        return "warn";
    }
    return "ok";
}

function renderModelRoleLine(label, role) {
    if (!role) {
        return `<div>${escapeHtml(label)}：暂无状态</div>`;
    }
    const modelId = role.model_id || "(未配置 model id)";
    const missing = Array.isArray(role.missing) && role.missing.length > 0
        ? ` · 缺少：${role.missing.map(item => escapeHtml(item)).join(", ")}`
        : "";
    return `<div>${escapeHtml(label)}：${escapeHtml(role.provider || "unknown")} / ${escapeHtml(modelId)} · ${escapeHtml(modelModeLabel(role.effective_mode))}${missing}</div>`;
}

function renderModelStatusDetail(model) {
    if (!model || !model.roles) {
        return "尚未读取到 Python Agent 模型状态。";
    }
    const roles = model.roles || {};
    const probe = model.last_probe || null;
    const probeLine = probe
        ? `最近真实探测：${escapeHtml(modelProbeStatusLabel(probe.status))} · real ${escapeHtml(String(probe.summary?.successful_real_roles ?? 0))}/${escapeHtml(String(probe.summary?.real_roles ?? 0))} · ${escapeHtml(formatTraceTime(probe.finished_at || probe.started_at || ""))}`
        : "最近真实探测：尚未运行";
    return [
        `Provider Auth：${model.provider_auth_configured ? "已配置" : "未配置"} · Stub 回退：${model.fallback_to_stub ? "开启" : "关闭"}`,
        `Memory LLM Extractor：${model.memory_llm_extractor_enabled ? "启用" : "关闭"}`,
        probeLine,
        renderModelRoleLine("Chat", roles.chat),
        renderModelRoleLine("Task", roles.task),
        renderModelRoleLine("Memory", roles.memory),
        renderModelRoleLine("Embedding", roles.embedding)
    ].join("<br>");
}

function modelProbeStatusLabel(status) {
    const labels = {
        healthy: "真实模型可用",
        degraded: "真实模型异常，可能回退 Stub",
        stub_only: "仅 Stub 模式"
    };
    return labels[status] || (status || "未知");
}

function renderModelProbeResult(payload) {
    const probe = payload?.model_probe || payload;
    if (!probe || !probe.roles) {
        return "没有可展示的模型探测结果。";
    }
    const rows = Object.values(probe.roles).map(role => {
        const status = role.ok ? "正常" : (role.status === "misconfigured" ? "配置不完整" : "异常");
        const extra = role.ok
            ? `${escapeHtml(String(role.latency_ms ?? 0))}ms`
            : `${escapeHtml(role.error_type || (role.missing || []).join(", ") || role.status || "")}${role.error_message ? ` · ${escapeHtml(role.error_message)}` : ""}`;
        return `<div>${escapeHtml(role.role)}：${escapeHtml(role.provider || "")} / ${escapeHtml(role.model_id || "(未配置)")} · ${status} · ${extra}</div>`;
    }).join("");
    const network = probe.network || {};
    const proxyKeys = Array.isArray(network.env_proxy_keys) ? network.env_proxy_keys.join(", ") : "";
    return `
        <div class="health-list">
            <div>探测状态：${escapeHtml(modelProbeStatusLabel(probe.status))}</div>
            <div>真实角色：${escapeHtml(String(probe.summary?.successful_real_roles ?? 0))}/${escapeHtml(String(probe.summary?.real_roles ?? 0))}</div>
            <div>系统代理变量：${network.env_proxy_configured ? `检测到 ${escapeHtml(proxyKeys)}` : "未检测到"} · 模型客户端继承代理：${network.trust_env_proxy ? "是" : "否"}</div>
            ${rows}
        </div>
    `;
}

function buildSystemHealthPayload(results) {
    const [summaryResult, toolsResult, knowledgeResult, memoryResult, gateResult, reportsResult] = results;
    const summary = summaryResult.status === "fulfilled" ? summaryResult.value : null;
    const tools = toolsResult.status === "fulfilled" ? toolsResult.value : null;
    const knowledgeFiles = knowledgeResult.status === "fulfilled" ? knowledgeResult.value : [];
    const memoryPayload = memoryResult.status === "fulfilled" ? memoryResult.value : null;
    const memorySettings = memoryPayload?.settings || memoryPayload;
    const gateConfig = gateResult.status === "fulfilled" ? gateResult.value : null;
    const reports = reportsResult.status === "fulfilled" ? reportsResult.value : null;
    const connectors = tools?.connectors || summary?.connectors?.items || [];
    const privacy = tools?.privacy || summary?.privacy || {};
    const connectorSummary = tools?.summary || {};
    const knowledge = summarizeKnowledgeFiles(knowledgeFiles);
    const evalSummary = summary?.eval || {};
    const latestEval = evalSummary.latest || {};
    const latestEvalSummary = latestEval.summary || {};
    const failedFetches = results.filter(result => result.status === "rejected").length;
    const connectorHealthy = connectors.filter(connector => (connector.health || {}).ok !== false).length;
    const connectorTotal = connectors.length || Number(connectorSummary.connectors || 0);
    const overallStatus = failedFetches > 0
        ? "degraded"
        : (latestEval.status === "failed" || (connectorTotal && connectorHealthy < connectorTotal) || knowledge.unhealthy > 0 ? "warn" : "ok");
    return {
        summary,
        tools,
        knowledgeFiles,
        memorySettings,
        gateConfig,
        reports,
        connectors,
        connectorHealthy,
        connectorTotal,
        knowledge,
        evalSummary,
        latestEval,
        latestEvalSummary,
        failedFetches,
        overallStatus,
        privacy
    };
}

function renderSystemHealthCenter(payload) {
    const memorySettings = payload.memorySettings || {};
    const memoryEnabled = memorySettings.memory_enabled !== false;
    const autoWrite = memorySettings.auto_write_enabled !== false;
    const sensitiveConfirm = memorySettings.sensitive_requires_confirmation !== false;
    const gateConfig = payload.gateConfig?.config || {};
    const reportSummary = payload.reports?.summary || {};
    const modelDetail = [
        "模型密钥只在 Python Agent 环境变量中读取；前端仅显示配置状态，不显示密钥值。",
        `Eval 报告：${reportSummary.total ?? "-"} 个，deterministic=${reportSummary.deterministic ?? "-"}。`
    ].join("<br>");
    const model = payload.summary?.model || null;
    const connectorRows = payload.connectors.slice(0, 4).map(connector => {
        const health = connector.health || {};
        return `<div>${escapeHtml(connector.name || connector.server_id || "connector")} · ${escapeHtml(health.ok === false ? "异常" : "正常")} · ${escapeHtml(health.message || "")}</div>`;
    }).join("");
    const latestEvalDetail = payload.latestEval?.run_id
        ? `最近运行：${escapeHtml(payload.latestEval.suite || "")}<br>状态：${escapeHtml(payload.latestEval.status || "")}<br>Pass rate：${escapeHtml(String((payload.latestEvalSummary.pass_rate ?? 0) * 100))}%`
        : "尚未找到 eval 历史。";
    const overallText = payload.overallStatus === "ok"
        ? "核心能力状态良好，可以继续使用。"
        : "部分能力需要关注，建议查看下方异常或刷新对应模块。";
    return `
        <div class="health-hero">
            <div>
                <div class="health-status-title">MyAI 系统健康</div>
                <div class="health-status-text">${overallText}</div>
            </div>
            <div>
                <div class="health-card-title">
                    <span>总体状态</span>
                    ${healthPill(payload.overallStatus)}
                </div>
                <div class="health-detail">接口异常：${escapeHtml(String(payload.failedFetches))} · Connector：${escapeHtml(String(payload.connectorHealthy))}/${escapeHtml(String(payload.connectorTotal || 0))} · 知识文件：${escapeHtml(String(payload.knowledge.total))}</div>
            </div>
        </div>
        <div class="health-grid">
            ${renderHealthCard("Java / Python 服务", payload.summary ? "ok" : "fail", payload.summary ? "Java 前端可用，Python observability API 可访问。" : "无法读取 Python observability API。")}
            ${renderHealthCard("隐私边界", payload.privacy?.redaction_applied === false ? "warn" : "ok", `
                默认脱敏：${payload.privacy?.redaction_applied === false ? "关闭" : "开启"}<br>
                敏感信息：${payload.privacy?.sensitive_included ? "已包含" : "未包含"}<br>
                范围：本机路径、connector root、eval 存储路径、secret-like 字段
            `)}
            ${renderHealthCard("模型运行模式", modelModeHealth(model), renderModelStatusDetail(model), `
                <div class="health-actions">
                    <button class="action-button" onclick="runModelProbe()">实时探测真实模型</button>
                </div>
                <div id="model-probe-result" class="health-detail"></div>
            `)}
            ${renderHealthCard("模型与 Eval 配置", payload.gateConfig ? "ok" : "warn", modelDetail)}
            ${renderHealthCard("记忆策略", memorySettings ? "ok" : "warn", `
                长期记忆：${memoryEnabled ? "启用" : "关闭"}<br>
                自动写入：${autoWrite ? "启用" : "关闭"}<br>
                敏感确认：${sensitiveConfirm ? "启用" : "关闭"}<br>
                默认视图：${escapeHtml(memorySettings.default_memory_view || "simple")}
            `)}
            ${renderHealthCard("知识库", payload.knowledge.status, `
                文件数：${escapeHtml(String(payload.knowledge.total))}<br>
                需关注：${escapeHtml(String(payload.knowledge.unhealthy))}<br>
                最近文件：${escapeHtml(payload.knowledge.latest?.file_name || "无")}
            `)}
            ${renderHealthCard("Connector", payload.connectorTotal && payload.connectorHealthy < payload.connectorTotal ? "warn" : "ok", `
                健康：${escapeHtml(String(payload.connectorHealthy))}/${escapeHtml(String(payload.connectorTotal || 0))}
                <div class="health-list">${connectorRows || "暂无 connector 信息。"}</div>
            `)}
            ${renderHealthCard("Eval Gate", payload.latestEval.status === "failed" ? "fail" : (payload.latestEval.status || "warn"), `
                ${latestEvalDetail}<br>
                门禁：min pass rate=${escapeHtml(String(gateConfig.min_pass_rate ?? "-"))}, failed cases<=${escapeHtml(String(gateConfig.max_failed_cases ?? "-"))}
            `, `
                <div class="health-actions">
                    <button class="action-button" onclick="runHealthGate()">运行质量门禁</button>
                    <button class="action-button" onclick="switchTab('observability')">查看观测</button>
                </div>
            `)}
        </div>
    `;
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
        method: options.method || "GET",
        headers: {
            ...(options.body ? {"Content-Type": "application/json"} : {}),
            ...csrfHeaders()
        },
        body: options.body
    });
    if (!response.ok) {
        throw new Error(`${url} HTTP ${response.status}`);
    }
    return response.json();
}

async function loadSystemHealthCenter() {
    if (isHealthCenterProcessing) return;
    isHealthCenterProcessing = true;
    const target = document.getElementById("system-health-center");
    if (target) {
        target.innerHTML = `
            <div class="health-status-title">正在检查系统健康</div>
            <div class="health-status-text">正在读取服务状态、记忆策略、知识库、connector 和 eval gate。</div>
        `;
    }
    try {
        const results = await Promise.allSettled([
            fetchJson("/observability/summary"),
            fetchJson("/task/tools"),
            fetchJson("/knowledge/files"),
            fetchJson("/memory/settings"),
            fetchJson("/eval/gates/config"),
            fetchJson("/eval/reports")
        ]);
        const payload = buildSystemHealthPayload(results);
        if (target) {
            target.innerHTML = renderSystemHealthCenter(payload);
        }
    } catch (error) {
        console.error(error);
        if (target) {
            target.innerHTML = `
                <div class="health-status-title">系统健康检查失败</div>
                <div class="health-status-text">请确认 Java 服务、Python Agent 和本地端口均已启动。</div>
            `;
        }
    } finally {
        isHealthCenterProcessing = false;
    }
}

async function runHealthGate() {
    const target = document.getElementById("system-health-center");
    if (target) {
        target.innerHTML = `
            <div class="health-status-title">正在运行质量门禁</div>
            <div class="health-status-text">这会运行 deterministic eval gate，并将结果写入 eval 历史。</div>
        `;
    }
    try {
        await fetchJson("/eval/gates/run?suite=all", {method: "POST"});
        await loadSystemHealthCenter();
        await loadObservabilityWorkbench();
    } catch (error) {
        console.error(error);
        if (target) {
            target.innerHTML = `
                <div class="health-status-title">质量门禁运行失败</div>
                <div class="health-status-text">请检查 Python Agent eval API 和日志。</div>
            `;
        }
    }
}

async function runModelProbe() {
    const target = document.getElementById("model-probe-result");
    if (target) {
        target.innerHTML = "正在探测真实模型调用...";
    }
    try {
        const payload = await fetchJson("/observability/model/probe", {method: "POST"});
        if (target) {
            target.innerHTML = renderModelProbeResult(payload);
        }
        await loadSystemHealthCenter();
    } catch (error) {
        console.error(error);
        if (target) {
            target.innerHTML = "真实模型探测失败，请检查 Python Agent 日志。";
        }
    }
}

function renderObservabilitySummary(payload, runsPayload) {
    const task = payload.task || {};
    const planner = task.planner || {};
    const connectors = payload.connectors || {};
    const evalSummary = payload.eval || {};
    const latest = evalSummary.latest || {};
    const latestSummary = latest.summary || {};
    const runs = Array.isArray(runsPayload.runs) ? runsPayload.runs : [];
    return `
        ${renderPrivacyNotice(payload.privacy)}
        <div class="task-block">
            <strong>Runtime Metrics</strong>
            <div class="task-step">
                <div class="task-step-title">Task</div>
                <div class="task-step-detail">
                    runs=${escapeHtml(String(task.runs || 0))}
                    · workflow=${escapeHtml(String(planner.workflow_hits || 0))}
                    · rule=${escapeHtml(String(planner.rule_hits || 0))}
                    · failures=${escapeHtml(String(planner.failures || 0))}
                </div>
            </div>
            <div class="task-step">
                <div class="task-step-title">Connectors</div>
                <div class="task-step-detail">
                    healthy=${escapeHtml(String(connectors.healthy || 0))}
                    / total=${escapeHtml(String(connectors.total || 0))}
                </div>
                ${renderConnectorHealthRows(connectors.items || [])}
            </div>
            <div class="task-step ${latest.status === "failed" ? "fail" : ""}">
                <div class="task-step-title">Latest Eval</div>
                <div class="task-step-detail">
                    suite=${escapeHtml(String(latest.suite || "none"))}
                    · status=${escapeHtml(String(latest.status || "none"))}
                    · pass=${escapeHtml(String(latestSummary.passed || 0))}/${escapeHtml(String(latestSummary.total || 0))}
                    · runs=${escapeHtml(String(evalSummary.runs || runs.length || 0))}
                </div>
            </div>
        </div>
    `;
}

function renderConnectorHealthRows(items) {
    const connectors = Array.isArray(items) ? items : [];
    if (!connectors.length) return "";
    return connectors.map(connector => {
        const health = connector.health || {};
        return `
            <div class="task-step-detail">
                ${escapeHtml(connector.server_id || connector.name || "")}
                · ${escapeHtml(health.ok === false ? "unhealthy" : "healthy")}
                · tools=${escapeHtml(String(connector.tool_count || 0))}
            </div>
        `;
    }).join("");
}

function renderObservabilityReports(payload, runsPayload) {
    const reports = Array.isArray(payload.reports) ? payload.reports : [];
    const runs = Array.isArray(runsPayload.runs) ? runsPayload.runs : [];
    const latestRun = runs[0] || {};
    return `
        <div class="task-step-detail">
            reports=${escapeHtml(String((payload.summary || {}).total || reports.length))}
            · domains=${escapeHtml(((payload.summary || {}).domains || []).join(", "))}
            · latest=${escapeHtml(String(latestRun.suite || "none"))}
        </div>
        ${reports.map(report => `
            <div class="task-step">
                <div class="task-step-title">${escapeHtml(report.name || report.report_id || "")}</div>
                <div class="task-step-detail">
                    ${escapeHtml(report.domain || "")}
                    · strict=${escapeHtml(String(report.strict_supported !== false))}
                    · deterministic=${escapeHtml(String(report.deterministic !== false))}
                    ${report.requires_live_llm ? " · live LLM" : ""}
                </div>
                <div class="task-step-detail">${escapeHtml(report.description || "")}</div>
            </div>
        `).join("")}
    `;
}

function renderObservabilityEvents(events) {
    const list = Array.isArray(events) ? events : [];
    if (!list.length) {
        return "暂无事件";
    }
    return list.map(event => `
        <div class="task-step ${event.status === "failed" || event.type?.includes("failed") ? "fail" : ""}">
            <div class="task-step-title">${escapeHtml(event.domain || "event")} · ${escapeHtml(event.type || "")}</div>
            <div class="task-step-detail">
                status=${escapeHtml(String(event.status || ""))}
                ${event.tool_name ? ` · tool=${escapeHtml(String(event.tool_name))}` : ""}
                ${event.connector_id ? ` · connector=${escapeHtml(String(event.connector_id))}` : ""}
                ${event.latency_ms !== undefined && event.latency_ms !== null ? ` · latency=${escapeHtml(String(event.latency_ms))}ms` : ""}
                ${event.evidence_count ? ` · evidence=${escapeHtml(String(event.evidence_count))}` : ""}
            </div>
            ${event.started_at ? `<div class="task-step-detail">${escapeHtml(formatTraceTime(event.started_at))}</div>` : ""}
            ${event.message ? `<div class="task-step-detail">${escapeHtml(String(event.message))}</div>` : ""}
        </div>
    `).join("");
}
