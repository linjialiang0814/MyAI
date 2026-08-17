package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class ChatResponse {
    private String reply;
    @JsonProperty("run_id")
    private String runId;
    private AgentRunResponse trace;
    @JsonProperty("conversation_id")
    private Long conversationId;

    public ChatResponse() {}

    public String getReply() {
        return reply;
    }
    public void setReply(String reply) {
        this.reply = reply;
    }

    public String getRunId() {
        return runId;
    }

    public void setRunId(String runId) {
        this.runId = runId;
    }

    public AgentRunResponse getTrace() {
        return trace;
    }

    public void setTrace(AgentRunResponse trace) {
        this.trace = trace;
    }

    public Long getConversationId() {
        return conversationId;
    }

    public void setConversationId(Long conversationId) {
        this.conversationId = conversationId;
    }
}
