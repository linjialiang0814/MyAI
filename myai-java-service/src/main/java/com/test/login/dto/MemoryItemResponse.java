package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Map;

public class MemoryItemResponse {
    @JsonProperty("memory_id")
    private String memoryId;
    private String content;

    @JsonProperty("mem_type")
    private String memType;

    private float score;
    private float importance;

    @JsonProperty("created_at")
    private String createdAt;

    @JsonProperty("last_accessed_at")
    private String lastAccessedAt;

    @JsonProperty("access_count")
    private int accessCount;

    private String status;
    private String source;

    @JsonProperty("source_ref")
    private Map<String, Object> sourceRef;

    @JsonProperty("extraction_reason")
    private String extractionReason;

    private Float confidence;

    @JsonProperty("raw_confidence")
    private Float rawConfidence;

    @JsonProperty("calibrated_confidence")
    private Float calibratedConfidence;

    @JsonProperty("confidence_calibration_reason")
    private String confidenceCalibrationReason;

    @JsonProperty("confidence_calibration_factors")
    private String confidenceCalibrationFactors;

    private String scope;
    private String sensitivity;

    @JsonProperty("review_status")
    private String reviewStatus;

    @JsonProperty("review_reason")
    private String reviewReason;

    @JsonProperty("sensitive_category")
    private String sensitiveCategory;

    @JsonProperty("edited_before_accept")
    private Boolean editedBeforeAccept;

    @JsonProperty("last_edited_at")
    private String lastEditedAt;

    @JsonProperty("original_content")
    private String originalContent;

    @JsonProperty("merged_count")
    private Integer mergedCount;

    @JsonProperty("merged_from")
    private String mergedFrom;

    @JsonProperty("merge_events")
    private String mergeEvents;

    @JsonProperty("last_merged_at")
    private String lastMergedAt;

    @JsonProperty("last_merge_reason")
    private String lastMergeReason;

    @JsonProperty("last_merge_type")
    private String lastMergeType;

    @JsonProperty("extraction_batch_id")
    private String extractionBatchId;

    @JsonProperty("candidate_index")
    private Integer candidateIndex;

    @JsonProperty("candidate_count")
    private Integer candidateCount;

    @JsonProperty("multi_candidate")
    private Boolean multiCandidate;

    @JsonProperty("observed_at")
    private String observedAt;

    @JsonProperty("valid_from")
    private String validFrom;

    @JsonProperty("valid_to")
    private String validTo;

    @JsonProperty("is_current")
    private Boolean current;

    @JsonProperty("consolidation_summary")
    private Boolean consolidationSummary;

    @JsonProperty("consolidation_kind")
    private String consolidationKind;

    @JsonProperty("consolidation_policy")
    private String consolidationPolicy;

    @JsonProperty("consolidation_evidence_action")
    private String consolidationEvidenceAction;

    @JsonProperty("consolidated_at")
    private String consolidatedAt;

    @JsonProperty("consolidated_count")
    private Integer consolidatedCount;

    @JsonProperty("consolidated_from")
    private String consolidatedFrom;

    @JsonProperty("consolidation_events")
    private String consolidationEvents;

    @JsonProperty("consolidated_into")
    private String consolidatedInto;

    @JsonProperty("retrieval_enabled")
    private Boolean retrievalEnabled;

    private Boolean pinned;

    @JsonProperty("user_hidden")
    private Boolean userHidden;

    @JsonProperty("user_locked")
    private Boolean userLocked;

    @JsonProperty("user_control_reason")
    private String userControlReason;

    public String getMemoryId() {
        return memoryId;
    }

    public void setMemoryId(String memoryId) {
        this.memoryId = memoryId;
    }

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

    public float getScore() {
        return score;
    }

    public void setScore(float score) {
        this.score = score;
    }

    public float getImportance() {
        return importance;
    }

    public void setImportance(float importance) {
        this.importance = importance;
    }

    public String getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(String createdAt) {
        this.createdAt = createdAt;
    }

    public String getLastAccessedAt() {
        return lastAccessedAt;
    }

    public void setLastAccessedAt(String lastAccessedAt) {
        this.lastAccessedAt = lastAccessedAt;
    }

    public int getAccessCount() {
        return accessCount;
    }

