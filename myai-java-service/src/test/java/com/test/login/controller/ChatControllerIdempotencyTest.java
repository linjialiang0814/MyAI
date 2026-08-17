package com.test.login.controller;

import com.test.login.dto.ChatRequest;
import com.test.login.dto.ChatResponse;
import com.test.login.model.ChatMessage;
import com.test.login.model.Conversation;
import com.test.login.model.User;
import com.test.login.service.ConversationService;
import com.test.login.service.PythonLLMService;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ChatControllerIdempotencyTest {

    @Test
    void shouldPersistOneLogicalUserAndAssistantMessageWithIdempotencyKey() {
        PythonLLMService python = mock(PythonLLMService.class);
        ConversationService conversations = mock(ConversationService.class);
        ChatController controller = new ChatController(python, conversations);
        User user = user(7L);
        Conversation conversation = conversation(42L, user);
        ChatRequest request = new ChatRequest(null, "hello");
        request.setConversationId(42L);
        request.setIdempotencyKey("request-42");

        when(conversations.findIdempotentMessage(user, "assistant", "request-42"))
                .thenReturn(Optional.empty());
        when(conversations.findIdempotentMessage(user, "user", "request-42"))
                .thenReturn(Optional.empty());
        when(conversations.getOrCreateConversation(user, 42L, "hello"))
                .thenReturn(conversation);
        when(conversations.recentHistory(42L, 12)).thenReturn(List.of());
        ChatMessage storedUser = message(conversation, "user", "hello", null);
        when(conversations.saveMessage(conversation, "user", "hello", user, "request-42", null))
                .thenReturn(storedUser);
        ChatResponse pythonResponse = new ChatResponse();
        pythonResponse.setReply("world");
        pythonResponse.setRunId("agent-42");
        when(python.chat("7", "hello", 42L, List.of(), "request-42"))
                .thenReturn(pythonResponse);
        ChatMessage storedAssistant = message(conversation, "assistant", "world", "agent-42");
        when(conversations.saveMessage(
                conversation, "assistant", "world", user, "request-42", "agent-42"
        )).thenReturn(storedAssistant);

        ChatResponse response = controller.chat(request, "request-42", user);

        assertEquals("world", response.getReply());
        assertEquals("agent-42", response.getRunId());
        assertEquals(42L, response.getConversationId());
        verify(python).chat("7", "hello", 42L, List.of(), "request-42");
        verify(conversations).saveMessage(
                conversation, "user", "hello", user, "request-42", null
        );
        verify(conversations).saveMessage(
                conversation, "assistant", "world", user, "request-42", "agent-42"
        );
    }

    @Test
    void shouldReplayStoredAssistantWithoutCallingPythonOrWritingMessages() {
        PythonLLMService python = mock(PythonLLMService.class);
        ConversationService conversations = mock(ConversationService.class);
        ChatController controller = new ChatController(python, conversations);
        User user = user(7L);
        Conversation conversation = conversation(42L, user);
        ChatMessage storedUser = message(conversation, "user", "hello", null);
        ChatMessage storedAssistant = message(conversation, "assistant", "cached", "agent-cached");
        when(conversations.findIdempotentMessage(user, "assistant", "request-42"))
                .thenReturn(Optional.of(storedAssistant));
        when(conversations.findIdempotentMessage(user, "user", "request-42"))
                .thenReturn(Optional.of(storedUser));
        ChatRequest request = new ChatRequest(null, "hello");
        request.setIdempotencyKey("request-42");

        ChatResponse response = controller.chat(request, "request-42", user);

        assertEquals("cached", response.getReply());
        assertEquals("agent-cached", response.getRunId());
        assertEquals(42L, response.getConversationId());
        verify(python, never()).chat(any(), any(), any(), any(), any());
        verify(conversations, never()).saveMessage(any(), any(), any(), any(), any(), any());
    }

    @Test
    void shouldRejectCompletedKeyReusedForDifferentMessage() {
        PythonLLMService python = mock(PythonLLMService.class);
        ConversationService conversations = mock(ConversationService.class);
        ChatController controller = new ChatController(python, conversations);
        User user = user(7L);
        Conversation conversation = conversation(42L, user);
        ChatMessage storedUser = message(conversation, "user", "original", null);
        ChatMessage storedAssistant = message(conversation, "assistant", "cached", "agent-cached");
        when(conversations.findIdempotentMessage(user, "assistant", "request-42"))
                .thenReturn(Optional.of(storedAssistant));
        when(conversations.findIdempotentMessage(user, "user", "request-42"))
                .thenReturn(Optional.of(storedUser));
        ChatRequest request = new ChatRequest(null, "different");
        request.setConversationId(42L);
        request.setIdempotencyKey("request-42");

        ResponseStatusException error = assertThrows(
                ResponseStatusException.class,
                () -> controller.chat(request, "request-42", user)
        );

        assertEquals(409, error.getStatusCode().value());
        verify(python, never()).chat(any(), any(), any(), any(), any());
        verify(conversations, never()).saveMessage(any(), any(), any(), any(), any(), any());
    }

    private static User user(Long id) {
        User user = new User();
        user.setId(id);
        return user;
    }

    private static Conversation conversation(Long id, User user) {
        Conversation conversation = new Conversation();
        conversation.setId(id);
        conversation.setUser(user);
        return conversation;
    }

    private static ChatMessage message(
            Conversation conversation,
            String role,
            String content,
            String agentRunId
    ) {
        ChatMessage message = new ChatMessage();
        message.setConversation(conversation);
        message.setRole(role);
        message.setContent(content);
        message.setAgentRunId(agentRunId);
        return message;
    }
}
