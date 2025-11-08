package com.skypro.resale.service.impl;

import com.skypro.resale.dto.Register;
import com.skypro.resale.dto.Role;
import com.skypro.resale.exception.IncorrectArgumentException;
import com.skypro.resale.service.AuthService;
import com.skypro.resale.config.SomeUserDetailsService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import static com.skypro.resale.dto.Role.USER;

@Slf4j
@Service
@Transactional
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {

    private final SomeUserDetailsService manager;
    private final PasswordEncoder encoder;


    @Override
    public boolean login(String userName, String password) {
        log.debug("Logging in user: {}", userName);
        UserDetails userDetails = manager.loadUserByUsername(userName);
        return encoder.matches(password, userDetails.getPassword());
    }

    @Override
    public boolean register(Register register) {
        Role role = register.getRole() == null ? USER : register.getRole();
        if(register.getUsername() == null || register.getUsername().isBlank()
                || register.getFirstName() == null || register.getFirstName().isBlank()
                || register.getLastName() == null || register.getLastName().isBlank()
                || register.getPhone() == null || register.getPhone().isBlank()
                || register.getPassword() == null || register.getPassword().isBlank()) throw new IncorrectArgumentException();

        log.info("Registering new user: {}", register.getUsername());
        manager.createUser(register, role);
        log.info("User {} registered successfully", register.getUsername());
        return true;
    }

}
