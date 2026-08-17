package com.test.login.controller;

import com.test.login.config.PasswordConfig;
import com.test.login.config.SecurityConfig;
import com.test.login.model.User;
import com.test.login.service.CustomUserDetailsService;
import com.test.login.service.LocalUserService;
import com.test.login.service.PythonMemoryService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(MemoryController.class)
@Import({SecurityConfig.class, PasswordConfig.class})
@TestPropertySource(properties = "myai.auth.mode=local")
class MemoryControllerLocalModeTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private PythonMemoryService pythonMemoryService;

    @MockitoBean
    private CustomUserDetailsService customUserDetailsService;

    @MockitoBean
    private LocalUserService localUserService;

    @Test
    void shouldQueryMemoryAsJsonInLocalMode() throws Exception {
        when(localUserService.getOrCreateLocalUser()).thenReturn(localUser());
        when(pythonMemoryService.queryMemory(any())).thenReturn(List.of("I like UESTC"));

        mockMvc.perform(post("/memory/query")
                        .with(csrf())
                        .contentType("application/json")
                        .content("{\"content\":\"UESTC\"}"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("application/json"))
                .andExpect(jsonPath("$[0]").value("I like UESTC"));
    }

    @Test
    void shouldReturnPythonWriteGovernanceResult() throws Exception {
        when(localUserService.getOrCreateLocalUser()).thenReturn(localUser());
        when(pythonMemoryService.writeMemory(any())).thenReturn(Map.of(
                "written", false,
                "reason", "writer rejected input"
        ));

        mockMvc.perform(post("/memory/write")
                        .with(csrf())
                        .contentType("application/json")
                        .content("{\"content\":\"temporary note\"}"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("application/json"))
                .andExpect(jsonPath("$.written").value(false))
                .andExpect(jsonPath("$.reason").value("writer rejected input"));
    }

    @Test
    void shouldReturnJsonWhenPythonMemoryServiceFails() throws Exception {
        when(localUserService.getOrCreateLocalUser()).thenReturn(localUser());
        when(pythonMemoryService.queryMemory(any())).thenThrow(new RuntimeException("embedding unavailable"));

        mockMvc.perform(post("/memory/query")
                        .with(csrf())
                        .contentType("application/json")
                        .content("{\"content\":\"Phoenix\"}"))
                .andExpect(status().isBadGateway())
                .andExpect(content().contentTypeCompatibleWith("application/json"))
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error").value("python_memory_service_error"));
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
