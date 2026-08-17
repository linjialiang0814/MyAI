async function writeMemory() {
    if (isMemWriteProcessing) return;

    const input = document.getElementById("memory-write-input");
    const content = input.value.trim();
    if (!content) return;

    isMemWriteProcessing = true;
    const writeBtn = document.getElementById("memory-write-btn");
    writeBtn.disabled = true;

    const resultDiv = document.getElementById("memory-write-result");
    resultDiv.style.display = "block";
    resultDiv.innerText = "正在写入记忆...";
    input.value = "";

    try {
        const response = await fetch("/memory/write", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...csrfHeaders()
            },
            body: JSON.stringify({ content: content })
        });

        const payload = await readJsonResponse(response, "memory.write");
        const results = Array.isArray(payload.results) ? payload.results : [payload];
        const pendingCount = results.filter(item => item?.governance?.review_status === "pending").length;
        const writtenCount = Number(payload.written_count ?? (payload.written ? 1 : 0));
        if (writtenCount > 0 && pendingCount > 0) {
            resultDiv.innerText = `已生成 ${writtenCount} 条候选记忆，其中 ${pendingCount} 条需要确认。`;
        } else if (writtenCount > 0) {
            resultDiv.innerText = `成功写入 ${writtenCount} 条记忆。`;
        } else {
            resultDiv.innerText = `未写入记忆：${payload.reason || "输入未被识别为可长期保存的记忆"}`;
        }
        await loadMemoryProfile();
        if (pendingCount > 0) {
            await loadPendingMemories();
        }
    } catch (error) {
        resultDiv.innerText = "写入记忆时发生错误，请稍后重试。";
        console.error(error);
    } finally {
        isMemWriteProcessing = false;
        writeBtn.disabled = false;
    }
}

async function queryMemory() {
    if (isMemQueryProcessing) return;

    const input = document.getElementById("memory-query-input");
    const query = input.value.trim();
    if (!query) return;

    isMemQueryProcessing = true;
    const queryBtn = document.getElementById("memory-query-btn");
    queryBtn.disabled = true;

    const resultDiv = document.getElementById("memory-query-result");
    resultDiv.style.display = "block";
    resultDiv.innerText = "正在查询...";
    input.value = "";

    try {
        const response = await fetch("/memory/query", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...csrfHeaders()
            },
            body: JSON.stringify({ content: query })
        });

        const payload = await readJsonResponse(response, "memory.query");
        const memories = Array.isArray(payload) ? payload : (Array.isArray(payload.memories) ? payload.memories : []);

        if (memories.length === 0) {
            resultDiv.innerText = "没有记忆被选中。";
        } else {
            resultDiv.innerHTML = `<strong>查询结果：</strong><ul>${memories.map(item => `<li>${escapeHtml(String(item))}</li>`).join("")}</ul>`;
        }
    } catch (error) {
        resultDiv.innerText = "查询记忆发生错误，请稍后重试。";
        console.error(error);
    } finally {
        isMemQueryProcessing = false;
        queryBtn.disabled = false;
    }
}

function memoryTypeLabel(memType) {
    const labels = {
        preference: "Preference",
        fact: "Fact",
        decision: "Decision",
        opinion: "Opinion",
        general: "General"
    };
    return labels[memType] || memType || "General";
}

function formatMemorySourceRef(sourceRef) {
    if (!sourceRef || Object.keys(sourceRef).length === 0) {
        return "";
    }
    return Object.entries(sourceRef)
        .filter(([, value]) => value !== null && value !== undefined && String(value) !== "")
        .map(([key, value]) => `${key}:${value}`)
        .join(", ");
}

