package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

public class KnowledgeFileResponse {
    @JsonProperty("file_id")
    private String fileId;

    @JsonProperty("file_name")
    private String fileName;

    @JsonProperty("file_type")
    private String fileType;

    @JsonProperty("size_bytes")
    private int sizeBytes;

    @JsonProperty("content_hash")
    private String contentHash;

    @JsonProperty("chunk_count")
    private int chunkCount;

    @JsonProperty("uploaded_at")
    private String uploadedAt;

    private String summary;

    @JsonProperty("document_profile")
    private Map<String, Object> documentProfile;

    private String parser;

    @JsonProperty("parser_version")
    private String parserVersion;

    @JsonProperty("text_length")
    private int textLength;

    @JsonProperty("embedding_provider")
    private String embeddingProvider;

    @JsonProperty("embedding_model")
    private String embeddingModel;

    @JsonProperty("ingestion_status")
    private String ingestionStatus;

    @JsonProperty("ingestion_warnings")
    private List<String> ingestionWarnings;

    @JsonProperty("ingestion_report")
    private Map<String, Object> ingestionReport;

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

    public String getFileType() {
        return fileType;
    }

    public void setFileType(String fileType) {
        this.fileType = fileType;
    }

    public int getSizeBytes() {
        return sizeBytes;
    }

    public void setSizeBytes(int sizeBytes) {
        this.sizeBytes = sizeBytes;
    }

    public String getContentHash() {
        return contentHash;
    }

    public void setContentHash(String contentHash) {
        this.contentHash = contentHash;
    }

    public int getChunkCount() {
        return chunkCount;
    }

    public void setChunkCount(int chunkCount) {
        this.chunkCount = chunkCount;
    }

    public String getUploadedAt() {
        return uploadedAt;
    }

    public void setUploadedAt(String uploadedAt) {
        this.uploadedAt = uploadedAt;
    }

    public String getSummary() {
        return summary;
    }

    public void setSummary(String summary) {
        this.summary = summary;
    }

    public Map<String, Object> getDocumentProfile() {
        return documentProfile;
    }

    public void setDocumentProfile(Map<String, Object> documentProfile) {
        this.documentProfile = documentProfile;
    }

    public String getParser() {
        return parser;
    }

    public void setParser(String parser) {
        this.parser = parser;
    }

    public String getParserVersion() {
        return parserVersion;
    }

    public void setParserVersion(String parserVersion) {
        this.parserVersion = parserVersion;
    }

    public int getTextLength() {
        return textLength;
    }

    public void setTextLength(int textLength) {
        this.textLength = textLength;
    }

    public String getEmbeddingProvider() {
        return embeddingProvider;
    }

    public void setEmbeddingProvider(String embeddingProvider) {
        this.embeddingProvider = embeddingProvider;
    }

    public String getEmbeddingModel() {
        return embeddingModel;
    }

    public void setEmbeddingModel(String embeddingModel) {
        this.embeddingModel = embeddingModel;
    }

    public String getIngestionStatus() {
        return ingestionStatus;
    }

    public void setIngestionStatus(String ingestionStatus) {
        this.ingestionStatus = ingestionStatus;
    }

    public List<String> getIngestionWarnings() {
        return ingestionWarnings;
    }

    public void setIngestionWarnings(List<String> ingestionWarnings) {
        this.ingestionWarnings = ingestionWarnings;
    }

    public Map<String, Object> getIngestionReport() {
        return ingestionReport;
    }

    public void setIngestionReport(Map<String, Object> ingestionReport) {
        this.ingestionReport = ingestionReport;
    }
}
