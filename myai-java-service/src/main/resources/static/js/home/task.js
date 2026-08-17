function renderTaskTimeline(events) {
    const list = Array.isArray(events) ? events : [];
    if (list.length === 0) {
        return "";
    }
    return `
        <div class="task-block">
            <strong>执行时间线</strong>
            ${list.map(event => {
                const mcpSummary = renderTaskMcpEventSummary(event);
                const metadata = event.metadata && Object.keys(event.metadata).length > 0
                    ? `<div class="task-step-detail"><strong>Metadata：</strong>${escapeHtml(JSON.stringify(event.metadata, null, 2))}</div>`
                    : "";
                return `
                    <div class="task-step ${String(event.type || "").includes("failed") ? "fail" : ""}">
                        <div class="task-step-title">${escapeHtml(event.type || "task.event")}</div>
                        <div class="task-step-detail"><strong>状态：</strong>${escapeHtml(String(event.status || ""))}</div>
                        ${event.step_id ? `<div class="task-step-detail"><strong>步骤：</strong>${escapeHtml(String(event.step_id))}</div>` : ""}
                        ${event.timestamp ? `<div class="task-step-detail"><strong>时间：</strong>${escapeHtml(formatTraceTime(event.timestamp))}</div>` : ""}
                        ${event.message ? `<div class="task-step-detail">${escapeHtml(String(event.message))}</div>` : ""}
                        ${mcpSummary}
                        ${metadata}
                    </div>
                `;
            }).join("")}
        </div>
    `;
}

function renderTaskMcpEventSummary(event) {
    if (!String(event.type || "").startsWith("task.mcp_call.")) {
        return "";
    }
    const metadata = event.metadata || {};
    const parts = [
        `server=${metadata.server_id || ""}`,
        `tool=${metadata.tool_name || ""}`,
        `status=${metadata.call_status || ""}`,
        `latency=${metadata.call_latency_ms ?? ""}ms`
    ].filter(part => !part.endsWith("=") && !part.endsWith("=ms"));
    if (metadata.attempt && metadata.max_attempts) {
        parts.push(`attempt=${metadata.attempt}/${metadata.max_attempts}`);
    }
    if (metadata.error) {
        parts.push(`error=${metadata.error}`);
    }
    return `<div class="task-step-detail"><strong>MCP：</strong>${escapeHtml(parts.join(" · "))}</div>`;
}

function taskStatusClass(status) {
    return String(status || "").toLowerCase().replace(/[^a-z0-9_-]/g, "");
}

function taskStatusPill(status) {
    const value = String(status || "unknown");
    return `<span class="task-status-pill ${taskStatusClass(value)}">${escapeHtml(value)}</span>`;
}

function summarizeTaskContent(content) {
    const value = String(content || "");
    return value.length > 42 ? `${value.slice(0, 42)}...` : value;
}

function renderTaskSteps(steps) {
    const list = Array.isArray(steps) ? steps : [];
    if (list.length === 0) {
        return "";
    }
    return `
        <div class="task-block">
            <strong>步骤</strong>
            ${list.map((step, index) => `
                <div class="task-step ${step.status === "failed" ? "fail" : ""}">
                    <div class="task-step-title">步骤 ${index + 1}: ${escapeHtml(step.description || step.tool_name || step.step_id || "Untitled")}</div>
                    <div class="task-step-detail"><strong>状态：</strong>${escapeHtml(String(step.status || ""))}</div>
                    <div class="task-step-detail"><strong>工具：</strong>${escapeHtml(String(step.tool_name || ""))}</div>
                    ${step.latency_ms !== undefined && step.latency_ms !== null ? `<div class="task-step-detail"><strong>延迟：</strong>${escapeHtml(String(step.latency_ms))} ms</div>` : ""}
                    ${step.error ? `<div class="task-step-detail"><strong>错误：</strong>${escapeHtml(String(step.error))}</div>` : ""}
                    ${step.result ? `<details><summary>结果</summary><pre>${escapeHtml(JSON.stringify(step.result, null, 2))}</pre></details>` : ""}
                </div>
            `).join("")}
        </div>
    `;
}

