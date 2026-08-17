package com.test.login.controller;

import com.test.login.config.SecurityConfig;
import com.test.login.config.PasswordConfig;
import com.test.login.model.User;
import com.test.login.service.CustomUserDetailsService;
import com.test.login.service.LocalUserService;
import com.test.login.service.UserService;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.model;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.view;

@WebMvcTest(AuthController.class)
@Import({SecurityConfig.class, PasswordConfig.class})
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private UserService userService;

    @MockitoBean
    private CustomUserDetailsService customUserDetailsService;

    @MockitoBean
    private LocalUserService localUserService;

    @Test
    void shouldRenderLoginPage() throws Exception {
        mockMvc.perform(get("/login"))
                .andExpect(status().isOk())
                .andExpect(view().name("login"));
    }

    @Test
    void shouldRedirectLoginToHomeInLocalMode() throws Exception {
        AuthController controller = new AuthController(userService, "local");

        assertThat(controller.loginPage()).isEqualTo("redirect:/home");
    }

    @Test
    void shouldRenderRegisterPage() throws Exception {
        mockMvc.perform(get("/register"))
                .andExpect(status().isOk())
                .andExpect(view().name("register"));
    }

    @Test
    void shouldServeHomeAssetsWithoutAuthentication() throws Exception {
        mockMvc.perform(get("/css/home.css"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("#main-interface")));

        mockMvc.perform(get("/js/home/app.js"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("DOMContentLoaded")));
    }

    @Test
    void shouldRegisterUserSuccessfully() throws Exception {
        when(userService.existsByUsername("alice")).thenReturn(false);
        when(userService.existsByEmail("alice@example.com")).thenReturn(false);

        mockMvc.perform(post("/register")
                        .with(csrf())
                        .param("username", "alice")
                        .param("password", "Password123")
                        .param("email", "alice@example.com"))
                .andExpect(status().isOk())
                .andExpect(view().name("login"))
                .andExpect(model().attribute("message", "注册成功，请登录"));

        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        verify(userService).register(userCaptor.capture());
        assertThat(userCaptor.getValue().getUsername()).isEqualTo("alice");
        assertThat(userCaptor.getValue().getEmail()).isEqualTo("alice@example.com");
        assertThat(userCaptor.getValue().getPassword()).isEqualTo("Password123");
    }

    @Test
    void shouldRejectDuplicateUsername() throws Exception {
        when(userService.existsByUsername("alice")).thenReturn(true);

        mockMvc.perform(post("/register")
                        .with(csrf())
                        .param("username", "alice")
                        .param("password", "Password123")
                        .param("email", "alice@example.com"))
                .andExpect(status().isOk())
                .andExpect(view().name("register"))
                .andExpect(model().attribute("error", "用户名已存在"));

        verify(userService, never()).register(any(User.class));
    }
}
