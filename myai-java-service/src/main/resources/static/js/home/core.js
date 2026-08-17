let isChatProcessing = false;
let isMemWriteProcessing = false;
let isMemQueryProcessing = false;
let isMemoryProfileProcessing = false;
let isKnowledgeUploadProcessing = false;
let isKnowledgeQueryProcessing = false;
let isKnowledgeMaintenanceProcessing = false;
let isTaskProcessing = false;
let currentBackgroundTaskRunId = null;
let selectedTaskRunId = null;
let taskRuns = [];
let taskPollTimer = null;
let currentConversationId = null;
let chatStatusController = null;
let memoryStateFilter = "all";
let memoryConsolidationFilter = "all";
let memoryVisibilityFilter = "visible";
let memoryViewMode = "simple";
let isMemorySettingsProcessing = false;
let latestAgentTrace = null;
let isHealthCenterProcessing = false;

function csrfHeaders() {
    const token = document.querySelector('meta[name="_csrf"]')?.content;
    const header = document.querySelector('meta[name="_csrf_header"]')?.content;
    if (!token || !header) {
        return {};
    }
    return { [header]: token };
}

async function readJsonResponse(response, label) {
    const contentType = response.headers.get("content-type") || "";
    if (!response.ok) {
        if (contentType.includes("application/json")) {
            const payload = await response.json();
            const detail = payload.message || payload.error || JSON.stringify(payload);
            throw new Error(`${label} HTTP ${response.status}: ${detail}`);
        }
        throw new Error(`${label} HTTP ${response.status}`);
    }
    if (!contentType.includes("application/json")) {
        const text = await response.text();
        const preview = text.replace(/\s+/g, " ").trim().slice(0, 120);
        throw new Error(`${label} expected JSON but received ${contentType || "unknown"}: ${preview}`);
    }
    return response.json();
}