function renderTaskMemoryContext(plan) {
    const context = plan && plan.memory_context ? plan.memory_context : null;
    const selected = context && Array.isArray(context.selected) ? context.selected : [];
    if (!context || (!context.enabled && selected.length === 0)) {
        return "";
    }
    const rows = selected.length > 0
        ? selected.map(memory => `
            <div class="task-step">
                <div class="task-step-title">${escapeHtml(String(memory.content || ""))}</div>
                <div class="task-step-detail">
                    <strong>类型：</strong>${escapeHtml(String(memory.mem_type || ""))}
                    ${memory.slot ? ` · <strong>Slot：</strong>${escapeHtml(String(memory.slot))}` : ""}
                    ${memory.final_score !== undefined ? ` · <strong>分数：</strong>${escapeHtml(String(memory.final_score))}` : ""}
                </div>
                <div class="task-step-detail">
                    <strong>来源：</strong>${escapeHtml(String(memory.source || "unknown"))}
                    ${memory.is_current === false ? " · historical" : ""}
                </div>
            </div>
        `).join("")
        : `<div class="task-step-detail">${context.error ? `检索失败：${escapeHtml(String(context.error))}` : "本轮规划未取用记忆"}</div>`;
    return `
        <div class="task-block">
            <strong>规划记忆引用</strong>
            ${rows}
        </div>
    `;
}

function renderTaskOutcomeMemory(result) {
    const outcome = result && result.outcome_memory ? result.outcome_memory : null;
    if (!outcome) {
        return "";
    }
    const governance = outcome.governance || {};
    const status = governance.review_status || (outcome.written ? "written" : "skipped");
    const memoryId = outcome.memory_id || outcome.target_memory_id || "";
    return `
        <div class="task-block">
            <strong>任务经验记忆</strong>
            <div class="task-step-detail"><strong>状态：</strong>${escapeHtml(String(status))}</div>
            ${memoryId ? `<div class="task-step-detail"><strong>Memory ID：</strong>${escapeHtml(String(memoryId))}</div>` : ""}
            <div class="task-step-detail"><strong>动作：</strong>${escapeHtml(String(outcome.action || (outcome.written ? "write" : "skip")))}</div>
            <div class="task-step-detail"><strong>原因：</strong>${escapeHtml(String(outcome.reason || governance.review_reason || ""))}</div>
        </div>
    `;
}

function renderTaskRunSnapshot(run) {
    let html = `
        <div class="task-detail-header">
            <div>
                <strong>${escapeHtml(summarizeTaskContent(run.content || "任务"))}</strong>
                <div class="task-run-meta">Run ID：${escapeHtml(String(run.task_run_id || ""))}</div>
            </div>
            ${taskStatusPill(run.status)}
        </div>
        <div class="task-summary-grid">
            <div class="task-summary-item">
                <div class="task-summary-label">创建时间</div>
                <div class="task-summary-value">${escapeHtml(run.created_at ? formatTraceTime(run.created_at) : "")}</div>
            </div>
            <div class="task-summary-item">
                <div class="task-summary-label">完成时间</div>
                <div class="task-summary-value">${escapeHtml(run.finished_at ? formatTraceTime(run.finished_at) : "")}</div>
            </div>
            <div class="task-summary-item">
                <div class="task-summary-label">耗时</div>
                <div class="task-summary-value">${escapeHtml(run.latency_ms !== undefined && run.latency_ms !== null ? `${run.latency_ms} ms` : "")}</div>
            </div>
            <div class="task-summary-item">
                <div class="task-summary-label">当前步骤</div>
                <div class="task-summary-value">${escapeHtml(String(run.current_step_id || ""))}</div>
            </div>
        </div>
    `;
    if (run.error) {
        html += `<div class="task-block"><strong>错误</strong><div class="task-step-detail">${escapeHtml(String(run.error))}</div></div>`;
    }
    html += renderTaskMemoryContext(run.plan);
    html += renderTaskSteps(run.steps);
    html += renderTaskTimeline(run.events);
    if (run.result) {
        const summary = run.result.summary ? `<div class="task-step-detail">${escapeHtml(String(run.result.summary))}</div>` : "";
        html += renderTaskOutcomeMemory(run.result);
        html += `<div class="task-block"><strong>结果</strong>${summary}<details><summary>Raw</summary><pre>${escapeHtml(JSON.stringify(run.result, null, 2))}</pre></details></div>`;
    }
    return html;
}

