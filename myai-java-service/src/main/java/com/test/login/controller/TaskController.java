package com.test.login.controller;

import com.test.login.dto.TaskRequest;
import com.test.login.dto.TaskResponse;
import com.test.login.model.User;
import com.test.login.service.PythonTaskService;
import com.test.login.service.ConversationService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClientException;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Mono;

import java.util.Map;

@RestController
@RequestMapping("/task")
public class TaskController {
    private final PythonTaskService pythonTaskService;
    private final ConversationService conversationService;

    public TaskController(PythonTaskService pythonTaskService, ConversationService conversationService) {
        this.pythonTaskService = pythonTaskService;
        this.conversationService = conversationService;
    }

    @PostMapping
    public Mono<TaskResponse> getTask(@RequestBody TaskRequest request,
                                      @AuthenticationPrincipal User user) {
        request.setUserId(String.valueOf(user.getId()));
        validateConversationOwnership(request, user);
        return pythonTaskService.getTask(request);
    }

    @GetMapping("/runs/{taskRunId}")
    public Mono<ResponseEntity<Map<String, Object>>> getTaskRun(@PathVariable String taskRunId,
                                                                @AuthenticationPrincipal User user) {
        return pythonTaskService.getTaskRun(taskRunId, String.valueOf(user.getId()))
                .map(ResponseEntity::ok)
                .defaultIfEmpty(ResponseEntity.notFound().build());
    }

    @GetMapping("/runs")
    public Mono<Map<String, Object>> listTaskRuns(@RequestParam(defaultValue = "20") int limit,
                                                  @AuthenticationPrincipal User user) {
        return pythonTaskService.listTaskRuns(String.valueOf(user.getId()), limit);
    }

    @GetMapping("/workflows")
    public Mono<Map<String, Object>> listWorkflows() {
        return pythonTaskService.listWorkflows();
    }

    @GetMapping("/tools")
    public Mono<Map<String, Object>> listTools() {
        return pythonTaskService.listTools();
    }

    @PostMapping("/runs")
    public Mono<Map<String, Object>> startTaskRun(@RequestBody TaskRequest request,
                                                  @AuthenticationPrincipal User user) {
        request.setUserId(String.valueOf(user.getId()));
        validateConversationOwnership(request, user);
        return pythonTaskService.startTaskRun(request);
    }

    @PostMapping("/runs/{taskRunId}/cancel")
    public Mono<ResponseEntity<Map<String, Object>>> cancelTaskRun(@PathVariable String taskRunId,
                                                                   @AuthenticationPrincipal User user) {
        return pythonTaskService.cancelTaskRun(taskRunId, String.valueOf(user.getId()))
                .map(ResponseEntity::ok)
                .defaultIfEmpty(ResponseEntity.notFound().build());
    }

    @ExceptionHandler({WebClientException.class, RuntimeException.class})
    public ResponseEntity<Map<String, Object>> handlePythonTaskError(Exception error) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of(
                "success", false,
                "error", "python_task_service_error",
                "message", error.getMessage() == null ? "Python task service call failed" : error.getMessage()
        ));
    }

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, Object>> handleConversationAccessError(ResponseStatusException error) {
        return ResponseEntity.status(error.getStatusCode()).body(Map.of(
                "success", false,
                "error", "conversation_not_found",
                "message", error.getReason() == null ? "Conversation not found" : error.getReason()
        ));
    }

    private void validateConversationOwnership(TaskRequest request, User user) {
        if (request.getConversationId() != null) {
            conversationService.getConversationDetail(user, request.getConversationId());
        }
    }
}
