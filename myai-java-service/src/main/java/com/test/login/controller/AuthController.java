package com.test.login.controller;

import com.test.login.model.User;
import com.test.login.service.UserService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

@Controller
public class AuthController {

    private final UserService userService;
    private final String authMode;

    public AuthController(UserService userService,
                          @Value("${myai.auth.mode:form}") String authMode) {
        this.userService = userService;
        this.authMode = authMode;
    }

    @GetMapping("/login")
    public String loginPage() {
        if ("local".equalsIgnoreCase(authMode)) {
            return "redirect:/home";
        }
        return "login";
    }

    @GetMapping("/register")
    public String registerPage() {
        return "register";
    }

    @PostMapping("/register")
    public String doRegister(@RequestParam String username,
                             @RequestParam String password,
                             @RequestParam String email,
                             Model model) {
        if (userService.existsByUsername(username)) {
            model.addAttribute("error", "用户名已存在");
            return "register";
        }

        if (userService.existsByEmail(email)) {
            model.addAttribute("error", "邮箱已被注册");
            return "register";
        }

        User user = new User();
        user.setUsername(username);
        user.setPassword(password);
        user.setEmail(email);

        userService.register(user);
        model.addAttribute("message", "注册成功，请登录");
        return "login";
    }
}
