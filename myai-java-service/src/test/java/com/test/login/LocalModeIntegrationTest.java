package com.test.login;

import com.test.login.model.User;
import com.test.login.repository.UserRepository;
import com.test.login.service.LocalUserService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;

import static org.assertj.core.api.Assertions.assertThat;

@ActiveProfiles("local")
@SpringBootTest
@TestPropertySource(properties = {
        "spring.datasource.url=jdbc:sqlite:file:myai-local-test?mode=memory&cache=shared",
        "spring.jpa.hibernate.ddl-auto=create-drop"
})
class LocalModeIntegrationTest {

    @Autowired
    private LocalUserService localUserService;

    @Autowired
    private UserRepository userRepository;

    @Test
    void shouldCreateAndReuseLocalUser() {
        User first = localUserService.getOrCreateLocalUser();
        User second = localUserService.getOrCreateLocalUser();

        assertThat(first.getId()).isNotNull();
        assertThat(second.getId()).isEqualTo(first.getId());
        assertThat(userRepository.findByUsername("local-user")).isPresent();
    }
}
