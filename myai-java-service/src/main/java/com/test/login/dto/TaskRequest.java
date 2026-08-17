package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class TaskRequest {
    @JsonProperty("user_id")
    private String userId;
    private String content;
    @JsonProperty("conversation_id")
    private Long conversationId;
    @JsonProperty("agent_run_id")
    private String agentRunId;
    @JsonProperty("idempotency_key")
    private String idempotencyKey;

    public TaskRequest() {}

    public TaskRequest(String content) {
        this.content = content;
    }

    public TaskRequest(String userId, String content) {
        this.userId = userId;
        this.content = content;
    }

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public Long getConversationId() {
        return conversationId;
    }

    public void setConversationId(Long conversationId) {
        this.conversationId = conversationId;
    }

    public String getAgentRunId() {
        return agentRunId;
    }

    public void setAgentRunId(String agentRunId) {
        this.agentRunId = agentRunId;
    }

    public String getIdempotencyKey() {
        return idempotencyKey;
    }

    public void setIdempotencyKey(String idempotencyKey) {
        this.idempotencyKey = idempotencyKey;
    }
}
