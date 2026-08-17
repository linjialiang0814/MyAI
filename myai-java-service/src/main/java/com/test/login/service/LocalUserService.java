package com.test.login.service;

import com.test.login.model.User;
import com.test.login.repository.UserRepository;
import jakarta.transaction.Transactional;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class LocalUserService {
    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final String username;
    private final String email;
    private final String password;

    public LocalUserService(
            UserRepository userRepository,
            PasswordEncoder passwordEncoder,
            @Value("${myai.local-user.username:local-user}") String username,
            @Value("${myai.local-user.email:local-user@myai.local}") String email,
            @Value("${myai.local-user.password:local-password}") String password) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.username = username;
        this.email = email;
        this.password = password;
    }

    @Transactional
    public User getOrCreateLocalUser() {
        return userRepository.findByUsername(username).orElseGet(() -> {
            User user = new User();
            user.setUsername(username);
            user.setEmail(email);
            user.setPassword(passwordEncoder.encode(password));
            return userRepository.save(user);
        });
    }
}
