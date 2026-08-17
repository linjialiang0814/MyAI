package com.test.login.controller;

import com.test.login.dto.MemoryEditRequest;
import com.test.login.dto.MemoryQueryRequest;
import com.test.login.dto.MemoryItemResponse;
import com.test.login.dto.MemorySettingsRequest;
import com.test.login.dto.MemoryWriteRequest;
import com.test.login.model.User;
import com.test.login.service.PythonMemoryService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClientException;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/memory")
public class MemoryController {

    private final PythonMemoryService pythonMemoryService;

    public MemoryController(PythonMemoryService pythonMemoryService) {
        this.pythonMemoryService = pythonMemoryService;
    }

    @PostMapping("/write")
    public Map<String, Object> writeMemory(@RequestBody MemoryWriteRequest request,
                                           @AuthenticationPrincipal User user) {
        request.setUserId(String.valueOf(user.getId()));
        return pythonMemoryService.writeMemory(request);
    }

    @PostMapping("/query")
    public List<String> queryMemory(@RequestBody MemoryQueryRequest request,
                                    @AuthenticationPrincipal User user) {
        request.setUserId(String.valueOf(user.getId()));
        return pythonMemoryService.queryMemory(request);
    }

    @GetMapping("/list")
    public List<MemoryItemResponse> listMemories(@RequestParam(required = false) String memType,
                                                 @AuthenticationPrincipal User user) {
        return pythonMemoryService.listMemories(String.valueOf(user.getId()), memType);
    }

    @GetMapping("/pending")
    public List<MemoryItemResponse> listPendingMemories(@AuthenticationPrincipal User user) {
        return pythonMemoryService.listPendingMemories(String.valueOf(user.getId()));
    }

    @PostMapping("/{memoryId}/accept")
    public MemoryItemResponse acceptMemory(@PathVariable String memoryId,
                                           @AuthenticationPrincipal User user) {
        return pythonMemoryService.acceptMemory(String.valueOf(user.getId()), memoryId);
    }

    @PostMapping("/{memoryId}/reject")
    public MemoryItemResponse rejectMemory(@PathVariable String memoryId,
                                           @AuthenticationPrincipal User user) {
        return pythonMemoryService.rejectMemory(String.valueOf(user.getId()), memoryId);
    }

    @PatchMapping("/{memoryId}")
    public MemoryItemResponse editMemory(@PathVariable String memoryId,
                                         @RequestBody MemoryEditRequest request,
                                         @AuthenticationPrincipal User user) {
        return pythonMemoryService.editMemory(String.valueOf(user.getId()), memoryId, request);
    }

    @DeleteMapping("/{memoryId}")
    public void deleteMemory(@PathVariable String memoryId,
                             @AuthenticationPrincipal User user) {
        pythonMemoryService.deleteMemory(String.valueOf(user.getId()), memoryId);
    }

    @GetMapping("/settings")
    public Map<String, Object> getMemorySettings(@AuthenticationPrincipal User user) {
        return pythonMemoryService.getMemorySettings(String.valueOf(user.getId()));
    }

    @PatchMapping("/settings")
    public Map<String, Object> updateMemorySettings(@RequestBody MemorySettingsRequest request,
                                                    @AuthenticationPrincipal User user) {
        return pythonMemoryService.updateMemorySettings(String.valueOf(user.getId()), request);
    }

    @ExceptionHandler({WebClientException.class, RuntimeException.class})
    public ResponseEntity<Map<String, Object>> handlePythonMemoryError(Exception error) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of(
                "success", false,
                "error", "python_memory_service_error",
                "message", error.getMessage() == null ? "Python memory service call failed" : error.getMessage()
        ));
    }
}
