package com.test.login.controller;

import com.test.login.dto.ChatRequest;
import com.test.login.dto.ChatResponse;
import com.test.login.model.Conversation;
import com.test.login.model.User;
import com.test.login.service.ConversationService;
import com.test.login.service.PythonLLMService;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.Objects;

import static org.springframework.http.HttpStatus.BAD_REQUEST;
import static org.springframework.http.HttpStatus.CONFLICT;

@RestController
@RequestMapping("/chat")
public class ChatController {
    private final PythonLLMService pythonLLMService;
    private final ConversationService conversationService;

    public ChatController(PythonLLMService pythonLLMService, ConversationService conversationService) {
        this.pythonLLMService = pythonLLMService;
        this.conversationService = conversationService;
    }

    @PostMapping
    public ChatResponse chat(@RequestBody ChatRequest request,
                             @RequestHeader(name = "Idempotency-Key", required = false) String idempotencyHeader,
                             @AuthenticationPrincipal User user) {
        String bodyKey = normalizeIdempotencyKey(request.getIdempotencyKey());
        String headerKey = normalizeIdempotencyKey(idempotencyHeader);
        if (bodyKey != null && headerKey != null && !bodyKey.equals(headerKey)) {
            throw new ResponseStatusException(BAD_REQUEST, "Idempotency key header and body value differ");
        }
        String idempotencyKey = headerKey != null ? headerKey : bodyKey;
        if (idempotencyKey != null && idempotencyKey.length() > 256) {
            throw new ResponseStatusException(BAD_REQUEST, "Idempotency key must not exceed 256 characters");
        }

        if (idempotencyKey != null) {
            var completed = conversationService.findIdempotentMessage(user, "assistant", idempotencyKey);
            if (completed.isPresent()) {
                var storedUser = conversationService.findIdempotentMessage(user, "user", idempotencyKey)
                        .orElseThrow(() -> new ResponseStatusException(
                                CONFLICT,
                                "Idempotency key has an incomplete persisted chat request"
                        ));
                validateStoredUserRequest(request, storedUser);
                if (!Objects.equals(
                        storedUser.getConversation().getId(),
                        completed.get().getConversation().getId()
                )) {
                    throw new ResponseStatusException(
                            CONFLICT,
                            "Idempotency key is bound to inconsistent conversation records"
                    );
                }
                return responseFromStored(completed.get());
            }
        }

        Conversation conversation;
        java.util.List<com.test.login.dto.ChatHistoryMessage> history;
        var existingUserMessage = idempotencyKey == null
                ? java.util.Optional.<com.test.login.model.ChatMessage>empty()
                : conversationService.findIdempotentMessage(user, "user", idempotencyKey);
        if (existingUserMessage.isPresent()) {
            validateStoredUserRequest(request, existingUserMessage.get());
            conversation = existingUserMessage.get().getConversation();
            history = conversationService.recentHistoryExcludingIdempotencyKey(
                    conversation.getId(), 12, idempotencyKey
            );
        } else {
            conversation = conversationService.getOrCreateConversation(
                    user,
                    request.getConversationId(),
                    request.getMessage()
            );
            history = conversationService.recentHistory(conversation.getId(), 12);
            try {
                conversationService.saveMessage(
                        conversation,
                        "user",
                        request.getMessage(),
                        user,
                        idempotencyKey,
                        null
                );
            } catch (DataIntegrityViolationException race) {
                var winner = conversationService.findIdempotentMessage(user, "user", idempotencyKey)
                        .orElseThrow(() -> race);
                validateStoredUserRequest(request, winner);
                conversation = winner.getConversation();
                history = conversationService.recentHistoryExcludingIdempotencyKey(
                        conversation.getId(), 12, idempotencyKey
                );
            }
        }
        ChatResponse pythonResponse = pythonLLMService.chat(
                String.valueOf(user.getId()),
                request.getMessage(),
                conversation.getId(),
                history,
                idempotencyKey
        );
        String reply = pythonResponse.getReply();
        com.test.login.model.ChatMessage storedAssistant;
        try {
            storedAssistant = conversationService.saveMessage(
                    conversation,
                    "assistant",
                    reply,
                    user,
                    idempotencyKey,
                    pythonResponse.getRunId()
            );
        } catch (DataIntegrityViolationException race) {
            storedAssistant = conversationService.findIdempotentMessage(user, "assistant", idempotencyKey)
                    .orElseThrow(() -> race);
        }

        ChatResponse response = new ChatResponse();
        response.setReply(storedAssistant.getContent());
        response.setRunId(storedAssistant.getAgentRunId());
        response.setTrace(pythonResponse.getTrace());
        response.setConversationId(conversation.getId());
        return response;
    }

    private ChatResponse responseFromStored(com.test.login.model.ChatMessage message) {
        ChatResponse response = new ChatResponse();
        response.setReply(message.getContent());
        response.setRunId(message.getAgentRunId());
        response.setConversationId(message.getConversation().getId());
        return response;
    }

    private void validateStoredUserRequest(
            ChatRequest request,
            com.test.login.model.ChatMessage storedUser
    ) {
        if (!Objects.equals(storedUser.getContent(), request.getMessage())) {
            throw new ResponseStatusException(
                    CONFLICT,
                    "Idempotency key is already bound to a different chat request"
            );
        }
        if (request.getConversationId() != null
                && !request.getConversationId().equals(storedUser.getConversation().getId())) {
            throw new ResponseStatusException(
                    CONFLICT,
                    "Idempotency key is already bound to a different conversation"
            );
        }
    }

    private String normalizeIdempotencyKey(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

}
