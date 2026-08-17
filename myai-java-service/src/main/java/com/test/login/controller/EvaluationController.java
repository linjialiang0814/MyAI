package com.test.login.controller;

import com.test.login.service.PythonObservabilityService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.util.Map;

@RestController
@RequestMapping("/eval")
public class EvaluationController {
    private final PythonObservabilityService pythonObservabilityService;

    public EvaluationController(PythonObservabilityService pythonObservabilityService) {
        this.pythonObservabilityService = pythonObservabilityService;
    }

    @GetMapping("/reports")
    public Mono<Map<String, Object>> listReports() {
        return pythonObservabilityService.listEvalReports();
    }

    @GetMapping("/runs")
    public Mono<Map<String, Object>> listRuns(@RequestParam(defaultValue = "10") int limit) {
        return pythonObservabilityService.listEvalRuns(limit);
    }

    @PostMapping("/runs")
    public Mono<Map<String, Object>> runEval(@RequestParam(defaultValue = "mcp") String suite,
                                             @RequestParam(defaultValue = "false") boolean includeLive) {
        return pythonObservabilityService.runEval(suite, includeLive);
    }

    @GetMapping("/gates/config")
    public Mono<Map<String, Object>> getGateConfig() {
        return pythonObservabilityService.getEvalGateConfig();
    }

    @PostMapping("/gates/run")
    public Mono<Map<String, Object>> runGate(@RequestParam(defaultValue = "all") String suite,
                                             @RequestParam(defaultValue = "false") boolean includeLive) {
        return pythonObservabilityService.runEvalGate(suite, includeLive);
    }

    @PostMapping("/maintenance-report")
    public Mono<Map<String, Object>> createMaintenanceReport(@RequestParam(defaultValue = "all") String suite,
                                                             @RequestParam(defaultValue = "false") boolean includeLive) {
        return pythonObservabilityService.createMaintenanceReport(suite, includeLive);
    }
}
