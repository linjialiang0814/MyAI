package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Map;

public class KnowledgeQueryHit {
    @JsonProperty("chunk_id")
    private String chunkId;

    @JsonProperty("file_id")
    private String fileId;

    @JsonProperty("file_name")
    private String fileName;

    @JsonProperty("chunk_index")
    private int chunkIndex;

    @JsonProperty("char_start")
    private int charStart;

    @JsonProperty("char_end")
    private int charEnd;

    @JsonProperty("page_start")
    private String pageStart;

    @JsonProperty("page_end")
    private String pageEnd;

    @JsonProperty("section_title")
    private String sectionTitle;

    @JsonProperty("token_estimate")
    private int tokenEstimate;

    private String content;
    private double score;

    @JsonProperty("citation_id")
    private String citationId;

    private String snippet;
    private Map<String, Object> citation;

    @JsonProperty("retrieval_mode")
    private String retrievalMode;

    @JsonProperty("retrieval_score")
    private double retrievalScore;

    @JsonProperty("vector_score")
    private double vectorScore;

    @JsonProperty("keyword_score")
    private double keywordScore;

    @JsonProperty("filename_score")
    private double filenameScore;

    @JsonProperty("recency_score")
    private double recencyScore;

    @JsonProperty("file_filter_score")
    private double fileFilterScore;

    @JsonProperty("retrieval_explanation")
    private Map<String, Object> retrievalExplanation;

    @JsonProperty("candidate_rank")
    private int candidateRank;

    @JsonProperty("final_rank")
    private int finalRank;

    @JsonProperty("rerank_score")
    private double rerankScore;

    @JsonProperty("query_coverage")
    private double queryCoverage;

    @JsonProperty("length_quality")
    private double lengthQuality;

    @JsonProperty("duplicate_penalty")
    private double duplicatePenalty;

    @JsonProperty("diversity_penalty")
    private double diversityPenalty;

    @JsonProperty("selection_status")
    private String selectionStatus;

    @JsonProperty("selection_reason")
    private String selectionReason;

    @JsonProperty("selection_explanation")
    private Map<String, Object> selectionExplanation;

    public String getChunkId() {
        return chunkId;
    }

    public void setChunkId(String chunkId) {
        this.chunkId = chunkId;
    }

    public String getFileId() {
        return fileId;
    }

    public void setFileId(String fileId) {
        this.fileId = fileId;
    }

    public String getFileName() {
        return fileName;
    }

    public void setFileName(String fileName) {
        this.fileName = fileName;
    }

    public int getChunkIndex() {
        return chunkIndex;
    }

    public void setChunkIndex(int chunkIndex) {
        this.chunkIndex = chunkIndex;
    }

    public int getCharStart() {
        return charStart;
    }

    public void setCharStart(int charStart) {
        this.charStart = charStart;
    }

    public int getCharEnd() {
        return charEnd;
    }

    public void setCharEnd(int charEnd) {
        this.charEnd = charEnd;
    }

    public String getPageStart() {
        return pageStart;
    }

    public void setPageStart(String pageStart) {
        this.pageStart = pageStart;
    }

    public String getPageEnd() {
        return pageEnd;
    }

    public void setPageEnd(String pageEnd) {
        this.pageEnd = pageEnd;
    }

    public String getSectionTitle() {
        return sectionTitle;
    }

    public void setSectionTitle(String sectionTitle) {
        this.sectionTitle = sectionTitle;
    }

    public int getTokenEstimate() {
        return tokenEstimate;
    }

    public void setTokenEstimate(int tokenEstimate) {
        this.tokenEstimate = tokenEstimate;
    }

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public double getScore() {
        return score;
    }

    public void setScore(double score) {
        this.score = score;
    }

    public String getCitationId() {
        return citationId;
    }

    public void setCitationId(String citationId) {
        this.citationId = citationId;
    }

    public String getSnippet() {
        return snippet;
    }

    public void setSnippet(String snippet) {
        this.snippet = snippet;
    }

    public Map<String, Object> getCitation() {
        return citation;
    }

    public void setCitation(Map<String, Object> citation) {
        this.citation = citation;
    }

    public String getRetrievalMode() {
        return retrievalMode;
    }

    public void setRetrievalMode(String retrievalMode) {
        this.retrievalMode = retrievalMode;
    }

    public double getRetrievalScore() {
        return retrievalScore;
    }

    public void setRetrievalScore(double retrievalScore) {
        this.retrievalScore = retrievalScore;
    }

    public double getVectorScore() {
        return vectorScore;
    }

    public void setVectorScore(double vectorScore) {
        this.vectorScore = vectorScore;
    }

    public double getKeywordScore() {
        return keywordScore;
    }

    public void setKeywordScore(double keywordScore) {
        this.keywordScore = keywordScore;
    }

    public double getFilenameScore() {
        return filenameScore;
    }

    public void setFilenameScore(double filenameScore) {
        this.filenameScore = filenameScore;
    }

    public double getRecencyScore() {
        return recencyScore;
    }

    public void setRecencyScore(double recencyScore) {
        this.recencyScore = recencyScore;
    }

    public double getFileFilterScore() {
        return fileFilterScore;
    }

    public void setFileFilterScore(double fileFilterScore) {
        this.fileFilterScore = fileFilterScore;
    }

    public Map<String, Object> getRetrievalExplanation() {
        return retrievalExplanation;
    }

    public void setRetrievalExplanation(Map<String, Object> retrievalExplanation) {
        this.retrievalExplanation = retrievalExplanation;
    }

    public int getCandidateRank() {
        return candidateRank;
    }

    public void setCandidateRank(int candidateRank) {
        this.candidateRank = candidateRank;
    }

    public int getFinalRank() {
        return finalRank;
    }

    public void setFinalRank(int finalRank) {
        this.finalRank = finalRank;
    }

    public double getRerankScore() {
        return rerankScore;
    }

    public void setRerankScore(double rerankScore) {
        this.rerankScore = rerankScore;
    }

    public double getQueryCoverage() {
        return queryCoverage;
    }

    public void setQueryCoverage(double queryCoverage) {
        this.queryCoverage = queryCoverage;
    }

    public double getLengthQuality() {
        return lengthQuality;
    }

    public void setLengthQuality(double lengthQuality) {
        this.lengthQuality = lengthQuality;
    }

    public double getDuplicatePenalty() {
        return duplicatePenalty;
    }

    public void setDuplicatePenalty(double duplicatePenalty) {
        this.duplicatePenalty = duplicatePenalty;
    }

    public double getDiversityPenalty() {
        return diversityPenalty;
    }

    public void setDiversityPenalty(double diversityPenalty) {
        this.diversityPenalty = diversityPenalty;
    }

    public String getSelectionStatus() {
        return selectionStatus;
    }

    public void setSelectionStatus(String selectionStatus) {
        this.selectionStatus = selectionStatus;
    }

    public String getSelectionReason() {
        return selectionReason;
    }

    public void setSelectionReason(String selectionReason) {
        this.selectionReason = selectionReason;
    }

    public Map<String, Object> getSelectionExplanation() {
        return selectionExplanation;
    }

    public void setSelectionExplanation(Map<String, Object> selectionExplanation) {
        this.selectionExplanation = selectionExplanation;
    }
}
