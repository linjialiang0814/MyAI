package com.test.login.service;

import com.test.login.dto.TaskRequest;
import com.test.login.dto.TaskResponse;
import com.test.login.dto.TaskRunAccessRequest;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class PythonTaskService {
    private final WebClient webClient;

    public PythonTaskService(WebClient pythonWebClient){
        this.webClient = pythonWebClient;
    }

    public Mono<TaskResponse> getTask(TaskRequest request){
        return webClient.post().uri("/task").bodyValue(request).retrieve().bodyToMono(TaskResponse.class);
    }

    public Mono<Map<String, Object>> getTaskRun(String taskRunId, String userId) {
        return webClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/task/runs/{taskRunId}")
                        .queryParam("user_id", userId)
                        .build(taskRunId))
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                .filter(run -> belongsToUser(run, userId))
                .onErrorResume(WebClientResponseException.NotFound.class, error -> Mono.empty());
    }

    public Mono<Map<String, Object>> listTaskRuns(String userId, int limit) {
        return webClient.get()
                .uri("/task/runs?user_id={userId}&limit={limit}", userId, limit)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                .map(payload -> filterRunsByUser(payload, userId));
    }

    public Mono<Map<String, Object>> listWorkflows() {
        return webClient.get()
                .uri("/task/workflows")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }

    public Mono<Map<String, Object>> listTools() {
        return webClient.get()
                .uri("/task/tools")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }

    public Mono<Map<String, Object>> startTaskRun(TaskRequest request) {
        return webClient.post()
                .uri("/task/runs")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }

    public Mono<Map<String, Object>> cancelTaskRun(String taskRunId, String userId) {
        return getTaskRun(taskRunId, userId)
                .flatMap(ownedRun -> webClient.post()
                        .uri("/task/runs/{taskRunId}/cancel", taskRunId)
                        .bodyValue(new TaskRunAccessRequest(userId))
                        .retrieve()
                        .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                        .filter(run -> belongsToUser(run, userId))
                        .onErrorResume(WebClientResponseException.NotFound.class, error -> Mono.empty()));
    }

    private boolean belongsToUser(Map<String, Object> run, String userId) {
        Object owner = run.get("user_id");
        return owner != null && userId.equals(String.valueOf(owner));
    }

    private Map<String, Object> filterRunsByUser(Map<String, Object> payload, String userId) {
        Object runsValue = payload.get("runs");
        List<?> runs = runsValue instanceof List<?> list ? list : List.of();
        List<Map<String, Object>> ownedRuns = runs.stream()
                .filter(Map.class::isInstance)
                .map(item -> (Map<?, ?>) item)
                .filter(item -> {
                    Object owner = item.get("user_id");
                    return owner != null && userId.equals(String.valueOf(owner));
                })
                .map(item -> {
                    Map<String, Object> run = new LinkedHashMap<>();
                    item.forEach((key, value) -> run.put(String.valueOf(key), value));
                    return run;
                })
                .toList();
        Map<String, Object> filtered = new LinkedHashMap<>(payload);
        filtered.put("runs", ownedRuns);
        return filtered;
    }
}
