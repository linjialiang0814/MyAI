package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class ChatRequest {
    @JsonProperty("user_id")
    private String userId;
    private String message;
    @JsonProperty("conversation_id")
    private Long conversationId;
    @JsonProperty("idempotency_key")
    private String idempotencyKey;
    private java.util.List<ChatHistoryMessage> history;

    public ChatRequest() {}
    public ChatRequest(String userId, String message) {
        this.userId = userId;
        this.message = message;
    }

    public String getUserId() {
        return userId;
    }
    public String getMessage() {
        return message;
    }
    public Long getConversationId() {
        return conversationId;
    }
    public java.util.List<ChatHistoryMessage> getHistory() {
        return history;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }
    public void setMessage(String message) {
        this.message = message;
    }
    public void setConversationId(Long conversationId) {
        this.conversationId = conversationId;
    }
    public void setHistory(java.util.List<ChatHistoryMessage> history) {
        this.history = history;
    }
    public String getIdempotencyKey() {
        return idempotencyKey;
    }
    public void setIdempotencyKey(String idempotencyKey) {
        this.idempotencyKey = idempotencyKey;
    }
}
