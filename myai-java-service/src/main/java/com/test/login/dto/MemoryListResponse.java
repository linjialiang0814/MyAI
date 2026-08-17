package com.test.login.dto;

import java.util.List;

public class MemoryListResponse {
    private List<MemoryItemResponse> memories;

    public List<MemoryItemResponse> getMemories() {
        return memories;
    }

    public void setMemories(List<MemoryItemResponse> memories) {
        this.memories = memories;
    }
}
