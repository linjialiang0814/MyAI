package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class KnowledgeQueryRequest {
    @JsonProperty("user_id")
    private String userId;

    private String query;

    @JsonProperty("top_k")
    private Integer topK = 3;

    @JsonProperty("file_id")
    private String fileId;

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }

    public String getQuery() {
        return query;
    }

    public void setQuery(String query) {
        this.query = query;
    }

    public Integer getTopK() {
        return topK;
    }

    public void setTopK(Integer topK) {
        this.topK = topK;
    }

    public String getFileId() {
        return fileId;
    }

    public void setFileId(String fileId) {
        this.fileId = fileId;
    }
}
