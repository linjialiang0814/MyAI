package com.test.login.dto;

import java.util.List;

public class KnowledgeQueryResponse {
    private List<KnowledgeQueryHit> hits;

    public List<KnowledgeQueryHit> getHits() {
        return hits;
    }

    public void setHits(List<KnowledgeQueryHit> hits) {
        this.hits = hits;
    }
}