function showTaskResult(content) {
    const resultDiv = document.getElementById("task-result");
    const emptyState = document.getElementById("task-empty-state");
    if (!resultDiv) return;
    if (emptyState) {
        emptyState.style.display = "none";
    }
    resultDiv.style.display = "block";
    resultDiv.innerHTML = content;
}

function taskErrorHtml(prefix, error) {
    return `<p>${escapeHtml(prefix)}${error?.message ? `：${escapeHtml(error.message)}` : ""}</p>`;
}

function renderTaskRunList() {
    const listDiv = document.getElementById("task-run-list");
    if (!listDiv) return;
    if (!Array.isArray(taskRuns) || taskRuns.length === 0) {
        listDiv.innerHTML = `<div class="quiet-empty">暂无任务。可以从上方输入一个目标，或到“演示”页选择任务场景。</div>`;
        return;
    }
    listDiv.innerHTML = taskRuns.map(run => `
        <button class="task-run-item ${run.task_run_id === selectedTaskRunId ? "active" : ""}" onclick="selectTaskRun('${escapeHtml(run.task_run_id)}')">
            <div class="task-run-title">${escapeHtml(summarizeTaskContent(run.content || "任务"))}</div>
            <div class="task-run-meta">
                ${taskStatusPill(run.status)}
                <span>${escapeHtml(run.created_at ? formatTraceTime(run.created_at) : "")}</span>
            </div>
        </button>
    `).join("");
}

async function loadTaskRuns() {
    try {
        const response = await fetch("/task/runs?limit=20", {
            method: "GET",
            headers: {
                ...csrfHeaders()
            }
        });
        const payload = await readJsonResponse(response, "task.runs");
        taskRuns = Array.isArray(payload.runs) ? payload.runs : [];
        renderTaskRunList();
    } catch (error) {
        console.error(error);
        const listDiv = document.getElementById("task-run-list");
        if (listDiv) {
            listDiv.innerText = `任务列表加载失败${error?.message ? `：${error.message}` : ""}`;
        }
    }
}

async function loadTaskTools() {
    const listDiv = document.getElementById("task-tool-list");
    if (!listDiv) return;
    listDiv.innerText = "正在加载工具...";
    try {
        const response = await fetch("/task/tools", {
            method: "GET",
            headers: {
                ...csrfHeaders()
            }
        });
        const payload = await readJsonResponse(response, "task.tools");
        const tools = Array.isArray(payload.tools) ? payload.tools : [];
        const connectors = Array.isArray(payload.connectors) ? payload.connectors : [];
        const summary = payload.summary || {};
        if (!tools.length) {
            listDiv.innerText = "暂无工具";
            return;
        }
        listDiv.innerHTML = `
            ${renderPrivacyNotice(payload.privacy)}
            <div class="task-step-detail">
                Total：${escapeHtml(String(summary.total || tools.length))}
                · Local：${escapeHtml(String(summary.local || 0))}
                · MCP：${escapeHtml(String(summary.mcp || 0))}
                · Confirm：${escapeHtml(String(summary.permission_required || 0))}
                · Connectors：${escapeHtml(String(summary.connectors || connectors.length))}
                · Healthy：${escapeHtml(String(summary.healthy_connectors || 0))}
            </div>
            ${renderTaskConnectors(connectors)}
            ${tools.map(renderTaskToolItem).join("")}
        `;
    } catch (error) {
        console.error(error);
        listDiv.innerText = "工具目录加载失败";
    }
}

function renderPrivacyNotice(privacy) {
    if (!privacy) return "";
    const applied = privacy.redaction_applied !== false;
    const status = applied ? "已默认脱敏" : "正在显示敏感信息";
    const detail = privacy.policy || "默认隐藏本机绝对路径和 secret-like 字段。";
    return `
        <div class="task-block">
            <strong>Privacy Boundary</strong>
            <div class="task-step-detail">${escapeHtml(status)} · ${escapeHtml(detail)}</div>
        </div>
    `;
}

function renderTaskConnectors(connectors) {
    const list = Array.isArray(connectors) ? connectors : [];
    if (!list.length) {
        return "";
    }
    return `
        <div class="task-block">
            <strong>Connector Settings & Health</strong>
            ${list.map(renderTaskConnectorItem).join("")}
        </div>
    `;
}

