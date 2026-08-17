package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class KnowledgeMaintenanceRequest {
    @JsonProperty("user_id")
    private String userId;

    @JsonProperty("dry_run")
    private boolean dryRun = true;

    @JsonProperty("file_id")
    private String fileId;

    private boolean rebuild = false;

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }

    public boolean isDryRun() {
        return dryRun;
    }

    public void setDryRun(boolean dryRun) {
        this.dryRun = dryRun;
    }

    public String getFileId() {
        return fileId;
    }

    public void setFileId(String fileId) {
        this.fileId = fileId;
    }

    public boolean isRebuild() {
        return rebuild;
    }

    public void setRebuild(boolean rebuild) {
        this.rebuild = rebuild;
    }
}
