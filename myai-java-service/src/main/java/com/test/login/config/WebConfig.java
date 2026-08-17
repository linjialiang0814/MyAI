package com.test.login.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ViewControllerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer {
    private final String authMode;

    public WebConfig(@Value("${myai.auth.mode:form}") String authMode) {
        this.authMode = authMode;
    }

    @Override
    public void addViewControllers(ViewControllerRegistry registry) {
        String target = "local".equalsIgnoreCase(authMode) ? "redirect:/home" : "redirect:/login";
        registry.addViewController("/").setViewName(target);
    }
}
