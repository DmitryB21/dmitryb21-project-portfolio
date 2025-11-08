package com.skypro.resale.service.impl;

import com.skypro.resale.dto.NewPassword;
import com.skypro.resale.dto.UpdateUser;
import com.skypro.resale.dto.UserDto;
import com.skypro.resale.exception.UsernameNotFoundException;
import com.skypro.resale.mapper.UserMapper;
import com.skypro.resale.model.User;
import com.skypro.resale.repository.UserRepository;
import com.skypro.resale.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;

@Service
@Transactional
@RequiredArgsConstructor
public class UserServiceImpl implements UserService {

    private final UserRepository userRepository;
    private final AvatarServiceImpl avatarService;
    private final PasswordEncoder passwordEncoder;

    @Override
    public void updatePassword(NewPassword newPassword, Authentication authentication) {
        User user = getUserByUsername(authentication.getName());
        if (!passwordEncoder.matches(newPassword.getCurrentPassword(), user.getPassword())) {
            throw new BadCredentialsException("Bad Credentials");
        }
        user.setPassword(passwordEncoder.encode(newPassword.getNewPassword()));
        userRepository.save(user);
//        log.debug("Password updated for user: {}", authentication.getName());
    }

    @Override
    public UserDto getUser(Authentication authentication) {
//        log.info("Returning details for user: {}", authentication.getName());
        User user = getUserByUsername(authentication.getName());
        return UserMapper.INSTANCE.toDto(user);
    }

    @Override
    public UpdateUser updateUser(UpdateUser updateUser, Authentication authentication) {
        if(updateUser.getFirstName() == null || updateUser.getFirstName().isBlank()
                || updateUser.getLastName() == null || updateUser.getLastName().isBlank()
                || updateUser.getPhone() == null || updateUser.getPhone().isBlank()) throw new IllegalArgumentException();

        User user = getUserByUsername(authentication.getName());
        user.setFirstName(updateUser.getFirstName());
        user.setLastName(updateUser.getLastName());
        user.setPhone(updateUser.getPhone());
        userRepository.save(user);
//        log.debug("User details updated for user: {}", authentication.getName());
        return updateUser;
    }

    @Override
    public void updateUserAvatar(MultipartFile avatar,
                                 Authentication authentication) throws IOException {
        User user = getUserByUsername(authentication.getName());

        if (user.getAvatar() != null) {
            avatarService.remove(user.getAvatar());
        }
        user.setAvatar(avatarService.uploadImage(avatar));
        userRepository.save(user);
//        log.debug("Avatar updated for user: {}", authentication.getName());
    }

    public User getUserByUsername(String username) {
        return userRepository.findByUsernameIgnoreCase(username)
                .orElseThrow(UsernameNotFoundException::new);
    }
}
