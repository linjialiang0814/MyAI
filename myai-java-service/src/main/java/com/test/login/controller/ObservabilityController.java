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
@RequestMapping("/observability")
public class ObservabilityController {
    private final PythonObservabilityService pythonObservabilityService;

    public ObservabilityController(PythonObservabilityService pythonObservabilityService) {
        this.pythonObservabilityService = pythonObservabilityService;
    }

    @GetMapping("/summary")
    public Mono<Map<String, Object>> getSummary() {
        return pythonObservabilityService.getSummary();
    }

    @GetMapping("/events")
    public Mono<Map<String, Object>> listEvents(@RequestParam(defaultValue = "50") int limit) {
        return pythonObservabilityService.listEvents(limit);
    }

    @PostMapping("/model/probe")
    public Mono<Map<String, Object>> probeModelRuntime() {
        return pythonObservabilityService.probeModelRuntime();
    }
}
