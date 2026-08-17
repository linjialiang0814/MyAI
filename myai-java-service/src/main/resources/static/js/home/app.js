document.addEventListener("DOMContentLoaded", function () {
    startNewConversation();
    loadConversations();

    document.getElementById("chat-message").addEventListener("keypress", function (e) {
        if (e.key === "Enter") sendChatMessage();
    });
    document.getElementById("memory-write-input").addEventListener("keypress", function (e) {
        if (e.key === "Enter") writeMemory();
    });
    document.getElementById("memory-query-input").addEventListener("keypress", function (e) {
        if (e.key === "Enter") queryMemory();
    });
    document.getElementById("knowledge-query-input").addEventListener("keypress", function (e) {
        if (e.key === "Enter") queryKnowledge();
    });
    document.getElementById("task-input").addEventListener("keypress", function (e) {
        if (e.key === "Enter") executeTask();
    });
});
