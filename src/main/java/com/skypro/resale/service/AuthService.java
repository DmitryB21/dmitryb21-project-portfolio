package com.skypro.resale.service;


import com.skypro.resale.dto.Register;

public interface AuthService {
    boolean login(String userName, String password);

    boolean register(Register register);
}
