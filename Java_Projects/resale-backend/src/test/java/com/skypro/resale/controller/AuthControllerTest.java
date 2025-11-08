package com.skypro.resale.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.skypro.resale.dto.Login;
import com.skypro.resale.dto.Register;
import com.skypro.resale.dto.Role;
import com.skypro.resale.exception.UsernameNotFoundException;
import com.skypro.resale.model.User;
import com.skypro.resale.repository.UserRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@Transactional
public class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private UserRepository userRepository;
    @Autowired
    private PasswordEncoder encoder;
    @Autowired
    private ObjectMapper objectMapper;

    private final Login login = new Login();
    private final User user = new User();
    private final Register register = new Register();


    @BeforeEach
    void setUp() {
        user.setUsername("username@mail.ru");
        user.setFirstName("User");
        user.setLastName("Test");
        user.setPhone("+79609279284");
        user.setPassword(encoder.encode("password"));
        user.setRole(Role.USER);
        userRepository.save(user);

        login.setUsername("username@mail.ru");
        login.setPassword("password");

        register.setUsername("username2@mail.ru");
        register.setFirstName("User2");
        register.setLastName("Test2");
        register.setPhone("+79609279285");
        register.setPassword("password2");
        register.setRole(Role.ADMIN);
    }

    @AfterEach
    void clearAll() {
        userRepository.delete(user);
    }

    @Test
    public void testLoginReturnsValidCredentialsWhenLoginSuccess() throws Exception {
        mockMvc.perform(post("/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(login)))
                .andExpect(status().isOk());
    }

    @Test
    public void testRegisterReturnsValidCredentialsWhenRegisterSuccess() throws Exception {
        mockMvc.perform(post("/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(register)))
                .andExpect(status().isCreated());

        User savedUser = userRepository.findByUsernameIgnoreCase(register.getUsername())
                .orElseThrow(UsernameNotFoundException::new);

        userRepository.delete(savedUser);
    }
}