    public void setAccessCount(int accessCount) {
        this.accessCount = accessCount;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public Map<String, Object> getSourceRef() {
        return sourceRef;
    }

    public void setSourceRef(Map<String, Object> sourceRef) {
        this.sourceRef = sourceRef;
    }

    public String getExtractionReason() {
        return extractionReason;
    }

    public void setExtractionReason(String extractionReason) {
        this.extractionReason = extractionReason;
    }

    public Float getConfidence() {
        return confidence;
    }

    public void setConfidence(Float confidence) {
        this.confidence = confidence;
    }

    public Float getRawConfidence() {
        return rawConfidence;
    }

    public void setRawConfidence(Float rawConfidence) {
        this.rawConfidence = rawConfidence;
    }

    public Float getCalibratedConfidence() {
        return calibratedConfidence;
    }

    public void setCalibratedConfidence(Float calibratedConfidence) {
        this.calibratedConfidence = calibratedConfidence;
    }

    public String getConfidenceCalibrationReason() {
        return confidenceCalibrationReason;
    }

    public void setConfidenceCalibrationReason(String confidenceCalibrationReason) {
        this.confidenceCalibrationReason = confidenceCalibrationReason;
    }

    public String getConfidenceCalibrationFactors() {
        return confidenceCalibrationFactors;
    }

    public void setConfidenceCalibrationFactors(String confidenceCalibrationFactors) {
        this.confidenceCalibrationFactors = confidenceCalibrationFactors;
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

    public String getReviewStatus() {
        return reviewStatus;
    }

    public void setReviewStatus(String reviewStatus) {
        this.reviewStatus = reviewStatus;
    }

    public String getReviewReason() {
        return reviewReason;
    }

    public void setReviewReason(String reviewReason) {
        this.reviewReason = reviewReason;
    }

    public String getSensitiveCategory() {
        return sensitiveCategory;
    }

    public void setSensitiveCategory(String sensitiveCategory) {
        this.sensitiveCategory = sensitiveCategory;
    }

    public Boolean getEditedBeforeAccept() {
        return editedBeforeAccept;
    }

    public void setEditedBeforeAccept(Boolean editedBeforeAccept) {
        this.editedBeforeAccept = editedBeforeAccept;
    }

    public String getLastEditedAt() {
        return lastEditedAt;
    }

    public void setLastEditedAt(String lastEditedAt) {
        this.lastEditedAt = lastEditedAt;
    }

    public String getOriginalContent() {
        return originalContent;
    }

    public void setOriginalContent(String originalContent) {
        this.originalContent = originalContent;
    }

    public Integer getMergedCount() {
        return mergedCount;
    }

    public void setMergedCount(Integer mergedCount) {
        this.mergedCount = mergedCount;
    }

    public String getMergedFrom() {
        return mergedFrom;
    }

    public void setMergedFrom(String mergedFrom) {
        this.mergedFrom = mergedFrom;
    }

    public String getMergeEvents() {
        return mergeEvents;
    }

    public void setMergeEvents(String mergeEvents) {
        this.mergeEvents = mergeEvents;
    }

    public String getLastMergedAt() {
        return lastMergedAt;
    }

    public void setLastMergedAt(String lastMergedAt) {
        this.lastMergedAt = lastMergedAt;
    }

    public String getLastMergeReason() {
        return lastMergeReason;
    }

    public void setLastMergeReason(String lastMergeReason) {
        this.lastMergeReason = lastMergeReason;
    }

    public String getLastMergeType() {
        return lastMergeType;
    }

    public void setLastMergeType(String lastMergeType) {
        this.lastMergeType = lastMergeType;
    }

    public String getExtractionBatchId() {
        return extractionBatchId;
    }

    public void setExtractionBatchId(String extractionBatchId) {
        this.extractionBatchId = extractionBatchId;
    }

    public Integer getCandidateIndex() {
        return candidateIndex;
    }

    public void setCandidateIndex(Integer candidateIndex) {
        this.candidateIndex = candidateIndex;
    }

    public Integer getCandidateCount() {
        return candidateCount;
    }

    public void setCandidateCount(Integer candidateCount) {
        this.candidateCount = candidateCount;
    }

    public Boolean getMultiCandidate() {
        return multiCandidate;
    }

    public void setMultiCandidate(Boolean multiCandidate) {
        this.multiCandidate = multiCandidate;
    }

    public String getObservedAt() {
        return observedAt;
    }

    public void setObservedAt(String observedAt) {
        this.observedAt = observedAt;
    }

    public String getValidFrom() {
        return validFrom;
    }

    public void setValidFrom(String validFrom) {
        this.validFrom = validFrom;
    }

    public String getValidTo() {
        return validTo;
    }

    public void setValidTo(String validTo) {
        this.validTo = validTo;
    }

    public Boolean getCurrent() {
        return current;
    }

    public void setCurrent(Boolean current) {
        this.current = current;
    }

    public Boolean getConsolidationSummary() {
        return consolidationSummary;
    }

    public void setConsolidationSummary(Boolean consolidationSummary) {
        this.consolidationSummary = consolidationSummary;
    }

    public String getConsolidationKind() {
        return consolidationKind;
    }

    public void setConsolidationKind(String consolidationKind) {
        this.consolidationKind = consolidationKind;
    }

    public String getConsolidationPolicy() {
        return consolidationPolicy;
    }

    public void setConsolidationPolicy(String consolidationPolicy) {
        this.consolidationPolicy = consolidationPolicy;
    }

    public String getConsolidationEvidenceAction() {
        return consolidationEvidenceAction;
    }

    public void setConsolidationEvidenceAction(String consolidationEvidenceAction) {
        this.consolidationEvidenceAction = consolidationEvidenceAction;
    }

    public String getConsolidatedAt() {
        return consolidatedAt;
    }

    public void setConsolidatedAt(String consolidatedAt) {
        this.consolidatedAt = consolidatedAt;
    }

    public Integer getConsolidatedCount() {
        return consolidatedCount;
    }

    public void setConsolidatedCount(Integer consolidatedCount) {
        this.consolidatedCount = consolidatedCount;
    }

    public String getConsolidatedFrom() {
        return consolidatedFrom;
    }

    public void setConsolidatedFrom(String consolidatedFrom) {
        this.consolidatedFrom = consolidatedFrom;
    }

    public String getConsolidationEvents() {
        return consolidationEvents;
    }

    public void setConsolidationEvents(String consolidationEvents) {
        this.consolidationEvents = consolidationEvents;
    }

    public String getConsolidatedInto() {
        return consolidatedInto;
    }

    public void setConsolidatedInto(String consolidatedInto) {
        this.consolidatedInto = consolidatedInto;
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

    public String getUserControlReason() {
        return userControlReason;
    }

    public void setUserControlReason(String userControlReason) {
        this.userControlReason = userControlReason;
    }
}