function renderTaskConnectorItem(connector) {
    const health = connector.health || {};
    const settings = connector.settings || {};
    const roots = Array.isArray(settings.roots) ? settings.roots : [];
    const risk = connector.risk_summary || {};
    const riskLevels = Array.isArray(connector.risk_levels) ? connector.risk_levels.join(", ") : "";
    const tools = Array.isArray(connector.tools) ? connector.tools : [];
    const rootRows = roots.length
        ? roots.map(root => `
            <div class="task-step-detail">
                root=${escapeHtml(root.name || "")}
                · ${escapeHtml(root.path || "")}
                · ${escapeHtml(root.readable ? "readable" : "unavailable")}
            </div>
        `).join("")
        : `<div class="task-step-detail">No configured roots reported.</div>`;
    return `
        <div class="task-step ${health.ok === false ? "fail" : ""}">
            <div class="task-step-title">${escapeHtml(connector.name || connector.server_id || "")}</div>
            <div class="task-step-detail">
                ${escapeHtml(connector.enabled === false ? "disabled" : "enabled")}
                · ${escapeHtml(health.ok === false ? "unhealthy" : "healthy")}
                · tools=${escapeHtml(String(connector.tool_count || tools.length))}
                · risk=${escapeHtml(risk.risk_level || riskLevels || "unknown")}
                · hosted=${escapeHtml(risk.allowed_in_hosted === false ? "blocked" : "allowed")}
            </div>
            <div class="task-step-detail">${escapeHtml(health.message || "")}</div>
            ${rootRows}
            <details>
                <summary>Connector tools</summary>
                <pre>${escapeHtml(JSON.stringify(tools, null, 2))}</pre>
            </details>
        </div>
    `;
}

function renderTaskToolItem(tool) {
    const policy = tool.policy || {};
    const policyMetadata = tool.policy_metadata || {};
    const source = tool.source || "local";
    const health = tool.health || {};
    const required = Array.isArray(tool.required) && tool.required.length
        ? ` · required=${escapeHtml(tool.required.join(", "))}`
        : "";
    const server = tool.server_id ? ` · ${escapeHtml(tool.server_id)}` : "";
    const confirm = policy.requires_confirmation ? " · confirmation required" : "";
    const reason = policyMetadata.policy_reason
        ? `<div class="task-step-detail">Policy：${escapeHtml(policyMetadata.policy_reason)}</div>`
        : "";
    return `
        <div class="task-step">
            <div class="task-step-title">${escapeHtml(tool.name || "")}</div>
            <div class="task-step-detail">
                ${escapeHtml(source.toUpperCase())}${server}
                · risk=${escapeHtml(policy.risk_level || "safe")}
                · ${escapeHtml(health.ok === false ? "unhealthy" : "available")}${confirm}${required}
            </div>
            <div class="task-step-detail">${escapeHtml(tool.description || "")}</div>
            ${reason}
            <details>
                <summary>Schema</summary>
                <pre>${escapeHtml(JSON.stringify(tool.schema || {}, null, 2))}</pre>
            </details>
        </div>
    `;
}

async function selectTaskRun(taskRunId) {
    selectedTaskRunId = taskRunId;
    renderTaskRunList();
    const run = await pollTaskRun(taskRunId, { keepSelection: true });
    if (run && !["succeeded", "failed", "cancelled"].includes(String(run.status || ""))) {
        currentBackgroundTaskRunId = run.task_run_id;
        document.getElementById("task-cancel-btn").disabled = false;
    }
}

function stopTaskPolling() {
    if (taskPollTimer) {
        clearInterval(taskPollTimer);
        taskPollTimer = null;
    }
}

async function pollTaskRun(taskRunId, options = {}) {
    try {
        const response = await fetch(`/task/runs/${encodeURIComponent(taskRunId)}`, {
            method: "GET",
            headers: {
                ...csrfHeaders()
            }
        });
        const run = await readJsonResponse(response, "task.run");
        const existingIndex = taskRuns.findIndex(item => item.task_run_id === run.task_run_id);
        if (existingIndex >= 0) {
            taskRuns[existingIndex] = run;
        } else {
            taskRuns = [run, ...taskRuns].slice(0, 20);
        }
        if (!selectedTaskRunId || options.keepSelection) {
            selectedTaskRunId = run.task_run_id;
        }
        renderTaskRunList();
        showTaskResult(renderTaskRunSnapshot(run));
        const finished = ["succeeded", "failed", "cancelled"].includes(String(run.status || ""));
        if (finished) {
            stopTaskPolling();
            if (currentBackgroundTaskRunId === run.task_run_id) {
                currentBackgroundTaskRunId = null;
            }
            document.getElementById("task-cancel-btn").disabled = true;
            document.getElementById("task-background-btn").disabled = false;
            loadTaskRuns();
        }
        return run;
    } catch (error) {
        console.error(error);
        showTaskResult(taskErrorHtml("后台任务状态刷新失败", error));
        stopTaskPolling();
    }
}