function renderMemoryGovernanceMeta(item) {
    const sourceRef = formatMemorySourceRef(item.source_ref || {});
    const confidence = item.confidence === null || item.confidence === undefined
        ? "unknown"
        : Number(item.confidence).toFixed(2);
    const calibratedConfidence = item.calibrated_confidence === null || item.calibrated_confidence === undefined
        ? confidence
        : Number(item.calibrated_confidence).toFixed(2);
    const primary = [
        item.pinned ? "pinned" : "",
        item.retrieval_enabled === false ? "检索关闭" : "可检索",
        item.user_hidden ? "已隐藏" : "可见",
        `review：${item.review_status || "accepted"}`,
        `state：${item.is_current === false ? "history" : "current"}`
    ].filter(Boolean);
    const secondary = [
        `type：${item.mem_type || "general"}`,
        `source：${item.source || "unknown"}`,
        `confidence：${calibratedConfidence}`,
        `sensitivity：${item.sensitivity || "normal"}`
    ];
    if (memoryViewMode !== "audit") {
        return `
            <div class="memory-card-meta">${primary.map(escapeHtml).join(" | ")}</div>
            <div class="memory-card-meta">${secondary.map(escapeHtml).join(" | ")}</div>
        `;
    }
    secondary.push(`importance：${item.importance ?? ""}`);
    secondary.push(`create_at：${item.created_at || ""}`);
    secondary.push(`scope：${item.scope || "global"}`);
    secondary.push(`category：${item.sensitive_category || "none"}`);
    if (item.observed_at) {
        secondary.push(`observed_at：${item.observed_at}`);
    }
    if (item.valid_from || item.valid_to) {
        secondary.push(`valid：${item.valid_from || ""} -> ${item.valid_to || "now"}`);
    }
    if (sourceRef) {
        secondary.push(`ref：${sourceRef}`);
    }
    if (item.extraction_reason) {
        secondary.push(`reason：${item.extraction_reason}`);
    }
    if (item.review_reason) {
        secondary.push(`review_reason：${item.review_reason}`);
    }
    if (item.multi_candidate && item.candidate_index && item.candidate_count) {
        secondary.push(`candidate：${item.candidate_index}/${item.candidate_count}`);
    }
    if (item.edited_before_accept) {
        secondary.push(`edited：${item.last_edited_at || "yes"}`);
    }
    if (item.merged_count) {
        secondary.push(`merged：${item.merged_count} | ${item.last_merge_type || "unknown"} | ${item.last_merge_reason || ""}`);
    }
    if (item.last_merged_at) {
        secondary.push(`last_merged_at：${item.last_merged_at}`);
    }
    if (item.consolidation_summary) {
        secondary.push(`summary：${item.consolidation_kind || "consolidation"} | count=${item.consolidated_count || ""}`);
    }
    if (item.consolidation_policy) {
        secondary.push(`consolidation_policy：${item.consolidation_policy}`);
    }
    if (item.consolidation_evidence_action) {
        secondary.push(`evidence_action：${item.consolidation_evidence_action}`);
    }
    if (item.consolidated_into) {
        secondary.push(`consolidated_into：${item.consolidated_into}`);
    }
    return `
        <div class="memory-card-meta">${primary.map(escapeHtml).join(" | ")}</div>
        <div class="memory-card-meta">${secondary.map(escapeHtml).join(" | ")}</div>
    `;
}

function renderMergeEvents(item) {
    const events = parseJsonMaybe(item.merge_events, []);
    if (!Array.isArray(events) || events.length === 0) {
        return "";
    }
    return `
        <div class="memory-event-list">
            ${events.map((event, index) => `
                <div class="memory-event">
                    <strong>merge event ${index + 1}</strong>
                    <br>type=${escapeHtml(String(event.merge_type ?? event.type ?? ""))}
                    reason=${escapeHtml(String(event.reason ?? ""))}
                    <br>source=${escapeHtml(String(event.source_memory_id ?? event.memory_id ?? ""))}
                    at=${escapeHtml(String(event.merged_at ?? event.at ?? ""))}
                    ${event.content ? `<br>${escapeHtml(String(event.content))}` : ""}
                </div>
            `).join("")}
        </div>
    `;
}

