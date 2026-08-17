package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class MemorySettingsRequest {
    @JsonProperty("memory_enabled")
    private Boolean memoryEnabled;

    @JsonProperty("auto_write_enabled")
    private Boolean autoWriteEnabled;

    @JsonProperty("sensitive_requires_confirmation")
    private Boolean sensitiveRequiresConfirmation;

    @JsonProperty("default_memory_view")
    private String defaultMemoryView;

    public Boolean getMemoryEnabled() {
        return memoryEnabled;
    }

    public void setMemoryEnabled(Boolean memoryEnabled) {
        this.memoryEnabled = memoryEnabled;
    }

    public Boolean getAutoWriteEnabled() {
        return autoWriteEnabled;
    }

    public void setAutoWriteEnabled(Boolean autoWriteEnabled) {
        this.autoWriteEnabled = autoWriteEnabled;
    }

    public Boolean getSensitiveRequiresConfirmation() {
        return sensitiveRequiresConfirmation;
    }

    public void setSensitiveRequiresConfirmation(Boolean sensitiveRequiresConfirmation) {
        this.sensitiveRequiresConfirmation = sensitiveRequiresConfirmation;
    }

    public String getDefaultMemoryView() {
        return defaultMemoryView;
    }

    public void setDefaultMemoryView(String defaultMemoryView) {
        this.defaultMemoryView = defaultMemoryView;
    }
}