function switchTab(tab) {
    ["chat", "memory", "knowledge", "task", "observability", "demo", "settings"].forEach(name => {
        document.getElementById(`sidebar-${name}`).classList.remove("active");
        document.getElementById(`${name}-section`).classList.remove("active");
    });

    document.getElementById(`sidebar-${tab}`).classList.add("active");
    document.getElementById(`${tab}-section`).classList.add("active");

    if (tab === "knowledge") {
        loadKnowledgeFiles();
    }
    if (tab === "memory") {
        loadMemoryProfile();
    }
    if (tab === "task") {
        loadTaskRuns();
        loadTaskTools();
    }
    if (tab === "observability") {
        loadObservabilityWorkbench();
    }
    if (tab === "demo") {
        renderDemoGuidance("选择一个场景开始演示。所有示例都只会填入内容或跳转，不会自动提交敏感操作。");
    }
    if (tab === "settings") {
        loadMemorySettings();
        loadSystemHealthCenter();
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.innerText = text;
    return div.innerHTML;
}

function appendUserMessage(text) {
    const box = document.getElementById("chat-box");
    const div = document.createElement("div");
    div.className = "message user-message";
    div.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function setAgentStatus(status, text) {
    const dot = document.getElementById("agent-status-dot");
    const label = document.getElementById("agent-status-text");
    if (!dot || !label) return;
    dot.classList.remove("busy", "error");
    if (status === "busy") {
        dot.classList.add("busy");
    }
    if (status === "error") {
        dot.classList.add("error");
    }
    label.innerText = text;
}

function renderChatEmptyState() {
    return `
        <div class="chat-empty-state" id="chat-empty-state">
            <h3>开始一次智能体对话</h3>
            <p>可以直接提问，也可以让 MyAI 调用记忆、知识库、任务和工具。每轮回答后，右侧会显示本轮执行摘要。</p>
            <div class="suggestion-grid">
                <button class="suggestion-card" onclick="useChatSuggestion('总结一下我最近的项目推进状态，并指出下一步最值得做什么')">总结项目推进状态</button>
                <button class="suggestion-card" onclick="useChatSuggestion('根据我的记忆和知识库，帮我制定今天的工作计划')">生成今日工作计划</button>
                <button class="suggestion-card" onclick="useChatSuggestion('检索知识库，回答一个带引用的问题')">知识库引用问答</button>
                <button class="suggestion-card" onclick="useChatSuggestion('创建一个可执行任务，并展示执行轨迹')">运行任务并看轨迹</button>
            </div>
        </div>
    `;
}

function ensureChatEmptyState() {
    const box = document.getElementById("chat-box");
    if (box && box.children.length === 0) {
        box.innerHTML = renderChatEmptyState();
    }
}

function removeChatEmptyState() {
    const empty = document.getElementById("chat-empty-state");
    if (empty) {
        empty.remove();
    }
}

function useChatSuggestion(text) {
    const input = document.getElementById("chat-message");
    input.value = text;
    input.focus();
}

function renderDemoGuidance(message) {
    const result = document.getElementById("demo-guidance-result");
    if (!result) return;
    result.style.display = "block";
    result.innerText = message;
}

function startDemoScenario(name) {
    const scenarios = {
        memory: {
            tab: "chat",
            message: "我喜欢用 Python 做数据分析。更正一下：我现在更喜欢用 Java 和 Python 搭配做智能体项目。请记住这个偏好，并说明你会如何处理旧偏好。",
            guidance: "已填入记忆纠正示例。发送后可展开 trace，再到记忆页查看 current/history、pending 和治理元数据。"
        },
        knowledge: {
            tab: "knowledge",
            guidance: "已打开知识库。先上传或选择一个文件，然后在查询框中提问，例如：请基于当前文档总结核心观点，并给出引用。"
        },
        task: {
            tab: "task",
            task: "检查当前系统信息，并用三点总结运行环境状态。如果可用，请在结果里展示执行步骤。",
            guidance: "已填入任务示例。点击执行或后台执行后，可查看任务 timeline、工具调用和结果摘要。"
        },
        mcp: {
            tab: "task",
            task: "读取本地文件 sample-knowledge.txt，并列出 Aurora Lantern 的发布编号、演示时间和回滚编号。",
            guidance: "已填入本地 MCP-style 只读工具示例。便携版只允许访问包内 demo 目录；点击执行后可查看 connector、policy 和 trace。标准 MCP Server 互操作将在下一检查点接入。"
        },
        observability: {
            tab: "observability",
            guidance: "已打开观测工作台。可以运行 MCP Eval 或全部 Eval，然后回到设置页查看系统健康中心中的 gate 状态。"
        }
    };
    const scenario = scenarios[name];
    if (!scenario) return;
    switchTab(scenario.tab);
    if (scenario.message) {
        const input = document.getElementById("chat-message");
        input.value = scenario.message;
        input.focus();
        setAgentStatus("ready", scenario.guidance);
    }
    if (scenario.task) {
        const input = document.getElementById("task-input");
        input.value = scenario.task;
        input.focus();
        showTaskResult(`<p>${escapeHtml(scenario.guidance)}</p>`);
    }
    if (name === "knowledge") {
        const input = document.getElementById("knowledge-query-input");
        input.value = "请基于当前文档总结核心观点，并给出引用。";
        input.focus();
        const result = document.getElementById("knowledge-query-result");
        result.style.display = "block";
        result.innerText = scenario.guidance;
    }
    if (name === "observability") {
        const result = document.getElementById("observability-summary");
        result.innerText = scenario.guidance;
    }
    renderDemoGuidance(scenario.guidance);
}

function formatTraceTime(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }
    return date.toLocaleString();
}

function formatTraceMetadata(metadata) {
    if (!metadata || Object.keys(metadata).length === 0) {
        return "";
    }
    return JSON.stringify(metadata, null, 2);
}

function parseJsonMaybe(value, fallback = []) {
    if (Array.isArray(value) || (value && typeof value === "object")) {
        return value;
    }
    if (typeof value !== "string" || value.trim() === "") {
        return fallback;
    }
    try {
        return JSON.parse(value);
    } catch (error) {
        return fallback;
    }
}

function compactNumber(value) {
    const number = Number(value);
    if (Number.isNaN(number)) {
        return value === null || value === undefined ? "" : String(value);
    }
    return number.toFixed(3);
}

function renderKeyValueGrid(items) {
    const visible = items.filter(item => item.value !== null && item.value !== undefined && String(item.value) !== "");
    if (visible.length === 0) {
        return "";
    }
    return `
        <div class="memory-observe-grid">
            ${visible.map(item => `
                <div class="memory-observe-item">
                    <span class="memory-observe-label">${escapeHtml(item.label)}</span>
                    <span class="memory-observe-value">${escapeHtml(String(item.value))}</span>
                </div>
            `).join("")}
        </div>
    `;
}

function renderMemoryCitations(metadata) {
    const citations = metadata && Array.isArray(metadata.citations) ? metadata.citations : [];
    if (citations.length === 0) {
        return "";
    }
    return `
        <div class="trace-step-detail">记忆引用：</div>
        ${citations.map(citation => `
            <div class="trace-step-detail">
                # ${escapeHtml(citation.memory_id || "")}
                ${escapeHtml(citation.mem_type || "memory")}
                confidence=${escapeHtml(String(citation.confidence ?? ""))}
                source=${escapeHtml(citation.source || "unknown")}
                <br>${escapeHtml(citation.content || "")}
            </div>
        `).join("")}
    `;
}

function renderMemoryRetrievalExplanations(metadata) {
    const explanations = metadata && Array.isArray(metadata.retrieval_explanations)
        ? metadata.retrieval_explanations
        : [];
    if (explanations.length === 0) {
        return "";
    }
    const selectedCount = explanations.filter(item => item.selected).length;
    const filteredCount = explanations.length - selectedCount;
    return `
        <div class="trace-step-detail">检索解释：selected ${selectedCount} / filtered ${filteredCount}</div>
        <div class="trace-explanation-grid">
        ${explanations.map(item => {
            const state = item.selected ? "selected" : "filtered";
            const factors = item.factors || {};
            return `
                <div class="trace-explanation-card ${state}">
                    <div class="trace-explanation-title">
                        <span>${escapeHtml(state)} # ${escapeHtml(item.memory_id || "")}</span>
                        <span>score=${escapeHtml(compactNumber(item.final_score ?? 0))}</span>
                    </div>
                    <div class="trace-explanation-body">
                        reason=${escapeHtml(item.reason || "")}
                        <br>sim=${escapeHtml(compactNumber(factors.similarity))}
                        confidence=${escapeHtml(compactNumber(factors.confidence))}
                        raw=${escapeHtml(compactNumber(factors.raw_confidence))}
                        review=${escapeHtml(String(factors.review_status ?? ""))}
                        sensitivity=${escapeHtml(String(factors.sensitivity ?? ""))}
                        source=${escapeHtml(String(factors.source ?? ""))}
                        <br>${escapeHtml(item.content || "")}
                    </div>
                </div>
            `;
        }).join("")}
        </div>
    `;
}

function renderKnowledgeCitations(metadata) {
    const citations = metadata && Array.isArray(metadata.citations) ? metadata.citations : [];
    if (citations.length === 0) {
        return "";
    }
    return `
        <div class="trace-step-detail">知识引用：</div>
        ${citations.map(citation => `
            <div class="trace-step-detail">
                # ${escapeHtml(citation.citation_id || citation.chunk_id || "")}
                ${escapeHtml(citation.file_name || "knowledge")}
                chunk=${escapeHtml(String(citation.chunk_index ?? ""))}
                rank=${escapeHtml(String(citation.final_rank ?? ""))}
                score=${escapeHtml(compactNumber(citation.rerank_score ?? citation.score ?? 0))}
                <br>${escapeHtml(citation.snippet || "")}
            </div>
        `).join("")}
    `;
}

function renderKnowledgeRetrievalExplanations(metadata) {
    const explanations = metadata && Array.isArray(metadata.retrieval_explanations)
        ? metadata.retrieval_explanations
        : [];
    if (explanations.length === 0) {
        return "";
    }
    return `
        <div class="trace-step-detail">知识检索解释：selected ${escapeHtml(String(explanations.filter(item => item.selected).length))} / ${escapeHtml(String(explanations.length))}</div>
        <div class="trace-explanation-grid">
        ${explanations.map(item => {
            const state = item.selected ? "selected" : "filtered";
            const factors = item.factors || {};
            return `
                <div class="trace-explanation-card ${state}">
                    <div class="trace-explanation-title">
                        <span>${escapeHtml(state)} # ${escapeHtml(item.citation_id || item.chunk_id || "")}</span>
                        <span>rerank=${escapeHtml(compactNumber(item.rerank_score ?? 0))}</span>
                    </div>
                    <div class="trace-explanation-body">
                        reason=${escapeHtml(item.reason || "")}
                        <br>mode=${escapeHtml(item.retrieval_mode || "")}
                        retrieval=${escapeHtml(compactNumber(item.retrieval_score ?? 0))}
                        vector=${escapeHtml(compactNumber(factors.vector_score ?? 0))}
                        keyword=${escapeHtml(compactNumber(factors.keyword_score ?? 0))}
                        coverage=${escapeHtml(compactNumber(factors.query_coverage ?? 0))}
                        <br>${escapeHtml(item.snippet || "")}
                    </div>
                </div>
            `;
        }).join("")}
        </div>
    `;
}

function renderTracePanel(trace) {
    if (!trace || !Array.isArray(trace.steps) || trace.steps.length === 0) {
        return "";
    }

    const totalLatency = trace.steps.reduce((sum, step) => sum + Number(step.latency_ms || 0), 0);
    const stepsHtml = trace.steps.map((step, index) => {
        const metadata = formatTraceMetadata(step.metadata || {});
        const status = String(step.status || "unknown");
        const citations = step.name === "memory.retrieve" ? renderMemoryCitations(step.metadata || {}) : "";
        const retrievalExplanations = step.name === "memory.retrieve" ? renderMemoryRetrievalExplanations(step.metadata || {}) : "";
        const knowledgeCitations = step.name === "knowledge.retrieve" ? renderKnowledgeCitations(step.metadata || {}) : "";
        const knowledgeRetrievalExplanations = step.name === "knowledge.retrieve" ? renderKnowledgeRetrievalExplanations(step.metadata || {}) : "";
        return `
            <div class="trace-step">
                <div class="trace-step-title">
                    <span class="trace-step-name">${index + 1}. ${escapeHtml(step.name || "unknown.step")}</span>
                    <span class="trace-step-status ${status === "failed" ? "failed" : ""}">${escapeHtml(status)}</span>
                </div>
                <div class="trace-step-detail">耗时：${escapeHtml(String(step.latency_ms ?? ""))} ms</div>
                ${step.input_summary ? `<div class="trace-step-detail">输入：${escapeHtml(String(step.input_summary))}</div>` : ""}
                ${step.output_summary ? `<div class="trace-step-detail">输出：${escapeHtml(String(step.output_summary))}</div>` : ""}
                ${citations}
                ${retrievalExplanations}
                ${knowledgeCitations}
                ${knowledgeRetrievalExplanations}
                ${metadata ? `<pre class="trace-step-metadata">${escapeHtml(metadata)}</pre>` : ""}
            </div>
        `;
    }).join("");

    return `
        <details class="trace-panel">
            <summary>
                <span>本轮执行轨迹</span>
                <span>${escapeHtml(String(trace.steps.length))} steps</span>
            </summary>
            <div class="trace-meta">
                <span>Run：${escapeHtml(trace.run_id || "")}</span>
                <span>状态：${escapeHtml(trace.status || "")}</span>
                <span>开始：${escapeHtml(formatTraceTime(trace.started_at))}</span>
                <span>结束：${escapeHtml(formatTraceTime(trace.finished_at))}</span>
                <span>总耗时：${escapeHtml(totalLatency.toFixed(1))} ms</span>
            </div>
            ${stepsHtml}
        </details>
    `;
}

function summarizeTraceForPanel(trace) {
    const steps = Array.isArray(trace?.steps) ? trace.steps : [];
    const totalLatency = steps.reduce((sum, step) => sum + Number(step.latency_ms || 0), 0);
    const memoryStep = steps.find(step => step.name === "memory.retrieve");
    const knowledgeStep = steps.find(step => step.name === "knowledge.retrieve");
    const taskSteps = steps.filter(step => String(step.name || "").includes("task"));
    const memoryMetadata = memoryStep?.metadata || {};
    const knowledgeMetadata = knowledgeStep?.metadata || {};
    const memoryCitations = Array.isArray(memoryMetadata.citations) ? memoryMetadata.citations : [];
    const memoryExplanations = Array.isArray(memoryMetadata.retrieval_explanations) ? memoryMetadata.retrieval_explanations : [];
    const knowledgeCitations = Array.isArray(knowledgeMetadata.citations) ? knowledgeMetadata.citations : [];
    const knowledgeExplanations = Array.isArray(knowledgeMetadata.retrieval_explanations) ? knowledgeMetadata.retrieval_explanations : [];
    return {
        steps,
        totalLatency,
        memoryCount: memoryCitations.length || memoryExplanations.filter(item => item.selected).length,
        knowledgeCount: knowledgeCitations.length || knowledgeExplanations.filter(item => item.selected).length,
        taskCount: taskSteps.length,
        failedCount: steps.filter(step => step.status === "failed").length,
        stepNames: steps.map(step => step.name || "unknown.step").slice(0, 8),
        memoryPreview: memoryCitations.slice(0, 2).map(item => item.content || item.memory_id || "memory"),
        knowledgePreview: knowledgeCitations.slice(0, 2).map(item => item.file_name || item.citation_id || item.chunk_id || "knowledge"),
        taskPreview: taskSteps.slice(0, 2).map(item => item.output_summary || item.input_summary || item.name || "task")
    };
}

function updateAgentContextPanel(trace = null, options = {}) {
    const stepsEl = document.getElementById("agent-trace-steps");
    const latencyEl = document.getElementById("agent-trace-latency");
    const memoryEl = document.getElementById("agent-memory-count");
    const knowledgeEl = document.getElementById("agent-knowledge-count");
    const tagsEl = document.getElementById("agent-trace-tags");
    const summaryEl = document.getElementById("agent-context-summary");
    if (!stepsEl || !latencyEl || !memoryEl || !knowledgeEl || !tagsEl || !summaryEl) {
        return;
    }

    if (!trace) {
        stepsEl.innerText = "0";
        latencyEl.innerText = "-";
        memoryEl.innerText = "0";
        knowledgeEl.innerText = "0";
        tagsEl.innerHTML = "";
        summaryEl.innerText = options.emptyText || "发送消息后，这里会显示记忆、知识和任务线索如何参与本轮回答。";
        return;
    }

    const summary = summarizeTraceForPanel(trace);
    stepsEl.innerText = String(summary.steps.length);
    latencyEl.innerText = `${summary.totalLatency.toFixed(0)} ms`;
    memoryEl.innerText = String(summary.memoryCount);
    knowledgeEl.innerText = String(summary.knowledgeCount);
    tagsEl.innerHTML = summary.stepNames.map(name => `<span class="agent-chip">${escapeHtml(name)}</span>`).join("");

    const parts = [];
    if (summary.memoryCount > 0) {
        parts.push(`记忆参与：${summary.memoryPreview.join(" / ") || `${summary.memoryCount} 条记忆`}`);
    } else {
        parts.push("本轮没有选中长期记忆。");
    }
    if (summary.knowledgeCount > 0) {
        parts.push(`知识引用：${summary.knowledgePreview.join(" / ") || `${summary.knowledgeCount} 条引用`}`);
    } else {
        parts.push("本轮没有选中知识库引用。");
    }
    if (summary.taskCount > 0) {
        parts.push(`任务线索：${summary.taskPreview.join(" / ")}`);
    }
    if (summary.failedCount > 0) {
        parts.push(`注意：${summary.failedCount} 个步骤失败，可展开回答下方轨迹查看。`);
    }
    summaryEl.innerText = parts.join("\n");
}
