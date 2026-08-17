package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class MemoryEditRequest {
    private String content;

    @JsonProperty("mem_type")
    private String memType;

    private String scope;
    private String sensitivity;
    private Float importance;

    @JsonProperty("retrieval_enabled")
    private Boolean retrievalEnabled;

    private Boolean pinned;

    @JsonProperty("user_hidden")
    private Boolean userHidden;

    @JsonProperty("user_locked")
    private Boolean userLocked;

    @JsonProperty("is_current")
    private Boolean current;

    @JsonProperty("user_control_reason")
    private String userControlReason;

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public String getMemType() {
        return memType;
    }

    public void setMemType(String memType) {
        this.memType = memType;
    }

    public String getScope() {
        return scope;
    }

    public void setScope(String scope) {
        this.scope = scope;
    }

    public String getSensitivity() {
        return sensitivity;
    }

    public void setSensitivity(String sensitivity) {
        this.sensitivity = sensitivity;
    }

    public Float getImportance() {
        return importance;
    }

    public void setImportance(Float importance) {
        this.importance = importance;
    }

    public Boolean getRetrievalEnabled() {
        return retrievalEnabled;
    }

    public void setRetrievalEnabled(Boolean retrievalEnabled) {
        this.retrievalEnabled = retrievalEnabled;
    }

    public Boolean getPinned() {
        return pinned;
    }

    public void setPinned(Boolean pinned) {
        this.pinned = pinned;
    }

    public Boolean getUserHidden() {
        return userHidden;
    }

    public void setUserHidden(Boolean userHidden) {
        this.userHidden = userHidden;
    }

    public Boolean getUserLocked() {
        return userLocked;
    }

    public void setUserLocked(Boolean userLocked) {
        this.userLocked = userLocked;
    }

    public Boolean getCurrent() {
        return current;
    }

    public void setCurrent(Boolean current) {
        this.current = current;
    }

    public String getUserControlReason() {
        return userControlReason;
    }

    public void setUserControlReason(String userControlReason) {
        this.userControlReason = userControlReason;
    }
}
