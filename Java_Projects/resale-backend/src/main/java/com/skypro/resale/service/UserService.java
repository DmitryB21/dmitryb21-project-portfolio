package com.skypro.resale.service;

import com.skypro.resale.dto.NewPassword;
import com.skypro.resale.dto.UpdateUser;
import com.skypro.resale.dto.UserDto;
import org.springframework.security.core.Authentication;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;

public interface UserService {
    void updatePassword(NewPassword newPassword, Authentication authentication);

//    UserDto getUser();


    UpdateUser updateUser(UpdateUser updateUser, Authentication authentication);

//    void updateUserAvatar(MultipartFile avatar) throws IOException;

    public UserDto getUser(Authentication authentication);

    void updateUserAvatar(MultipartFile avatar, Authentication authentication) throws IOException;
}
