package com.test.login.service;

import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Map;

@Service
public class PythonObservabilityService {
    private final WebClient webClient;

    public PythonObservabilityService(WebClient pythonWebClient) {
        this.webClient = pythonWebClient;
    }

    public Mono<Map<String, Object>> getSummary() {
        return webClient.get()
                .uri("/observability/summary")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }

    public Mono<Map<String, Object>> listEvents(int limit) {
        return webClient.get()
                .uri("/observability/events?limit={limit}", limit)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }

    public Mono<Map<String, Object>> probeModelRuntime() {
        return webClient.post()
                .uri("/observability/model/probe")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }

    public Mono<Map<String, Object>> listEvalReports() {
        return webClient.get()
                .uri("/eval/reports")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }

    public Mono<Map<String, Object>> listEvalRuns(int limit) {
        return webClient.get()
                .uri("/eval/runs?limit={limit}", limit)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }

    public Mono<Map<String, Object>> runEval(String suite, boolean includeLive) {
        return webClient.post()
                .uri("/eval/runs?suite={suite}&include_live={includeLive}", suite, includeLive)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }

    public Mono<Map<String, Object>> getEvalGateConfig() {
        return webClient.get()
                .uri("/eval/gates/config")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }

    public Mono<Map<String, Object>> runEvalGate(String suite, boolean includeLive) {
        return webClient.post()
                .uri("/eval/gates/run?suite={suite}&include_live={includeLive}", suite, includeLive)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }

    public Mono<Map<String, Object>> createMaintenanceReport(String suite, boolean includeLive) {
        return webClient.post()
                .uri("/eval/maintenance-report?suite={suite}&include_live={includeLive}", suite, includeLive)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {});
    }
}
