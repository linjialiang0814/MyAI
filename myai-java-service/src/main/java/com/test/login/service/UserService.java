package com.test.login.service;

import com.test.login.model.User;

public interface UserService {
    User register(User user);
    boolean existsByUsername(String username);
    boolean existsByEmail(String email);
}
