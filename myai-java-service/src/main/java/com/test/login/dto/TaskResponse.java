package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;

public class TaskResponse {
    @JsonProperty("task_run_id")
    private String taskRunId;
    @JsonProperty("agent_run_id")
    private String agentRunId;
    @JsonProperty("conversation_id")
    private Long conversationId;
    private String status;
    private String content;
    private Map<String, Object> plan;
    private Map<String, Object> result;
    private float reward;
    private boolean success;
    private String error;
    @JsonProperty("error_code")
    private String errorCode;
    private Boolean retryable;
    @JsonProperty("latency_ms")
    private float latencyMs;
    private List<Map<String, Object>> events;

    public TaskResponse(){}

    public String getTaskRunId() {
        return taskRunId;
    }
    public void setTaskRunId(String taskRunId) {
        this.taskRunId = taskRunId;
    }

    public String getAgentRunId() {
        return agentRunId;
    }
    public void setAgentRunId(String agentRunId) {
        this.agentRunId = agentRunId;
    }

    public Long getConversationId() {
        return conversationId;
    }
    public void setConversationId(Long conversationId) {
        this.conversationId = conversationId;
    }

    public String getStatus() {
        return status;
    }
    public void setStatus(String status) {
        this.status = status;
    }

    public String getContent() {
        return content;
    }
    public void setContent(String content) {
        this.content = content;
    }

    public Map<String, Object> getPlan() {
        return plan;
    }
    public void setPlan(Map<String, Object> plan) {
        this.plan = plan;
    }
    public Map<String, Object> getResult() {
        return result;
    }
    public void setResult(Map<String, Object> result) {
        this.result = result;
    }

    public float getReward() {
        return reward;
    }
    public void setReward(float reward) {
        this.reward = reward;
    }
    public boolean isSuccess() {
        return success;
    }
    public void setSuccess(boolean success) {
        this.success = success;
    }

    public String getError() {
        return error;
    }
    public void setError(String error) {
        this.error = error;
    }

    public String getErrorCode() {
        return errorCode;
    }
    public void setErrorCode(String errorCode) {
        this.errorCode = errorCode;
    }

    public Boolean getRetryable() {
        return retryable;
    }
    public void setRetryable(Boolean retryable) {
        this.retryable = retryable;
    }

    public float getLatencyMs() {
        return latencyMs;
    }
    public void setLatencyMs(float latencyMs) {
        this.latencyMs = latencyMs;
    }

    public List<Map<String, Object>> getEvents() {
        return events;
    }
    public void setEvents(List<Map<String, Object>> events) {
        this.events = events;
    }
}
