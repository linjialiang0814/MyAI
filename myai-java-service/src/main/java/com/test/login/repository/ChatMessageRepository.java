package com.test.login.repository;

import com.test.login.model.ChatMessage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.EntityGraph;

import java.util.List;
import java.util.Optional;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, Long> {
    List<ChatMessage> findByConversationIdOrderByCreatedAtAsc(Long conversationId);

    @EntityGraph(attributePaths = "conversation")
    Optional<ChatMessage> findByRequestUserIdAndRoleAndIdempotencyKeyHash(
            Long requestUserId,
            String role,
            String idempotencyKeyHash
    );
}
