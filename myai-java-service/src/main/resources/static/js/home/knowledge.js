async function uploadKnowledge() {
    if (isKnowledgeUploadProcessing) return;

    const fileInput = document.getElementById("knowledge-file-input");
    const file = fileInput.files[0];
    if (!file) return;

    isKnowledgeUploadProcessing = true;
    const uploadBtn = document.getElementById("knowledge-upload-btn");
    uploadBtn.disabled = true;

    const resultDiv = document.getElementById("knowledge-upload-result");
    resultDiv.style.display = "block";
    resultDiv.innerText = "Uploading...";

    try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch("/knowledge/upload", {
            method: "POST",
            headers: {
                ...csrfHeaders()
            },
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        const report = payload.ingestion_report || {};
        const status = report.status || payload.ingestion_status || "indexed";
        const warnings = Array.isArray(report.warnings) && report.warnings.length
            ? `<div>Warnings：${escapeHtml(report.warnings.join("; "))}</div>`
            : "";
        resultDiv.innerHTML = `
            <strong>${status === "duplicate" ? "Duplicate：" : "Uploaded："}</strong>${escapeHtml(payload.file_name)}
            <div>Status：${escapeHtml(status)}</div>
            <div>Chunks：${escapeHtml(String(payload.chunk_count || 0))}</div>
            <div>Size：${escapeHtml(String(payload.size_bytes || 0))} bytes</div>
            <div>Summary：${escapeHtml(payload.summary || "no summary")}</div>
            ${renderKnowledgeProfile(payload.document_profile || {})}
            ${warnings}
        `;
        fileInput.value = "";
        await loadKnowledgeFiles();
    } catch (error) {
        resultDiv.innerText = "上传时发生错误，请检查您的文件。";
        console.error(error);
    } finally {
        isKnowledgeUploadProcessing = false;
        uploadBtn.disabled = false;
    }
}

async function loadKnowledgeFiles() {
    const listDiv = document.getElementById("knowledge-file-list");
    const filterSelect = document.getElementById("knowledge-file-filter");
    listDiv.innerText = "正在加载...";

    try {
        const response = await fetch("/knowledge/files", {
            method: "GET",
            headers: {
                ...csrfHeaders()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const files = await response.json();
        filterSelect.innerHTML = '<option value="">全部文件：</option>';
        if (!Array.isArray(files) || files.length === 0) {
            listDiv.innerText = "这里没有文件。";
            return;
        }

        files.forEach(file => {
            const option = document.createElement("option");
            option.value = file.file_id;
            option.textContent = file.file_name;
            filterSelect.appendChild(option);
        });

        listDiv.innerHTML = files.map(file => {
            const profile = file.document_profile || {};
            const keywords = Array.isArray(profile.keywords) && profile.keywords.length
                ? ` | Keywords：${escapeHtml(profile.keywords.slice(0, 5).join(", "))}`
                : "";
            return `
                <div class="knowledge-file">
                    <div class="knowledge-file-meta">
                        <div class="knowledge-file-name">${escapeHtml(file.file_name)}</div>
                        <div class="knowledge-file-detail">
                            Type：${escapeHtml(file.file_type)} | Chunks：${escapeHtml(String(file.chunk_count))} | Time：${escapeHtml(file.uploaded_at)}
                        </div>
                        <div class="knowledge-file-detail">
                            Status：${escapeHtml(file.ingestion_status || "indexed")} | Size：${escapeHtml(String(file.size_bytes || 0))} bytes${keywords}
                        </div>
                        <div class="knowledge-file-detail">Summary：${escapeHtml(file.summary || "No summary")}</div>
                        ${renderKnowledgeProfile(profile)}
                    </div>
                    <div>
                        <button class="action-button" onclick="deleteKnowledgeFile('${escapeHtml(file.file_id)}')">删除</button>
                    </div>
                </div>
            `;
        }).join("");
    } catch (error) {
        listDiv.innerText = "加载文件失败。";
        console.error(error);
    }
}

function renderKnowledgeProfile(profile) {
    if (!profile || Object.keys(profile).length === 0) {
        return "";
    }
    const outline = Array.isArray(profile.outline) ? profile.outline : [];
    const passages = Array.isArray(profile.important_passages) ? profile.important_passages : [];
    const questions = Array.isArray(profile.possible_questions) ? profile.possible_questions : [];
    const keywords = Array.isArray(profile.keywords) ? profile.keywords : [];
    const stats = profile.stats || {};
    return `
        <details class="trace-panel" style="margin-top: 8px;">
            <summary>Document profile</summary>
            <div class="knowledge-file-detail">Language：${escapeHtml(profile.document_language || "unknown")} | Method：${escapeHtml(profile.summary_method || "")}</div>
            ${keywords.length ? `<div class="knowledge-file-detail">Keywords：${escapeHtml(keywords.join(", "))}</div>` : ""}
            ${outline.length ? `<div class="knowledge-file-detail">Outline：${outline.map(item => escapeHtml(item.title || "")).join(" / ")}</div>` : ""}
            ${passages.length ? `<div class="knowledge-file-detail">Passages：${passages.map(item => escapeHtml(item)).join(" / ")}</div>` : ""}
            ${questions.length ? `<div class="knowledge-file-detail">Questions：${questions.map(item => escapeHtml(item)).join(" / ")}</div>` : ""}
            <div class="knowledge-file-detail">Stats：chars=${escapeHtml(String(stats.character_count || 0))} · paragraphs=${escapeHtml(String(stats.paragraph_count || 0))} · sentences=${escapeHtml(String(stats.sentence_count || 0))}</div>
        </details>
    `;
}

async function deleteKnowledgeFile(fileId) {
    try {
        const response = await fetch(`/knowledge/files/${encodeURIComponent(fileId)}`, {
            method: "DELETE",
            headers: {
                ...csrfHeaders()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        await loadKnowledgeFiles();
    } catch (error) {
        alert("删除时发生错误，请稍后重试。");
        console.error(error);
    }
}

async function runKnowledgeMaintenance(dryRun, rebuild) {
    if (isKnowledgeMaintenanceProcessing) return;

    const fileFilter = document.getElementById("knowledge-file-filter");
    const resultDiv = document.getElementById("knowledge-maintenance-result");
    const checkBtn = document.getElementById("knowledge-maintenance-check-btn");
    const repairBtn = document.getElementById("knowledge-maintenance-repair-btn");
    const rebuildBtn = document.getElementById("knowledge-maintenance-rebuild-btn");
    const selectedFileId = fileFilter.value || null;
    if (rebuild && !selectedFileId) {
        resultDiv.style.display = "block";
        resultDiv.innerText = "请先选择一个文件，再重建所选文件。";
        return;
    }

    isKnowledgeMaintenanceProcessing = true;
    checkBtn.disabled = true;
    repairBtn.disabled = true;
    rebuildBtn.disabled = true;
    resultDiv.style.display = "block";
    resultDiv.innerText = dryRun ? "正在检查知识库..." : "正在维护知识库...";

    try {
        const response = await fetch("/knowledge/maintenance", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...csrfHeaders()
            },
            body: JSON.stringify({
                dry_run: dryRun,
                rebuild: rebuild,
                file_id: selectedFileId
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        resultDiv.innerHTML = renderKnowledgeMaintenanceReport(payload);
        if (!dryRun) {
            await loadKnowledgeFiles();
        }
    } catch (error) {
        resultDiv.innerText = "知识库维护失败，请稍后重试。";
        console.error(error);
    } finally {
        isKnowledgeMaintenanceProcessing = false;
        checkBtn.disabled = false;
        repairBtn.disabled = false;
        rebuildBtn.disabled = false;
    }
}

function renderKnowledgeMaintenanceReport(report) {
    const summary = report.summary || {};
    const files = Array.isArray(report.files) ? report.files : [];
    const actions = Array.isArray(report.actions) ? report.actions : [];
    const duplicates = Array.isArray(report.duplicate_groups) ? report.duplicate_groups : [];
    const fileRows = files.length
        ? files.map(file => `
            <div class="knowledge-hit">
                <div><strong>${escapeHtml(file.file_name || file.file_id || "file")}</strong></div>
                <div>Status：${escapeHtml(file.health || "")} | Stored：${escapeHtml(file.stored_file_status || "")}</div>
                <div>Chunks：${escapeHtml(String(file.actual_chunk_count || 0))}/${escapeHtml(String(file.expected_chunk_count || 0))}</div>
                <div>Action：${escapeHtml(file.action || "none")}</div>
                ${(file.missing_chunk_ids || []).length ? `<div>Missing：${escapeHtml(file.missing_chunk_ids.join(", "))}</div>` : ""}
            </div>
        `).join("")
        : `<div class="knowledge-file-detail">没有需要检查的文件。</div>`;
    const actionRows = actions.length
        ? `<details style="margin-top: 8px;"><summary>维护动作</summary>${actions.map(action => `
            <div class="knowledge-file-detail">
                ${escapeHtml(action.type || "")} · ${escapeHtml(action.status || "")} · count=${escapeHtml(String(action.count || (action.missing_chunk_ids || []).length || 0))}
            </div>
        `).join("")}</details>`
        : "";
    const duplicateRows = duplicates.length
        ? `<details style="margin-top: 8px;"><summary>重复文件</summary>${duplicates.map(group => `
            <div class="knowledge-file-detail">
                ${escapeHtml((group.file_names || []).join(", "))} · count=${escapeHtml(String(group.count || 0))}
            </div>
        `).join("")}</details>`
        : "";
    return `
        <div><strong>Maintenance：</strong>${escapeHtml(report.status || "")}</div>
        <div>Mode：${report.dry_run ? "dry-run" : "apply"}${report.rebuild ? " · rebuild" : ""}</div>
        <div>Checked：${escapeHtml(formatTraceTime(report.checked_at || ""))}</div>
        <div>
            Files：${escapeHtml(String(summary.files_checked || 0))}
            · Missing chunks：${escapeHtml(String(summary.missing_chunks || 0))}
            · Orphans：${escapeHtml(String(summary.orphan_chunks || 0))}
            · Deleted：${escapeHtml(String(summary.orphan_chunks_deleted || 0))}
            · Duplicates：${escapeHtml(String(summary.duplicate_groups || 0))}
        </div>
        ${actionRows}
        ${duplicateRows}
        <div style="margin-top: 8px;">${fileRows}</div>
    `;
}

async function queryKnowledge() {
    if (isKnowledgeQueryProcessing) return;

    const input = document.getElementById("knowledge-query-input");
    const fileFilter = document.getElementById("knowledge-file-filter");
    const query = input.value.trim();
    if (!query) return;

    isKnowledgeQueryProcessing = true;
    const queryBtn = document.getElementById("knowledge-query-btn");
    queryBtn.disabled = true;

    const resultDiv = document.getElementById("knowledge-query-result");
    resultDiv.style.display = "block";
    resultDiv.innerText = "正在查询...";

    try {
        const response = await fetch("/knowledge/query", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...csrfHeaders()
            },
            body: JSON.stringify({ query: query, top_k: 3, file_id: fileFilter.value || null })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        const hits = Array.isArray(payload.hits) ? payload.hits : [];

        if (hits.length === 0) {
            resultDiv.innerText = "没有发现匹配的知识。";
        } else {
            resultDiv.innerHTML = hits.map(renderKnowledgeHit).join("");
        }
    } catch (error) {
        resultDiv.innerText = "查询时发生错误，请稍后重试。";
        console.error(error);
    } finally {
        isKnowledgeQueryProcessing = false;
        queryBtn.disabled = false;
    }
}

async function askKnowledgeDocument() {
    if (isKnowledgeQueryProcessing) return;

    const input = document.getElementById("knowledge-query-input");
    const fileFilter = document.getElementById("knowledge-file-filter");
    const question = input.value.trim();
    if (!question) return;
    if (!fileFilter.value) {
        const resultDiv = document.getElementById("knowledge-query-result");
        resultDiv.style.display = "block";
        resultDiv.innerText = "请先选择一个文件，再进行文档问答。";
        return;
    }

    isKnowledgeQueryProcessing = true;
    const queryBtn = document.getElementById("knowledge-query-btn");
    const qaBtn = document.getElementById("knowledge-qa-btn");
    queryBtn.disabled = true;
    qaBtn.disabled = true;

    const resultDiv = document.getElementById("knowledge-query-result");
    resultDiv.style.display = "block";
    resultDiv.innerText = "正在基于所选文档回答...";

    try {
        const response = await fetch("/knowledge/qa", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...csrfHeaders()
            },
            body: JSON.stringify({ question: question, top_k: 3, file_id: fileFilter.value })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        const hits = Array.isArray(payload.hits) ? payload.hits : [];
        resultDiv.innerHTML = `
            <div class="knowledge-hit">
                <div><strong>Document：</strong>${escapeHtml(payload.file_name || "")}</div>
                <div><strong>Status：</strong>${escapeHtml(payload.answer_status || "")} | Evidence：${escapeHtml(String(payload.evidence_count || 0))}</div>
                <div style="margin-top: 8px;">${escapeHtml(payload.answer || "")}</div>
            </div>
            ${hits.length ? hits.map(renderKnowledgeHit).join("") : ""}
        `;
    } catch (error) {
        resultDiv.innerText = "文档问答时发生错误，请稍后重试。";
        console.error(error);
    } finally {
        isKnowledgeQueryProcessing = false;
        queryBtn.disabled = false;
        qaBtn.disabled = false;
    }
}

function renderKnowledgeHit(hit) {
    const citation = hit.citation || {};
    const citationId = citation.citation_id || hit.citation_id || hit.chunk_id || "";
    const chunkIndex = citation.chunk_index ?? hit.chunk_index ?? "";
    const pageStart = citation.page_start || hit.page_start || "";
    const pageEnd = citation.page_end || hit.page_end || "";
    const pageLabel = pageStart && pageEnd && pageStart !== pageEnd
        ? ` · p.${pageStart}-${pageEnd}`
        : (pageStart ? ` · p.${pageStart}` : "");
    const sourceLabel = `${hit.file_name || citation.file_name || ""} · chunk ${chunkIndex}${pageLabel}`;
    const snippet = hit.snippet || citation.snippet || hit.content || "";
    const explanation = hit.retrieval_explanation || {};
    const selection = hit.selection_explanation || {};
    const retrievalScore = hit.retrieval_score ?? explanation.retrieval_score ?? hit.score ?? citation.score ?? "";
    const rerankScore = hit.rerank_score ?? selection.rerank_score ?? "";
    const factors = [
        `mode=${hit.retrieval_mode || explanation.mode || "unknown"}`,
        `vector=${compactNumber(hit.vector_score ?? explanation.vector_score ?? 0)}`,
        `keyword=${compactNumber(hit.keyword_score ?? explanation.keyword_score ?? 0)}`,
        `filename=${compactNumber(hit.filename_score ?? explanation.filename_score ?? 0)}`,
        `fresh=${compactNumber(hit.recency_score ?? explanation.recency_score ?? 0)}`,
        `coverage=${compactNumber(hit.query_coverage ?? selection.query_coverage ?? 0)}`,
        `len=${compactNumber(hit.length_quality ?? selection.length_quality ?? 0)}`
    ].join(" · ");
    return `
        <div class="knowledge-hit">
            <div><strong>Citation：</strong>${escapeHtml(citationId)}</div>
            <div><strong>Source：</strong>${escapeHtml(sourceLabel)}</div>
            <div><strong>Rank：</strong>${escapeHtml(String(hit.final_rank || ""))} / candidate ${escapeHtml(String(hit.candidate_rank || ""))}</div>
            <div><strong>Retrieval：</strong>${escapeHtml(String(retrievalScore))}</div>
            <div><strong>Rerank：</strong>${escapeHtml(String(rerankScore))}</div>
            <div><strong>Factors：</strong>${escapeHtml(factors)}</div>
            ${explanation.reason ? `<div><strong>Reason：</strong>${escapeHtml(explanation.reason)}</div>` : ""}
            ${hit.selection_reason ? `<div><strong>Selection：</strong>${escapeHtml(hit.selection_reason)}</div>` : ""}
            <div style="margin-top: 8px;">${escapeHtml(snippet)}</div>
            <details style="margin-top: 8px;">
                <summary>查看原始片段</summary>
                <div style="margin-top: 6px;">${escapeHtml(hit.content || "")}</div>
            </details>
        </div>
    `;
}
