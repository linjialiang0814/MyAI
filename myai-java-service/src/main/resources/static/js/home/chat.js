function appendReply(text, trace = null) {
    const box = document.getElementById("chat-box");
    removeChatEmptyState();
    const div = document.createElement("div");
    div.className = "message assistant-message";
    const chips = trace && Array.isArray(trace.steps)
        ? `<div class="message-actions">
            <span class="message-chip">${escapeHtml(String(trace.steps.length))} steps</span>
            <span class="message-chip">${escapeHtml(trace.status || "trace")}</span>
        </div>`
        : "";
    div.innerHTML = `<div class="message-label">MyAI</div><div class="reply">${escapeHtml(text)}</div>${chips}${renderTracePanel(trace)}`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    if (trace) {
        latestAgentTrace = trace;
        updateAgentContextPanel(trace);
        setAgentStatus(trace.status === "failed" ? "error" : "ready", trace.status === "failed" ? "本轮执行完成，但存在失败步骤。" : "本轮回答完成，右侧已更新执行摘要。");
    }
}

function createPendingReply() {
    const box = document.getElementById("chat-box");
    removeChatEmptyState();
    const wrapper = document.createElement("div");
    wrapper.className = "message assistant-message";
    const label = document.createElement("div");
    label.className = "message-label";
    label.innerText = "MyAI";
    const reply = document.createElement("div");
    reply.className = "reply pending";
    wrapper.appendChild(label);
    wrapper.appendChild(reply);
    box.appendChild(wrapper);
    box.scrollTop = box.scrollHeight;
    return { wrapper, reply };
}

function startChatStatusRotation(target) {
    const stages = [
        "MyAI正在分析问题",
        "MyAI正在思考",
        "MyAI正在整理上下文",
        "MyAI正在回忆相关信息",
        "MyAI正在组织答案"
    ];
    let stageIndex = 0;
    let dotCount = 0;

    const render = () => {
        const dots = ".".repeat(dotCount + 1);
        target.textContent = `${stages[stageIndex]}${dots}`;
    };

    render();

    const dotTimer = window.setInterval(() => {
        dotCount = (dotCount + 1) % 3;
        render();
    }, 360);

    const stageTimer = window.setInterval(() => {
        if (stageIndex < stages.length - 1) {
            stageIndex += 1;
            render();
            return;
        }
        window.clearInterval(stageTimer);
    }, 1400);

    return {
        stop() {
            window.clearInterval(dotTimer);
            window.clearInterval(stageTimer);
        }
    };
}

function clearChatBox() {
    document.getElementById("chat-box").innerHTML = "";
}

function renderConversationMessages(messages) {
    clearChatBox();
    if (!Array.isArray(messages) || messages.length === 0) {
        ensureChatEmptyState();
        updateAgentContextPanel(null, {emptyText: "这是一个新的对话。发送消息后，我会在这里整理本轮执行摘要。"});
        return;
    }
    messages.forEach(item => {
        if (item.role === "user") {
            appendUserMessage(item.content || "");
        } else {
            appendReply(item.content || "");
        }
    });
    updateAgentContextPanel(null, {emptyText: "历史消息已加载。新的回复会刷新本轮 trace、记忆、知识和任务摘要。"});
}

