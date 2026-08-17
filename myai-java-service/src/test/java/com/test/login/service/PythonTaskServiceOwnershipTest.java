package com.test.login.service;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class PythonTaskServiceOwnershipTest {

    @Test
    void shouldSendOwnerAndAcceptMatchingTaskRun() {
        AtomicReference<ClientRequest> capturedRequest = new AtomicReference<>();
        WebClient webClient = webClientReturning(
                "{\"task_run_id\":\"run-1\",\"user_id\":\"owner\"}",
                capturedRequest
        );
        PythonTaskService service = new PythonTaskService(webClient);

        StepVerifier.create(service.getTaskRun("run-1", "owner"))
                .assertNext(run -> assertEquals("run-1", run.get("task_run_id")))
                .verifyComplete();

        assertNotNull(capturedRequest.get());
        assertEquals(HttpMethod.GET, capturedRequest.get().method());
        assertEquals("user_id=owner", capturedRequest.get().url().getQuery());
    }

    @Test
    void shouldRejectMismatchedOwnerBeforeCancellationRequest() {
        AtomicInteger callCount = new AtomicInteger();
        WebClient webClient = WebClient.builder()
                .exchangeFunction(request -> {
                    callCount.incrementAndGet();
                    return Mono.just(jsonResponse(
                            "{\"task_run_id\":\"run-1\",\"user_id\":\"someone-else\"}"
                    ));
                })
                .build();
        PythonTaskService service = new PythonTaskService(webClient);

        StepVerifier.create(service.cancelTaskRun("run-1", "owner"))
                .verifyComplete();

        assertEquals(1, callCount.get());
    }

    @Test
    void shouldFilterUnexpectedForeignRunsFromListResponse() {
        AtomicReference<ClientRequest> capturedRequest = new AtomicReference<>();
        WebClient webClient = webClientReturning(
                "{\"runs\":[{\"task_run_id\":\"owned\",\"user_id\":\"owner\"},{\"task_run_id\":\"foreign\",\"user_id\":\"someone-else\"}]}",
                capturedRequest
        );
        PythonTaskService service = new PythonTaskService(webClient);

        StepVerifier.create(service.listTaskRuns("owner", 20))
                .assertNext(payload -> {
                    var runs = (java.util.List<?>) payload.get("runs");
                    assertEquals(1, runs.size());
                    assertEquals("owned", ((java.util.Map<?, ?>) runs.get(0)).get("task_run_id"));
                })
                .verifyComplete();

        assertNotNull(capturedRequest.get());
        assertEquals("user_id=owner&limit=20", capturedRequest.get().url().getQuery());
    }

    private static WebClient webClientReturning(String body, AtomicReference<ClientRequest> capturedRequest) {
        return WebClient.builder()
                .exchangeFunction(request -> {
                    capturedRequest.set(request);
                    return Mono.just(jsonResponse(body));
                })
                .build();
    }

    private static ClientResponse jsonResponse(String body) {
        return ClientResponse.create(HttpStatus.OK)
                .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .body(body)
                .build();
    }
}
