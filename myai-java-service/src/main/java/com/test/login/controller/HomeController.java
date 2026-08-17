package com.test.login.controller;

import com.test.login.model.User;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

import java.time.format.DateTimeFormatter;

@Controller
public class HomeController {

    @GetMapping("/home")
    public String home(@AuthenticationPrincipal User user, Model model) {
        model.addAttribute("user", user);

        String formattedCreateTime = "";
        if (user != null && user.getCreateTime() != null) {
            formattedCreateTime = user.getCreateTime()
                    .format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        }
        model.addAttribute("formattedCreateTime", formattedCreateTime);

        return "home";
    }
}

