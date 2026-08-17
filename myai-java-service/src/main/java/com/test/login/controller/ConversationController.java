package com.test.login.controller;

import com.test.login.dto.ConversationDetailResponse;
import com.test.login.dto.ConversationSummaryResponse;
import com.test.login.model.User;
import com.test.login.service.ConversationService;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.util.List;

@RestController
@RequestMapping("/conversations")
public class ConversationController {
    private final ConversationService conversationService;

    public ConversationController(ConversationService conversationService) {
        this.conversationService = conversationService;
    }

    @GetMapping
    public List<ConversationSummaryResponse> listConversations(@AuthenticationPrincipal User user) {
        return conversationService.listConversations(user);
    }

    @GetMapping("/{conversationId}")
    public ConversationDetailResponse getConversation(@PathVariable Long conversationId,
                                                      @AuthenticationPrincipal User user) {
        return conversationService.getConversationDetail(user, conversationId);
    }

    @DeleteMapping("/{conversationId}")
    public void deleteConversation(@PathVariable Long conversationId,
                                   @AuthenticationPrincipal User user) {
        conversationService.deleteConversation(user, conversationId);
    }

    @GetMapping("/{conversationId}/export")
    public ResponseEntity<byte[]> exportConversation(@PathVariable Long conversationId,
                                                     @AuthenticationPrincipal User user) {
        String content = conversationService.exportConversation(user, conversationId);
        byte[] data = content.getBytes(StandardCharsets.UTF_8);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("text/markdown"))
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"conversation-" + conversationId + ".md\"")
                .body(data);
    }
}
