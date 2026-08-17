package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class ChatHistoryMessage {
    private String role;
    private String content;

    @JsonProperty("created_at")
    private String createdAt;

    public ChatHistoryMessage() {}

    public ChatHistoryMessage(String role, String content) {
        this.role = role;
        this.content = content;
    }

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public String getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(String createdAt) {
        this.createdAt = createdAt;
    }
}