async function startBackgroundTask() {
    if (currentBackgroundTaskRunId) return;

    const input = document.getElementById("task-input");
    const content = input.value.trim();
    if (!content) return;

    const backgroundBtn = document.getElementById("task-background-btn");
    const cancelBtn = document.getElementById("task-cancel-btn");
    backgroundBtn.disabled = true;
    cancelBtn.disabled = true;
    showTaskResult("<p>正在创建后台任务...</p>");

    try {
        const response = await fetch("/task/runs", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...csrfHeaders()
            },
            body: JSON.stringify({ content })
        });
        const run = await readJsonResponse(response, "task.runs.create");
        currentBackgroundTaskRunId = run.task_run_id;
        selectedTaskRunId = run.task_run_id;
        taskRuns = [run, ...taskRuns.filter(item => item.task_run_id !== run.task_run_id)].slice(0, 20);
        renderTaskRunList();
        input.value = "";
        cancelBtn.disabled = false;
        showTaskResult(renderTaskRunSnapshot(run));
        stopTaskPolling();
        taskPollTimer = setInterval(() => {
            if (currentBackgroundTaskRunId) {
                pollTaskRun(currentBackgroundTaskRunId);
            }
        }, 1200);
        await pollTaskRun(currentBackgroundTaskRunId);
    } catch (error) {
        showTaskResult(taskErrorHtml("后台任务创建失败", error));
        backgroundBtn.disabled = false;
        cancelBtn.disabled = true;
        currentBackgroundTaskRunId = null;
        console.error(error);
    }
}

async function cancelBackgroundTask() {
    if (!currentBackgroundTaskRunId) return;
    const taskRunId = currentBackgroundTaskRunId;
    const cancelBtn = document.getElementById("task-cancel-btn");
    cancelBtn.disabled = true;
    try {
        const response = await fetch(`/task/runs/${encodeURIComponent(taskRunId)}/cancel`, {
            method: "POST",
            headers: {
                ...csrfHeaders()
            }
        });
        const run = await readJsonResponse(response, "task.runs.cancel");
        const index = taskRuns.findIndex(item => item.task_run_id === run.task_run_id);
        if (index >= 0) {
            taskRuns[index] = run;
            renderTaskRunList();
        }
        showTaskResult(renderTaskRunSnapshot(run));
        if (["succeeded", "failed", "cancelled"].includes(String(run.status || ""))) {
            stopTaskPolling();
            currentBackgroundTaskRunId = null;
            document.getElementById("task-background-btn").disabled = false;
        }
    } catch (error) {
        cancelBtn.disabled = false;
        alert(`取消后台任务失败${error?.message ? `：${error.message}` : ""}`);
        console.error(error);
    }
}