async function loadConversations() {
    const listDiv = document.getElementById("conversation-list");
    listDiv.innerText = "正在加载...";

    try {
        const response = await fetch("/conversations", {
            method: "GET",
            headers: {
                ...csrfHeaders()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const conversations = await response.json();
        if (!Array.isArray(conversations) || conversations.length === 0) {
            listDiv.innerText = "还没有对话。";
            return;
        }

        listDiv.innerHTML = conversations.map(item => `
            <div class="conversation-item ${item.id === currentConversationId ? "active" : ""}" onclick="loadConversation(${item.id})">
                <div class="conversation-title">${escapeHtml(item.title || "Untitled")}</div>
                <div class="conversation-meta">Update time：${escapeHtml(item.updated_at || "")}</div>
                <div class="conversation-preview">${escapeHtml(item.last_message_preview || "")}</div>
                <div class="conversation-actions">
                    <button class="conversation-delete" onclick="deleteConversation(event, ${item.id})">删除</button>
                </div>
            </div>
        `).join("");
    } catch (error) {
        listDiv.innerText = "加载对话失败。";
        console.error(error);
    }
}

async function loadConversation(conversationId) {
    try {
        const response = await fetch(`/conversations/${conversationId}`, {
            method: "GET",
            headers: {
                ...csrfHeaders()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const detail = await response.json();
        currentConversationId = detail.id;
        document.getElementById("current-conversation-title").innerText = `当前对话：${detail.title || "untitled"}`;
        renderConversationMessages(detail.messages || []);
        setAgentStatus("ready", "历史对话已加载，可以继续追问或开启新任务。");
        await loadConversations();
    } catch (error) {
        console.error(error);
        alert("加载失败，请稍后重试。");
    }
}

function startNewConversation() {
    currentConversationId = null;
    document.getElementById("current-conversation-title").innerText = "当前对话：新对话";
    clearChatBox();
    latestAgentTrace = null;
    ensureChatEmptyState();
    updateAgentContextPanel(null, {emptyText: "新的对话已准备好。你可以从建议开始，也可以直接输入问题。"});
    setAgentStatus("ready", "准备就绪，可以开始新的对话。");
    loadConversations();
}

function exportCurrentConversation() {
    if (!currentConversationId) {
        alert("没有可导出的对话。");
        return;
    }
    window.location.href = `/conversations/${currentConversationId}/export`;
}

async function deleteConversation(event, conversationId) {
    event.stopPropagation();
    if (!confirm("确认删除这个对话？")) {
        return;
    }

    try {
        const response = await fetch(`/conversations/${conversationId}`, {
            method: "DELETE",
            headers: {
                ...csrfHeaders()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        if (currentConversationId === conversationId) {
            startNewConversation();
            return;
        }
        await loadConversations();
    } catch (error) {
        console.error(error);
        alert("删除失败，请稍后重试。");
    }
}

async function sendChatMessage() {
    if (isChatProcessing) return;

    const input = document.getElementById("chat-message");
    const text = input.value.trim();
    if (!text) return;

    isChatProcessing = true;
    const sendBtn = document.getElementById("chat-send-btn");
    sendBtn.disabled = true;
    input.disabled = true;

    setAgentStatus("busy", "正在分析本轮输入，并准备检索记忆、知识或任务能力。");
    updateAgentContextPanel(null, {emptyText: "MyAI 正在执行本轮对话，完成后会显示 trace 摘要。"});
    appendUserMessage(text);
    input.value = "";
    const pending = createPendingReply();
    chatStatusController = startChatStatusRotation(pending.reply);
    const idempotencyKey = (window.crypto && typeof window.crypto.randomUUID === "function")
        ? window.crypto.randomUUID()
        : `chat-${Date.now()}-${Math.random().toString(16).slice(2)}`;

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Idempotency-Key": idempotencyKey,
                ...csrfHeaders()
            },
            body: JSON.stringify({
                message: text,
                conversation_id: currentConversationId,
                idempotency_key: idempotencyKey
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        currentConversationId = payload.conversation_id ?? currentConversationId;
        if (currentConversationId) {
            const nextTitle = text.length > 24 ? `${text.slice(0, 24)}...` : text;
            document.getElementById("current-conversation-title").innerText = `当前对话：${nextTitle}`;
        }
        if (currentConversationId) {
            await loadConversations();
        }
        pending.wrapper.remove();
        appendReply(payload.reply || "", payload.trace || null);
    } catch (error) {
        pending.wrapper.remove();
        appendReply("System error, please check the backend service.");
        setAgentStatus("error", "本轮请求失败，请检查 Java/Python 服务状态。");
        updateAgentContextPanel(null, {emptyText: "请求失败，暂时没有可展示的执行摘要。"});
        console.error(error);
    } finally {
        if (chatStatusController) {
            chatStatusController.stop();
            chatStatusController = null;
        }
        isChatProcessing = false;
        sendBtn.disabled = false;
        input.disabled = false;
        input.focus();
    }
}
