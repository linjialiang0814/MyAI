package com.test.login.service;

import com.test.login.dto.KnowledgeFileResponse;
import com.test.login.dto.KnowledgeMaintenanceRequest;
import com.test.login.dto.KnowledgeQARequest;
import com.test.login.dto.KnowledgeQAResponse;
import com.test.login.dto.KnowledgeQueryRequest;
import com.test.login.dto.KnowledgeQueryResponse;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.client.WebClient;

import java.io.IOException;
import java.util.List;
import java.util.Map;

@Service
public class PythonKnowledgeService {
    private final WebClient pythonWebClient;

    public PythonKnowledgeService(WebClient pythonWebClient) {
        this.pythonWebClient = pythonWebClient;
    }

    public KnowledgeFileResponse uploadKnowledge(String userId, MultipartFile file) throws IOException {
        MultipartBodyBuilder builder = new MultipartBodyBuilder();
        builder.part("user_id", userId);
        builder.part("file", new NamedByteArrayResource(file.getBytes(), file.getOriginalFilename()))
                .contentType(resolveContentType(file.getContentType()));

        KnowledgeFileResponse response = pythonWebClient.post()
                .uri("/knowledge/upload")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .bodyValue(builder.build())
                .retrieve()
                .bodyToMono(KnowledgeFileResponse.class)
                .block();

        if (response == null) {
            throw new RuntimeException("Error uploading knowledge file");
        }
        return response;
    }

    public KnowledgeQueryResponse queryKnowledge(KnowledgeQueryRequest request) {
        KnowledgeQueryResponse response = pythonWebClient.post()
                .uri("/knowledge/query")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(KnowledgeQueryResponse.class)
                .block();

        if (response == null) {
            throw new RuntimeException("Error querying knowledge base");
        }
        return response;
    }

    public KnowledgeQAResponse answerDocumentQuestion(KnowledgeQARequest request) {
        KnowledgeQAResponse response = pythonWebClient.post()
                .uri("/knowledge/qa")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(KnowledgeQAResponse.class)
                .block();

        if (response == null) {
            throw new RuntimeException("Error answering knowledge document question");
        }
        return response;
    }

    public Map<String, Object> maintain(KnowledgeMaintenanceRequest request) {
        Map<String, Object> response = pythonWebClient.post()
                .uri("/knowledge/maintenance")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                .block();

        if (response == null) {
            throw new RuntimeException("Error maintaining knowledge base");
        }
        return response;
    }

    public List<KnowledgeFileResponse> listFiles(String userId) {
        List<KnowledgeFileResponse> response = pythonWebClient.get()
                .uri("/knowledge/files/{userId}", userId)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<List<KnowledgeFileResponse>>() {})
                .block();

        if (response == null) {
            throw new RuntimeException("Error listing knowledge files");
        }
        return response;
    }

    public Map<String, Object> deleteFile(String userId, String fileId) {
        Map<String, Object> response = pythonWebClient.delete()
                .uri("/knowledge/files/{userId}/{fileId}", userId, fileId)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                .block();

        if (response == null) {
            throw new RuntimeException("Error deleting knowledge file");
        }
        return response;
    }

    private MediaType resolveContentType(String contentType) {
        if (contentType == null || contentType.isBlank()) {
            return MediaType.APPLICATION_OCTET_STREAM;
        }
        return MediaType.parseMediaType(contentType);
    }

    private static class NamedByteArrayResource extends ByteArrayResource {
        private final String filename;

        private NamedByteArrayResource(byte[] byteArray, String filename) {
            super(byteArray);
            this.filename = filename;
        }

        @Override
        public String getFilename() {
            return filename;
        }
    }
}
