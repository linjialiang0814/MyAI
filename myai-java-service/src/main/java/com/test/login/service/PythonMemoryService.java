package com.test.login.service;

import com.test.login.dto.MemoryEditRequest;
import com.test.login.dto.MemoryQueryRequest;
import com.test.login.dto.MemoryQueryResponse;
import com.test.login.dto.MemoryItemResponse;
import com.test.login.dto.MemoryListResponse;
import com.test.login.dto.MemorySettingsRequest;
import com.test.login.dto.MemoryWriteRequest;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.List;
import java.util.Map;

@Service
public class PythonMemoryService {
    private final WebClient pythonWebClient;

    public PythonMemoryService(WebClient pythonWebClient){
        this.pythonWebClient = pythonWebClient;
    }

    public Map<String, Object> writeMemory(MemoryWriteRequest request){
        Map<String, Object> response = pythonWebClient.post()
                .uri("/memory/write")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                .block();

        if (response == null) {
            throw new RuntimeException("Error writing memory!");
        }

        return response;
    }

    public List<String> queryMemory(MemoryQueryRequest request){
        MemoryQueryResponse response = pythonWebClient.post()
                .uri("/memory/query")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(MemoryQueryResponse.class)
                .block();

        if(response == null){
            throw new RuntimeException("Error querying memory!");
        }

        return response.getMemories();
    }

    public List<MemoryItemResponse> listMemories(String userId, String memType) {
        String uri = memType == null || memType.isBlank()
                ? "/memory/list/{userId}"
                : "/memory/list/{userId}?mem_type={memType}";
        MemoryListResponse response = pythonWebClient.get()
                .uri(uri, userId, memType)
                .retrieve()
                .bodyToMono(MemoryListResponse.class)
                .block();

        if (response == null) {
            throw new RuntimeException("Error listing memories!");
        }

        return response.getMemories();
    }

    public List<MemoryItemResponse> listPendingMemories(String userId) {
        MemoryListResponse response = pythonWebClient.get()
                .uri("/memory/pending/{userId}", userId)
                .retrieve()
                .bodyToMono(MemoryListResponse.class)
                .block();

        if (response == null) {
            throw new RuntimeException("Error listing pending memories!");
        }

        return response.getMemories();
    }

    public MemoryItemResponse acceptMemory(String userId, String memoryId) {
        MemoryItemResponse response = pythonWebClient.post()
                .uri("/memory/{userId}/{memoryId}/accept", userId, memoryId)
                .retrieve()
                .bodyToMono(MemoryItemResponse.class)
                .block();

        if (response == null) {
            throw new RuntimeException("Error accepting memory!");
        }

        return response;
    }

    public MemoryItemResponse rejectMemory(String userId, String memoryId) {
        MemoryItemResponse response = pythonWebClient.post()
                .uri("/memory/{userId}/{memoryId}/reject", userId, memoryId)
                .retrieve()
                .bodyToMono(MemoryItemResponse.class)
                .block();

        if (response == null) {
            throw new RuntimeException("Error rejecting memory!");
        }

        return response;
    }

    public MemoryItemResponse editMemory(String userId, String memoryId, MemoryEditRequest request) {
        MemoryItemResponse response = pythonWebClient.patch()
                .uri("/memory/{userId}/{memoryId}", userId, memoryId)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(MemoryItemResponse.class)
                .block();

        if (response == null) {
            throw new RuntimeException("Error editing memory!");
        }

        return response;
    }

    public void deleteMemory(String userId, String memoryId) {
        pythonWebClient.delete()
                .uri("/memory/{userId}/{memoryId}", userId, memoryId)
                .retrieve()
                .bodyToMono(Void.class)
                .block();
    }

    public Map<String, Object> getMemorySettings(String userId) {
        Map<String, Object> response = pythonWebClient.get()
                .uri("/memory/settings/{userId}", userId)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                .block();

        if (response == null) {
            throw new RuntimeException("Error loading memory settings!");
        }

        return response;
    }

    public Map<String, Object> updateMemorySettings(String userId, MemorySettingsRequest request) {
        Map<String, Object> response = pythonWebClient.patch()
                .uri("/memory/settings/{userId}", userId)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                .block();

        if (response == null) {
            throw new RuntimeException("Error updating memory settings!");
        }

        return response;
    }
}