function renderConsolidationEvents(item) {
    const events = parseJsonMaybe(item.consolidation_events, []);
    if (!Array.isArray(events) || events.length === 0) {
        return "";
    }
    return `
        <div class="memory-event-list">
            ${events.map((event, index) => {
                const state = event.is_current === false ? "history" : "current";
                const validFrom = event.valid_from || "";
                const validTo = event.valid_to || "now";
                return `
                    <div class="memory-event consolidation">
                        <strong>evidence ${index + 1}</strong>
                        <br>memory=${escapeHtml(String(event.memory_id || ""))}
                        source=${escapeHtml(String(event.source || "unknown"))}
                        state=${escapeHtml(state)}
                        <br>observed=${escapeHtml(String(event.observed_at || ""))}
                        valid=${escapeHtml(String(validFrom))} -> ${escapeHtml(String(validTo))}
                        ${event.content ? `<br>${escapeHtml(String(event.content))}` : ""}
                    </div>
                `;
            }).join("")}
        </div>
    `;
}

function renderMemoryObservationPanel(item) {
    const sourceRef = formatMemorySourceRef(item.source_ref || {});
    const candidateLabel = item.multi_candidate && item.candidate_index && item.candidate_count
        ? `${item.candidate_index}/${item.candidate_count}`
        : "";
    const governanceGrid = renderKeyValueGrid([
        {label: "Memory ID", value: item.memory_id},
        {label: "Type", value: item.mem_type},
        {label: "Status", value: item.status},
        {label: "Review", value: item.review_status || "accepted"},
        {label: "Review reason", value: item.review_reason},
        {label: "Sensitivity", value: item.sensitivity || "normal"},
        {label: "Sensitive category", value: item.sensitive_category || "none"},
        {label: "Confidence", value: item.confidence === null || item.confidence === undefined ? "" : Number(item.confidence).toFixed(2)},
        {label: "Raw confidence", value: item.raw_confidence === null || item.raw_confidence === undefined ? "" : Number(item.raw_confidence).toFixed(2)},
        {label: "Calibrated confidence", value: item.calibrated_confidence === null || item.calibrated_confidence === undefined ? "" : Number(item.calibrated_confidence).toFixed(2)},
        {label: "Calibration reason", value: item.confidence_calibration_reason},
        {label: "Calibration factors", value: item.confidence_calibration_factors},
        {label: "Importance", value: item.importance},
        {label: "Scope", value: item.scope || "global"},
        {label: "Source", value: item.source || "unknown"},
        {label: "Source ref", value: sourceRef},
        {label: "Extraction reason", value: item.extraction_reason}
    ]);
    const userControlGrid = renderKeyValueGrid([
        {label: "Retrieval enabled", value: item.retrieval_enabled === false ? "no" : "yes"},
        {label: "Pinned", value: item.pinned ? "yes" : ""},
        {label: "Hidden", value: item.user_hidden ? "yes" : ""},
        {label: "Locked", value: item.user_locked ? "yes" : ""},
        {label: "User control reason", value: item.user_control_reason}
    ]);
    const lifecycleGrid = renderKeyValueGrid([
        {label: "State", value: item.is_current === false ? "history" : "current"},
        {label: "Created", value: item.created_at},
        {label: "Observed", value: item.observed_at},
        {label: "Valid from", value: item.valid_from},
        {label: "Valid to", value: item.valid_to || "now"},
        {label: "Last accessed", value: item.last_accessed_at},
        {label: "Access count", value: item.access_count},
        {label: "Edited before accept", value: item.edited_before_accept ? "yes" : ""},
        {label: "Last edited", value: item.last_edited_at},
        {label: "Original content", value: item.original_content}
    ]);
    const batchGrid = renderKeyValueGrid([
        {label: "Candidate", value: candidateLabel},
        {label: "Batch ID", value: item.extraction_batch_id}
    ]);
    const mergeGrid = renderKeyValueGrid([
        {label: "Merged count", value: item.merged_count},
        {label: "Merged from", value: item.merged_from},
        {label: "Last merged", value: item.last_merged_at},
        {label: "Last merge type", value: item.last_merge_type},
        {label: "Last merge reason", value: item.last_merge_reason}
    ]);
    const consolidationGrid = renderKeyValueGrid([
        {label: "Consolidation summary", value: item.consolidation_summary ? "yes" : ""},
        {label: "Consolidation kind", value: item.consolidation_kind},
        {label: "Consolidation policy", value: item.consolidation_policy},
        {label: "Evidence action", value: item.consolidation_evidence_action},
        {label: "Consolidated at", value: item.consolidated_at},
        {label: "Consolidated count", value: item.consolidated_count},
        {label: "Consolidated from", value: item.consolidated_from},
        {label: "Consolidated into", value: item.consolidated_into}
    ]);
    const mergeEvents = renderMergeEvents(item);
    const consolidationEvents = renderConsolidationEvents(item);
    const hasDetails = governanceGrid || userControlGrid || lifecycleGrid || batchGrid || mergeGrid || mergeEvents || consolidationGrid || consolidationEvents;
    if (!hasDetails) {
        return "";
    }
    return `
        <details class="memory-observe-panel">
            <summary>治理与审计详情</summary>
            <div class="memory-observe-body">
                ${governanceGrid}
                ${userControlGrid ? `<div style="height:8px;"></div>${userControlGrid}` : ""}
                ${lifecycleGrid ? `<div style="height:8px;"></div>${lifecycleGrid}` : ""}
                ${batchGrid ? `<div style="height:8px;"></div>${batchGrid}` : ""}
                ${mergeGrid ? `<div style="height:8px;"></div>${mergeGrid}` : ""}
                ${consolidationGrid ? `<div style="height:8px;"></div>${consolidationGrid}` : ""}
                ${mergeEvents}
                ${consolidationEvents}
            </div>
        </details>
    `;
}

