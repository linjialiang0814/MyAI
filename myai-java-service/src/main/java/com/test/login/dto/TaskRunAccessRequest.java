package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class TaskRunAccessRequest {
    @JsonProperty("user_id")
    private String userId;

    public TaskRunAccessRequest() {}

    public TaskRunAccessRequest(String userId) {
        this.userId = userId;
    }

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }
}
