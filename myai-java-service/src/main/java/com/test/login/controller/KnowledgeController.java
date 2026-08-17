package com.test.login.controller;

import com.test.login.dto.KnowledgeFileResponse;
import com.test.login.dto.KnowledgeMaintenanceRequest;
import com.test.login.dto.KnowledgeQARequest;
import com.test.login.dto.KnowledgeQAResponse;
import com.test.login.dto.KnowledgeQueryRequest;
import com.test.login.dto.KnowledgeQueryResponse;
import com.test.login.model.User;
import com.test.login.service.PythonKnowledgeService;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/knowledge")
public class KnowledgeController {
    private final PythonKnowledgeService pythonKnowledgeService;

    public KnowledgeController(PythonKnowledgeService pythonKnowledgeService) {
        this.pythonKnowledgeService = pythonKnowledgeService;
    }

    @PostMapping("/upload")
    public ResponseEntity<KnowledgeFileResponse> uploadKnowledge(@RequestParam("file") MultipartFile file,
                                                                 @AuthenticationPrincipal User user) throws IOException {
        KnowledgeFileResponse response = pythonKnowledgeService.uploadKnowledge(String.valueOf(user.getId()), file);
        return ResponseEntity.ok(response);
    }

    @PostMapping("/query")
    public ResponseEntity<KnowledgeQueryResponse> queryKnowledge(@RequestBody KnowledgeQueryRequest request,
                                                                 @AuthenticationPrincipal User user) {
        request.setUserId(String.valueOf(user.getId()));
        return ResponseEntity.ok(pythonKnowledgeService.queryKnowledge(request));
    }

    @PostMapping("/qa")
    public ResponseEntity<KnowledgeQAResponse> answerDocumentQuestion(@RequestBody KnowledgeQARequest request,
                                                                      @AuthenticationPrincipal User user) {
        request.setUserId(String.valueOf(user.getId()));
        return ResponseEntity.ok(pythonKnowledgeService.answerDocumentQuestion(request));
    }

    @PostMapping("/maintenance")
    public ResponseEntity<Map<String, Object>> maintainKnowledge(@RequestBody KnowledgeMaintenanceRequest request,
                                                                 @AuthenticationPrincipal User user) {
        request.setUserId(String.valueOf(user.getId()));
        return ResponseEntity.ok(pythonKnowledgeService.maintain(request));
    }

    @GetMapping("/files")
    public ResponseEntity<List<KnowledgeFileResponse>> listKnowledgeFiles(@AuthenticationPrincipal User user) {
        return ResponseEntity.ok(pythonKnowledgeService.listFiles(String.valueOf(user.getId())));
    }

    @DeleteMapping("/files/{fileId}")
    public ResponseEntity<Map<String, Object>> deleteKnowledgeFile(@PathVariable String fileId,
                                                                   @AuthenticationPrincipal User user) {
        return ResponseEntity.ok(pythonKnowledgeService.deleteFile(String.valueOf(user.getId()), fileId));
    }
}
