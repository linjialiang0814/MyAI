package com.test.login.controller;

import com.test.login.config.PasswordConfig;
import com.test.login.config.SecurityConfig;
import com.test.login.dto.TaskResponse;
import com.test.login.model.User;
import com.test.login.service.CustomUserDetailsService;
import com.test.login.service.ConversationService;
import com.test.login.service.LocalUserService;
import com.test.login.service.PythonTaskService;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.asyncDispatch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.junit.jupiter.api.Assertions.assertEquals;

@WebMvcTest(TaskController.class)
@Import({SecurityConfig.class, PasswordConfig.class})
@TestPropertySource(properties = "myai.auth.mode=local")
class TaskControllerLocalModeTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private PythonTaskService pythonTaskService;

    @MockitoBean
    private ConversationService conversationService;

    @MockitoBean
    private CustomUserDetailsService customUserDetailsService;

    @MockitoBean
    private LocalUserService localUserService;

    @Test
    void shouldListTaskRunsAsJsonInLocalMode() throws Exception {
        when(localUserService.getOrCreateLocalUser()).thenReturn(localUser());
        when(pythonTaskService.listTaskRuns("1", 20)).thenReturn(Mono.just(Map.of(
                "runs", List.of(Map.of("task_run_id", "run-1", "status", "succeeded"))
        )));

        var result = mockMvc.perform(get("/task/runs?limit=20"))
                .andExpect(status().isOk())
                .andExpect(request().asyncStarted())
                .andReturn();

        mockMvc.perform(asyncDispatch(result))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("application/json"))
                .andExpect(jsonPath("$.runs[0].task_run_id").value("run-1"));
    }

    @Test
    void shouldExecuteTaskAsJsonInLocalMode() throws Exception {
        when(localUserService.getOrCreateLocalUser()).thenReturn(localUser());
        TaskResponse response = new TaskResponse();
        response.setTaskRunId("run-2");
        response.setStatus("succeeded");
        response.setContent("check current system info");
        response.setSuccess(true);
        when(pythonTaskService.getTask(any())).thenReturn(Mono.just(response));

        var result = mockMvc.perform(post("/task")
                        .with(csrf())
                        .contentType("application/json")
                        .content("{\"content\":\"check current system info\"}"))
                .andExpect(status().isOk())
                .andExpect(request().asyncStarted())
                .andReturn();

        mockMvc.perform(asyncDispatch(result))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("application/json"))
                .andExpect(jsonPath("$.task_run_id").value("run-2"))
                .andExpect(jsonPath("$.success").value(true));
    }

    @Test
    void shouldValidateAndForwardRuntimeLinkFields() throws Exception {
        when(localUserService.getOrCreateLocalUser()).thenReturn(localUser());
        TaskResponse response = new TaskResponse();
        response.setTaskRunId("run-linked");
        response.setStatus("succeeded");
        response.setContent("linked task");
        response.setSuccess(true);
        when(pythonTaskService.getTask(any())).thenReturn(Mono.just(response));

        var result = mockMvc.perform(post("/task")
                        .with(csrf())
                        .contentType("application/json")
                        .content("{\"content\":\"linked task\",\"conversation_id\":42,"
                                + "\"agent_run_id\":\"agent-42\","
                                + "\"idempotency_key\":\"request-42\"}"))
                .andExpect(status().isOk())
                .andExpect(request().asyncStarted())
                .andReturn();

        mockMvc.perform(asyncDispatch(result)).andExpect(status().isOk());

        verify(conversationService).getConversationDetail(any(User.class), eq(42L));
        ArgumentCaptor<com.test.login.dto.TaskRequest> captor =
                ArgumentCaptor.forClass(com.test.login.dto.TaskRequest.class);
        verify(pythonTaskService).getTask(captor.capture());
        assertEquals("1", captor.getValue().getUserId());
        assertEquals(42L, captor.getValue().getConversationId());
        assertEquals("agent-42", captor.getValue().getAgentRunId());
        assertEquals("request-42", captor.getValue().getIdempotencyKey());
    }

    @Test
    void shouldFetchTaskRunForAuthenticatedLocalUser() throws Exception {
        when(localUserService.getOrCreateLocalUser()).thenReturn(localUser());
        when(pythonTaskService.getTaskRun("run-1", "1")).thenReturn(Mono.just(Map.of(
                "task_run_id", "run-1",
                "user_id", "1",
                "status", "succeeded"
        )));

        var result = mockMvc.perform(get("/task/runs/run-1"))
                .andExpect(status().isOk())
                .andExpect(request().asyncStarted())
                .andReturn();

        mockMvc.perform(asyncDispatch(result))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.task_run_id").value("run-1"));
        verify(pythonTaskService).getTaskRun("run-1", "1");
    }

    @Test
    void shouldCancelTaskRunForAuthenticatedLocalUser() throws Exception {
        when(localUserService.getOrCreateLocalUser()).thenReturn(localUser());
        when(pythonTaskService.cancelTaskRun("run-1", "1")).thenReturn(Mono.just(Map.of(
                "task_run_id", "run-1",
                "user_id", "1",
                "cancel_requested", true
        )));

        var result = mockMvc.perform(post("/task/runs/run-1/cancel").with(csrf()))
                .andExpect(status().isOk())
                .andExpect(request().asyncStarted())
                .andReturn();

        mockMvc.perform(asyncDispatch(result))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cancel_requested").value(true));
        verify(pythonTaskService).cancelTaskRun("run-1", "1");
    }

    @Test
    void shouldReturnNotFoundWhenTaskRunIsNotOwnedByLocalUser() throws Exception {
        when(localUserService.getOrCreateLocalUser()).thenReturn(localUser());
        when(pythonTaskService.getTaskRun("other-run", "1")).thenReturn(Mono.empty());

        var result = mockMvc.perform(get("/task/runs/other-run"))
                .andExpect(status().isOk())
                .andExpect(request().asyncStarted())
                .andReturn();

        mockMvc.perform(asyncDispatch(result))
                .andExpect(status().isNotFound());
    }

    @Test
    void shouldReturnJsonWhenPythonTaskServiceFails() throws Exception {
        when(localUserService.getOrCreateLocalUser()).thenReturn(localUser());
        when(pythonTaskService.listTaskRuns("1", 20)).thenReturn(Mono.error(new RuntimeException("task runtime unavailable")));

        var result = mockMvc.perform(get("/task/runs?limit=20"))
                .andExpect(status().isOk())
                .andExpect(request().asyncStarted())
                .andReturn();

        mockMvc.perform(asyncDispatch(result))
                .andExpect(status().isBadGateway())
                .andExpect(content().contentTypeCompatibleWith("application/json"))
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error").value("python_task_service_error"));
    }

    private static User localUser() {
        User user = new User();
        user.setId(1L);
        user.setUsername("local-user");
        user.setPassword("{noop}local");
        user.setEmail("local@myai.local");
        return user;
    }
}