function memoryEditElementId(memoryId, field) {
    return `memory-edit-${field}-${String(memoryId || "").replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function selectOption(value, current, label) {
    return `<option value="${escapeHtml(value)}" ${value === current ? "selected" : ""}>${escapeHtml(label)}</option>`;
}

function renderPendingMemoryEditor(item) {
    const memoryId = item.memory_id || "";
    const contentId = memoryEditElementId(memoryId, "content");
    const typeId = memoryEditElementId(memoryId, "type");
    const scopeId = memoryEditElementId(memoryId, "scope");
    const sensitivityId = memoryEditElementId(memoryId, "sensitivity");
    const currentType = item.mem_type || "general";
    const currentScope = item.scope || "global";
    const currentSensitivity = item.sensitivity || "personal";

    return `
        <div class="memory-edit-form">
            <textarea id="${contentId}" aria-label="记忆内容">${escapeHtml(item.content || "")}</textarea>
            <div class="memory-edit-controls">
                <select id="${typeId}" aria-label="记忆类型">
                    ${selectOption("preference", currentType, "Preference")}
                    ${selectOption("fact", currentType, "Fact")}
                    ${selectOption("decision", currentType, "Decision")}
                    ${selectOption("opinion", currentType, "Opinion")}
                    ${selectOption("general", currentType, "General")}
                </select>
                <select id="${scopeId}" aria-label="作用范围">
                    ${selectOption("global", currentScope, "Global")}
                    ${selectOption("conversation", currentScope, "Conversation")}
                </select>
                <select id="${sensitivityId}" aria-label="敏感级别">
                    ${selectOption("normal", currentSensitivity, "Normal")}
                    ${selectOption("personal", currentSensitivity, "Personal")}
                    ${selectOption("sensitive", currentSensitivity, "Sensitive")}
                </select>
            </div>
        </div>
    `;
}

function renderMemoryCard(item, options = {}) {
    const actions = [];
    if (options.showReviewActions) {
        actions.push(`<button class="action-button" onclick="savePendingMemoryEdit('${escapeHtml(item.memory_id)}', false)">保存</button>`);
        actions.push(`<button class="action-button" onclick="savePendingMemoryEdit('${escapeHtml(item.memory_id)}', true)">保存并接受</button>`);
        actions.push(`<button class="action-button" onclick="rejectMemory('${escapeHtml(item.memory_id)}')">拒绝</button>`);
    }
    if (options.showDelete !== false) {
        actions.push(`<button class="action-button" onclick="toggleMemoryRetrieval('${escapeHtml(item.memory_id)}', ${item.retrieval_enabled === false})">${item.retrieval_enabled === false ? "开启检索" : "关闭检索"}</button>`);
        actions.push(`<button class="action-button" onclick="toggleMemoryHidden('${escapeHtml(item.memory_id)}', ${!item.user_hidden})">${item.user_hidden ? "取消隐藏" : "隐藏"}</button>`);
        actions.push(`<button class="action-button" onclick="toggleMemoryPinned('${escapeHtml(item.memory_id)}', ${!item.pinned})">${item.pinned ? "取消置顶" : "置顶"}</button>`);
        actions.push(`<button class="action-button" onclick="toggleMemoryCurrent('${escapeHtml(item.memory_id)}', ${item.is_current === false})">${item.is_current === false ? "恢复当前" : "设为历史"}</button>`);
        actions.push(`<button class="action-button" onclick="deleteMemory('${escapeHtml(item.memory_id)}')">删除</button>`);
    }
    return `
        <div class="memory-card">
            <div class="memory-card-content">${escapeHtml(item.content || "")}</div>
            ${renderMemoryGovernanceMeta(item)}
            ${memoryViewMode === "audit" ? renderMemoryObservationPanel(item) : ""}
            ${options.showReviewActions ? renderPendingMemoryEditor(item) : ""}
            ${actions.length > 0 ? `<div style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">${actions.join("")}</div>` : ""}
        </div>
    `;
}

function setMemoryStateFilter(value) {
    memoryStateFilter = value || "all";
    loadMemoryProfile();
}

function setMemoryConsolidationFilter(value) {
    memoryConsolidationFilter = value || "all";
    loadMemoryProfile();
}

function setMemoryVisibilityFilter(value) {
    memoryVisibilityFilter = value || "visible";
    loadMemoryProfile();
}

function setMemoryViewMode(value) {
    memoryViewMode = value || "simple";
    loadMemoryProfile();
}

function applyMemorySettings(settings) {
    const normalized = settings || {};
    const memoryEnabled = document.getElementById("memory-enabled-setting");
    const autoWriteEnabled = document.getElementById("auto-write-enabled-setting");
    const sensitiveConfirmation = document.getElementById("sensitive-confirmation-setting");
    const defaultMemoryView = document.getElementById("default-memory-view-setting");
    const memoryViewModeSelect = document.getElementById("memory-view-mode");

    if (memoryEnabled) {
        memoryEnabled.checked = normalized.memory_enabled !== false;
    }
    if (autoWriteEnabled) {
        autoWriteEnabled.checked = normalized.auto_write_enabled !== false;
    }
    if (sensitiveConfirmation) {
        sensitiveConfirmation.checked = normalized.sensitive_requires_confirmation !== false;
    }
    if (defaultMemoryView) {
        defaultMemoryView.value = normalized.default_memory_view === "audit" ? "audit" : "simple";
        memoryViewMode = defaultMemoryView.value;
    }
    if (memoryViewModeSelect) {
        memoryViewModeSelect.value = memoryViewMode;
    }
}

async function loadMemorySettings() {
    if (isMemorySettingsProcessing) return;

    isMemorySettingsProcessing = true;
    const resultDiv = document.getElementById("memory-settings-result");
    if (resultDiv) {
        resultDiv.style.display = "block";
        resultDiv.innerText = "正在加载记忆设置...";
    }

    try {
        const response = await fetch("/memory/settings", {
            method: "GET",
            headers: {
                ...csrfHeaders()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        applyMemorySettings(payload.settings);
        if (resultDiv) {
            resultDiv.innerText = "记忆设置已加载。";
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.innerText = "加载记忆设置失败，请稍后重试。";
        }
        console.error(error);
    } finally {
        isMemorySettingsProcessing = false;
    }
}

async function saveMemorySettings() {
    if (isMemorySettingsProcessing) return;

    const resultDiv = document.getElementById("memory-settings-result");
    const payload = {
        memory_enabled: document.getElementById("memory-enabled-setting")?.checked === true,
        auto_write_enabled: document.getElementById("auto-write-enabled-setting")?.checked === true,
        sensitive_requires_confirmation: document.getElementById("sensitive-confirmation-setting")?.checked === true,
        default_memory_view: document.getElementById("default-memory-view-setting")?.value || "simple"
    };

    isMemorySettingsProcessing = true;
    if (resultDiv) {
        resultDiv.style.display = "block";
        resultDiv.innerText = "正在保存记忆设置...";
    }

    try {
        const response = await fetch("/memory/settings", {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                ...csrfHeaders()
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const updated = await response.json();
        applyMemorySettings(updated.settings);
        if (resultDiv) {
            resultDiv.innerText = "记忆设置已保存。";
        }
        if (document.getElementById("memory-section").classList.contains("active")) {
            await loadMemoryProfile();
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.innerText = "保存记忆设置失败，请稍后重试。";
        }
        console.error(error);
    } finally {
        isMemorySettingsProcessing = false;
    }
}

function filterMemoriesByState(list) {
    let filtered = list;
    if (memoryStateFilter === "current") {
        filtered = filtered.filter(item => item.is_current !== false);
    } else if (memoryStateFilter === "history") {
        filtered = filtered.filter(item => item.is_current === false);
    }
    if (memoryConsolidationFilter === "summary") {
        filtered = filtered.filter(item => item.consolidation_summary);
    } else if (memoryConsolidationFilter === "evidence") {
        filtered = filtered.filter(item => item.consolidated_into && !item.consolidation_summary);
    } else if (memoryConsolidationFilter === "raw") {
        filtered = filtered.filter(item => !item.consolidation_summary && !item.consolidated_into);
    }
    if (memoryVisibilityFilter === "visible") {
        return filtered.filter(item => !item.user_hidden);
    }
    if (memoryVisibilityFilter === "hidden") {
        return filtered.filter(item => item.user_hidden);
    }
    return filtered;
}

async function loadMemoryProfile() {
    if (isMemoryProfileProcessing) return;

    isMemoryProfileProcessing = true;
    const resultDiv = document.getElementById("memory-profile-result");
    resultDiv.style.display = "block";
    resultDiv.innerText = "正在加载记忆画像...";

    try {
        const response = await fetch("/memory/list", {
            method: "GET",
            headers: {
                ...csrfHeaders()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const memories = await response.json();
        const allMemories = Array.isArray(memories) ? memories : [];
        const list = filterMemoriesByState(allMemories);
        if (allMemories.length === 0) {
            resultDiv.innerText = "还没有记忆。";
            return;
        }
        if (list.length === 0) {
            resultDiv.innerText = "当前筛选条件下没有记忆。";
            return;
        }

        const groups = {
            preference: [],
            fact: [],
            decision: [],
            opinion: [],
            general: []
        };
        list.forEach(item => {
            const key = groups[item.mem_type] ? item.mem_type : "general";
            groups[key].push(item);
        });

        resultDiv.innerHTML = `
            <div class="memory-profile-grid">
                ${Object.entries(groups).map(([memType, items]) => `
                    <div class="memory-group">
                        <h4>${escapeHtml(memoryTypeLabel(memType))}</h4>
                        ${items.length === 0
                            ? `<div class="memory-card-meta">no memory</div>`
                            : items.map(item => renderMemoryCard(item)).join("")}
                    </div>
                `).join("")}
            </div>
        `;
    } catch (error) {
        resultDiv.innerText = "加载记忆画像错误，请稍后重试。";
        console.error(error);
    } finally {
        isMemoryProfileProcessing = false;
    }
}

async function deleteMemory(memoryId) {
    try {
        const response = await fetch(`/memory/${encodeURIComponent(memoryId)}`, {
            method: "DELETE",
            headers: {
                ...csrfHeaders()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        await loadMemoryProfile();
    } catch (error) {
        alert("删除时发生错误，请稍后重试。");
        console.error(error);
    }
}

async function updateMemoryControl(memoryId, patch) {
    try {
        const response = await fetch(`/memory/${encodeURIComponent(memoryId)}`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                ...csrfHeaders()
            },
            body: JSON.stringify(patch)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        await loadMemoryProfile();
        await loadPendingMemories();
    } catch (error) {
        alert("更新记忆控制失败，请稍后重试。");
        console.error(error);
    }
}

function toggleMemoryRetrieval(memoryId, enabled) {
    updateMemoryControl(memoryId, {
        retrieval_enabled: enabled,
        user_control_reason: enabled ? "retrieval enabled by user" : "retrieval disabled by user"
    });
}

function toggleMemoryHidden(memoryId, hidden) {
    updateMemoryControl(memoryId, {
        user_hidden: hidden,
        user_control_reason: hidden ? "hidden by user" : "unhidden by user"
    });
}

function toggleMemoryPinned(memoryId, pinned) {
    updateMemoryControl(memoryId, {
        pinned,
        user_control_reason: pinned ? "pinned by user" : "unpinned by user"
    });
}

function toggleMemoryCurrent(memoryId, current) {
    updateMemoryControl(memoryId, {
        is_current: current,
        retrieval_enabled: current,
        user_control_reason: current ? "restored as current by user" : "marked historical by user"
    });
}

async function loadPendingMemories() {
    const resultDiv = document.getElementById("memory-pending-result");
    resultDiv.style.display = "block";
    resultDiv.innerText = "正在加载待确认记忆...";

    try {
        const response = await fetch("/memory/pending", {
            method: "GET",
            headers: {
                ...csrfHeaders()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const memories = await response.json();
        const list = Array.isArray(memories) ? memories : [];
        if (list.length === 0) {
            resultDiv.innerText = "暂无待确认记忆。";
            return;
        }

        resultDiv.innerHTML = list.map(item => renderMemoryCard(item, {
            showReviewActions: true,
            showDelete: false
        })).join("");
    } catch (error) {
        resultDiv.innerText = "加载待确认记忆错误，请稍后重试。";
        console.error(error);
    }
}

async function reviewMemory(memoryId, action) {
    try {
        const response = await fetch(`/memory/${encodeURIComponent(memoryId)}/${action}`, {
            method: "POST",
            headers: {
                ...csrfHeaders()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        await loadPendingMemories();
        await loadMemoryProfile();
    } catch (error) {
        alert("更新记忆状态失败，请稍后重试。");
        console.error(error);
    }
}

function acceptMemory(memoryId) {
    reviewMemory(memoryId, "accept");
}

function rejectMemory(memoryId) {
    reviewMemory(memoryId, "reject");
}

async function savePendingMemoryEdit(memoryId, acceptAfterSave) {
    const content = document.getElementById(memoryEditElementId(memoryId, "content"))?.value || "";
    const memType = document.getElementById(memoryEditElementId(memoryId, "type"))?.value || "general";
    const scope = document.getElementById(memoryEditElementId(memoryId, "scope"))?.value || "global";
    const sensitivity = document.getElementById(memoryEditElementId(memoryId, "sensitivity"))?.value || "personal";

    try {
        const response = await fetch(`/memory/${encodeURIComponent(memoryId)}`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                ...csrfHeaders()
            },
            body: JSON.stringify({
                content,
                mem_type: memType,
                scope,
                sensitivity
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const updated = await response.json();
        if (acceptAfterSave) {
            if (updated.review_status === "rejected") {
                alert("该记忆包含高风险敏感信息，不能接受。");
                await loadPendingMemories();
                await loadMemoryProfile();
                return;
            }
            await reviewMemory(memoryId, "accept");
            return;
        }

        await loadPendingMemories();
        await loadMemoryProfile();
    } catch (error) {
        alert("保存记忆编辑失败，请稍后重试。");
        console.error(error);
    }
}
