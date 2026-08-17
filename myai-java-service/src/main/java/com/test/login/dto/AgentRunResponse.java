package com.test.login.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

public class AgentRunResponse {
    @JsonProperty("run_id")
    private String runId;
    private String status;
    @JsonProperty("started_at")
    private String startedAt;
    @JsonProperty("finished_at")
    private String finishedAt;
    private List<AgentStepResponse> steps;

    public String getRunId() {
        return runId;
    }

    public void setRunId(String runId) {
        this.runId = runId;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getStartedAt() {
        return startedAt;
    }

    public void setStartedAt(String startedAt) {
        this.startedAt = startedAt;
    }

    public String getFinishedAt() {
        return finishedAt;
    }

    public void setFinishedAt(String finishedAt) {
        this.finishedAt = finishedAt;
    }

    public List<AgentStepResponse> getSteps() {
        return steps;
    }

    public void setSteps(List<AgentStepResponse> steps) {
        this.steps = steps;
    }
}

