package com.test.login.service;

import com.test.login.dto.ChatRequest;
import com.test.login.dto.ChatResponse;
import com.test.login.dto.ChatHistoryMessage;
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;

@Service
public class PythonLLMService {
    private final WebClient webClient;
    private final Duration requestTimeout;

    public PythonLLMService(
            WebClient pythonWebClient,
            @Value("${python.service.request-timeout-seconds:160}") long requestTimeoutSeconds
    ) {
        this.webClient = pythonWebClient;
        this.requestTimeout = Duration.ofSeconds(requestTimeoutSeconds);
    }
    public ChatResponse chat(
            String userId,
            String message,
            Long conversationId,
            java.util.List<ChatHistoryMessage> history,
            String idempotencyKey
    ) {
        ChatRequest request = new ChatRequest(userId, message);
        request.setConversationId(conversationId);
        request.setHistory(history);
        request.setIdempotencyKey(idempotencyKey);

        ChatResponse response = webClient
                .post()
                .uri("/chat")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(ChatResponse.class)
                .block(requestTimeout);

        if (response == null) {
            throw new RuntimeException("Error generating response!");
        }
        return response;
    }
}
