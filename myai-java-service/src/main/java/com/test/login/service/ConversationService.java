package com.test.login.service;

import com.test.login.dto.ChatHistoryMessage;
import com.test.login.dto.ConversationDetailResponse;
import com.test.login.dto.ConversationSummaryResponse;
import com.test.login.model.ChatMessage;
import com.test.login.model.Conversation;
import com.test.login.model.User;
import com.test.login.repository.ChatMessageRepository;
import com.test.login.repository.ConversationRepository;
import jakarta.transaction.Transactional;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;

import static org.springframework.http.HttpStatus.NOT_FOUND;

@Service
public class ConversationService {
    private static final DateTimeFormatter FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final ConversationRepository conversationRepository;
    private final ChatMessageRepository chatMessageRepository;

    public ConversationService(ConversationRepository conversationRepository, ChatMessageRepository chatMessageRepository) {
        this.conversationRepository = conversationRepository;
        this.chatMessageRepository = chatMessageRepository;
    }

    @Transactional
    public Conversation getOrCreateConversation(User user, Long conversationId, String firstMessage) {
        if (conversationId != null) {
            return conversationRepository.findByIdAndUserId(conversationId, user.getId())
                    .orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "Conversation not found"));
        }

        Conversation conversation = new Conversation();
        conversation.setUser(user);
        conversation.setTitle(buildTitle(firstMessage));
        return conversationRepository.save(conversation);
    }

    public List<ChatMessage> listMessages(Long conversationId) {
        return chatMessageRepository.findByConversationIdOrderByCreatedAtAsc(conversationId);
    }

    @Transactional
    public ChatMessage saveMessage(Conversation conversation, String role, String content) {
        return saveMessage(conversation, role, content, null, null, null);
    }

    @Transactional
    public ChatMessage saveMessage(
            Conversation conversation,
            String role,
            String content,
            User requestUser,
            String idempotencyKey,
            String agentRunId
    ) {
        String keyHash = hashIdempotencyKey(idempotencyKey);
        if (requestUser != null && keyHash != null) {
            Optional<ChatMessage> existing = chatMessageRepository
                    .findByRequestUserIdAndRoleAndIdempotencyKeyHash(requestUser.getId(), role, keyHash);
            if (existing.isPresent()) {
                ChatMessage message = existing.get();
                if (!message.getContent().equals(content)) {
                    throw new ResponseStatusException(
                            org.springframework.http.HttpStatus.CONFLICT,
                            "Idempotency key is already bound to a different chat message"
                    );
                }
                return message;
            }
        }
        ChatMessage message = new ChatMessage();
        message.setConversation(conversation);
        message.setRole(role);
        message.setContent(content);
        message.setRequestUserId(requestUser == null ? null : requestUser.getId());
        message.setIdempotencyKeyHash(keyHash);
        message.setAgentRunId(agentRunId);
        ChatMessage saved = chatMessageRepository.saveAndFlush(message);
        conversation.setUpdatedAt(LocalDateTime.now());
        if ((conversation.getTitle() == null || conversation.getTitle().isBlank()) && "user".equals(role)) {
            conversation.setTitle(buildTitle(content));
        }
        conversationRepository.save(conversation);
        return saved;
    }

    public Optional<ChatMessage> findIdempotentMessage(User user, String role, String idempotencyKey) {
        String keyHash = hashIdempotencyKey(idempotencyKey);
        if (user == null || keyHash == null) {
            return Optional.empty();
        }
        return chatMessageRepository.findByRequestUserIdAndRoleAndIdempotencyKeyHash(
                user.getId(), role, keyHash
        );
    }

    public List<ConversationSummaryResponse> listConversations(User user) {
        return conversationRepository.findByUserIdOrderByUpdatedAtDesc(user.getId()).stream()
                .map(conversation -> {
                    ConversationSummaryResponse item = new ConversationSummaryResponse();
                    item.setId(conversation.getId());
                    item.setTitle(conversation.getTitle());
                    item.setCreatedAt(format(conversation.getCreatedAt()));
                    item.setUpdatedAt(format(conversation.getUpdatedAt()));
                    List<ChatMessage> messages = listMessages(conversation.getId());
                    String preview = messages.isEmpty() ? "" : messages.get(messages.size() - 1).getContent();
                    item.setLastMessagePreview(truncate(preview, 60));
                    return item;
                })
                .toList();
    }

    public ConversationDetailResponse getConversationDetail(User user, Long conversationId) {
        Conversation conversation = conversationRepository.findByIdAndUserId(conversationId, user.getId())
                .orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "Conversation not found"));
        List<ChatHistoryMessage> messages = listMessages(conversationId).stream()
                .map(this::toHistoryMessage)
                .toList();

        ConversationDetailResponse detail = new ConversationDetailResponse();
        detail.setId(conversation.getId());
        detail.setTitle(conversation.getTitle());
        detail.setCreatedAt(format(conversation.getCreatedAt()));
        detail.setUpdatedAt(format(conversation.getUpdatedAt()));
        detail.setMessages(messages);
        return detail;
    }

    public List<ChatHistoryMessage> recentHistory(Long conversationId, int maxMessages) {
        List<ChatMessage> all = listMessages(conversationId);
        int start = Math.max(0, all.size() - maxMessages);
        return all.subList(start, all.size()).stream().map(this::toHistoryMessage).toList();
    }

    public List<ChatHistoryMessage> recentHistoryExcludingIdempotencyKey(
            Long conversationId,
            int maxMessages,
            String idempotencyKey
    ) {
        String keyHash = hashIdempotencyKey(idempotencyKey);
        List<ChatMessage> all = listMessages(conversationId).stream()
                .filter(message -> keyHash == null || !keyHash.equals(message.getIdempotencyKeyHash()))
                .toList();
        int start = Math.max(0, all.size() - maxMessages);
        return all.subList(start, all.size()).stream().map(this::toHistoryMessage).toList();
    }

    @Transactional
    public void deleteConversation(User user, Long conversationId) {
        Conversation conversation = conversationRepository.findByIdAndUserId(conversationId, user.getId())
                .orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "Conversation not found"));
        List<ChatMessage> messages = listMessages(conversationId);
        chatMessageRepository.deleteAll(messages);
        conversationRepository.delete(conversation);
    }

    public String exportConversation(User user, Long conversationId) {
        ConversationDetailResponse detail = getConversationDetail(user, conversationId);
        StringBuilder builder = new StringBuilder();
        builder.append("# ").append(detail.getTitle()).append("\n\n");
        for (ChatHistoryMessage message : detail.getMessages()) {
            String role = "user".equals(message.getRole()) ? "User" : "Assistant";
            builder.append("[").append(message.getCreatedAt()).append("] ").append(role).append(":\n");
            builder.append(message.getContent()).append("\n\n");
        }
        return builder.toString();
    }

    private ChatHistoryMessage toHistoryMessage(ChatMessage message) {
        ChatHistoryMessage item = new ChatHistoryMessage(message.getRole(), message.getContent());
        item.setCreatedAt(format(message.getCreatedAt()));
        return item;
    }

    private String buildTitle(String firstMessage) {
        String compact = firstMessage == null ? "" : firstMessage.trim().replaceAll("\\s+", " ");
        if (compact.isBlank()) {
            return "新会话";
        }
        return truncate(compact, 24);
    }

    private String truncate(String text, int maxLength) {
        if (text == null || text.length() <= maxLength) {
            return text == null ? "" : text;
        }
        return text.substring(0, maxLength) + "...";
    }

    private String format(LocalDateTime time) {
        return time == null ? "" : time.format(FORMATTER);
    }

    private String hashIdempotencyKey(String idempotencyKey) {
        if (idempotencyKey == null || idempotencyKey.isBlank()) {
            return null;
        }
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(idempotencyKey.trim().getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
