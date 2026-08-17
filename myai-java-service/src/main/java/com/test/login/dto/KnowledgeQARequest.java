package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class KnowledgeQARequest {
    @JsonProperty("user_id")
    private String userId;

    @JsonProperty("file_id")
    private String fileId;

    private String question;

    @JsonProperty("top_k")
    private Integer topK = 3;

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }

    public String getFileId() {
        return fileId;
    }

    public void setFileId(String fileId) {
        this.fileId = fileId;
    }

    public String getQuestion() {
        return question;
    }

    public void setQuestion(String question) {
        this.question = question;
    }

    public Integer getTopK() {
        return topK;
    }

    public void setTopK(Integer topK) {
        this.topK = topK;
    }
}