async function executeTask() {
    if (isTaskProcessing) return;

    const input = document.getElementById("task-input");
    const content = input.value.trim();
    if (!content) return;

    isTaskProcessing = true;
    const executeBtn = document.getElementById("task-execute-btn");
    executeBtn.disabled = true;

    showTaskResult("<p>正在执行...</p>");
    input.value = "";

    try {
        const response = await fetch("/task", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...csrfHeaders()
            },
            body: JSON.stringify({ content: content })
        });

        const taskResp = await readJsonResponse(response, "task.execute");
        let html = "<strong>任务结果：</strong>";
        if (taskResp.task_run_id) {
            html += `<p><strong>Run ID：</strong>${escapeHtml(String(taskResp.task_run_id))}</p>`;
        }
        if (taskResp.status) {
            html += `<p><strong>状态：</strong>${escapeHtml(String(taskResp.status))}</p>`;
        }
        html += `<p><strong>成功状态：</strong>${escapeHtml(String(taskResp.success))}</p>`;
        if (taskResp.reward !== undefined && taskResp.reward !== null) {
            html += `<p><strong>反馈：</strong>${escapeHtml(String(taskResp.reward))}</p>`;
        }
        if (taskResp.latency_ms !== undefined && taskResp.latency_ms !== null) {
            html += `<p><strong>延迟：</strong>${escapeHtml(String(taskResp.latency_ms))} ms</p>`;
        }
        if (taskResp.error) {
            html += `<p><strong>错误：</strong>${escapeHtml(String(taskResp.error))}</p>`;
        }
        html += renderTaskTimeline(taskResp.events);

        if (taskResp.plan) {
            const planSteps = Array.isArray(taskResp.plan.steps) ? taskResp.plan.steps : [];
            html += `<div class="task-block"><strong>任务规划：</strong>`;
            html += `<div class="task-step-detail">来源：${escapeHtml(String(taskResp.plan.source || "none"))}</div>`;
            if (taskResp.plan.rationale) {
                html += `<div class="task-step-detail">解释：${escapeHtml(String(taskResp.plan.rationale))}</div>`;
            }
            if (planSteps.length > 0) {
                html += planSteps.map((step, index) => `
                    <div class="task-step">
                        <div class="task-step-title">步骤 ${index + 1}: ${escapeHtml(step.description || step.tool_name || "Untitled")}</div>
                        <div class="task-step-detail"><strong>工具：</strong>${escapeHtml(step.tool_name || "")}</div>
                        <div class="task-step-detail"><strong>参数：</strong>${escapeHtml(JSON.stringify(step.tool_args || {}, null, 2))}</div>
                    </div>
                `).join("");
            } else if (taskResp.plan.tool_name) {
                html += `
                    <div class="task-step">
                        <div class="task-step-title">单步任务</div>
                        <div class="task-step-detail"><strong>工具：</strong>${escapeHtml(taskResp.plan.tool_name)}</div>
                        <div class="task-step-detail"><strong>参数：</strong>${escapeHtml(JSON.stringify(taskResp.plan.tool_args || {}, null, 2))}</div>
                    </div>
                `;
            }
            html += `</div>`;
        }

        if (taskResp.result) {
            const resultSteps = Array.isArray(taskResp.result.steps) ? taskResp.result.steps : [];
            html += `<div class="task-block"><strong>执行过程</strong>`;
            if (resultSteps.length > 0) {
                html += resultSteps.map((step, index) => `
                    <div class="task-step ${step.result && step.result.success === false ? "fail" : ""}">
                        <div class="task-step-title">步骤 ${index + 1}: ${escapeHtml(step.description || step.tool_name || "Untitled")}</div>
                        <div class="task-step-detail"><strong>工具：</strong>${escapeHtml(step.tool_name || "")}</div>
                        <div class="task-step-detail"><strong>延迟：</strong>${escapeHtml(String(step.latency_ms ?? ""))} ms</div>
                        <div class="task-step-detail"><strong>是否成功：</strong>${escapeHtml(String(step.result?.success))}</div>
                        <div class="task-step-detail"><strong>执行结果：</strong>${escapeHtml(JSON.stringify(step.result?.data ?? step.result, null, 2))}</div>
                        ${step.result?.error ? `<div class="task-step-detail"><strong>Error：</strong>${escapeHtml(String(step.result.error))}</div>` : ""}
                    </div>
                `).join("");
            } else {
                html += `<div class="task-step-detail">${escapeHtml(JSON.stringify(taskResp.result, null, 2))}</div>`;
            }
            if (taskResp.result.summary) {
                html += `<div class="task-block"><strong>具体信息：</strong><div class="task-step-detail">${escapeHtml(String(taskResp.result.summary))}</div></div>`;
            }
            if (taskResp.result.context) {
                html += `<div class="task-block"><strong>上下文：</strong><pre>${escapeHtml(JSON.stringify(taskResp.result.context, null, 2))}</pre></div>`;
            }
            html += `</div>`;
        }

        showTaskResult(html);
        if (taskResp.task_run_id) {
            await pollTaskRun(taskResp.task_run_id, { keepSelection: true });
        } else {
            loadTaskRuns();
        }
    } catch (error) {
        showTaskResult(taskErrorHtml("任务执行错误", error));
        console.error(error);
    } finally {
        isTaskProcessing = false;
        executeBtn.disabled = false;
    }
}
