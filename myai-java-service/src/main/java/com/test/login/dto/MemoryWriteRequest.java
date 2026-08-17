package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class MemoryWriteRequest {
    @JsonProperty("user_id")
    private String userId;
    private String content;

    public MemoryWriteRequest(){}

    public MemoryWriteRequest(String userId, String content){
        this.userId = userId;
        this.content = content;
    }

    public String getUserId(){
        return userId;
    }

    public String getContent(){
        return content;
    }

    public void setUserId(String userId){
        this.userId = userId;
    }

    public void setContent(String content){
        this.content = content;
    }

}
