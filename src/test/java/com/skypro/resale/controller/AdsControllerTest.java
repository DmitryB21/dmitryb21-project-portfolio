package com.skypro.resale.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.skypro.resale.config.SomeUserDetailsService;
import com.skypro.resale.dto.CreateOrUpdateAd;
import com.skypro.resale.dto.Role;
import com.skypro.resale.model.Ad;
import com.skypro.resale.model.Image;
import com.skypro.resale.model.User;
import com.skypro.resale.repository.AdRepository;
import com.skypro.resale.repository.ImageRepository;
import com.skypro.resale.repository.UserRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockPart;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@Transactional
public class AdsControllerTest {

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private AdRepository adRepository;
    @Autowired
    private ObjectMapper objectMapper;
    @Autowired
    private PasswordEncoder encoder;
    @Autowired
    private UserRepository userRepository;
    @Autowired
    private SomeUserDetailsService userDetailsService;

    private Authentication auth;
    @Autowired
    private ImageRepository imageRepository;
    private final MockPart imageFile
            = new MockPart("image", "image", "image".getBytes());
    private final User user = new User();
    private final CreateOrUpdateAd createAds = new CreateOrUpdateAd();
    private final Ad ads = new Ad();
    private final Image image = new Image();

    @BeforeEach
    void setUp() {
        user.setUsername("username@mail.ru");
        user.setFirstName("User");
        user.setLastName("Test");
        user.setPhone("+79609279284");
        user.setPassword(encoder.encode("password"));
        user.setRole(Role.ADMIN);
        userRepository.save(user);

        UserDetails userDetails = userDetailsService.loadUserByUsername(user.getUsername());
        auth = new UsernamePasswordAuthenticationToken(userDetails.getUsername(),
                userDetails.getPassword(),
                userDetails.getAuthorities());

        ads.setTitle("Ads");
        ads.setDescription("description");
        ads.setPrice(1000);
        ads.setAuthor(user);
        adRepository.save(ads);
    }

    @AfterEach
    void cleanUp() {
        userRepository.delete(user);
    }

    @Test
    public void testGetAllAdsReturnsCorrectAdsList() throws Exception {
        mockMvc.perform(get("/ads"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").exists())
                .andExpect(jsonPath("$.count").isNumber())
                .andExpect(jsonPath("$.results").isArray());
    }

    @Test
    public void testGetFullAddReturnsCorrectAds() throws Exception {
        mockMvc.perform(get("/ads/{id}", ads.getId())
                        .with(authentication(auth)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.pk").value(ads.getId()))
                .andExpect(jsonPath("$.title").value(ads.getTitle()))
                .andExpect(jsonPath("$.description").value(ads.getDescription()))
                .andExpect(jsonPath("$.price").value(ads.getPrice()))
                .andExpect(jsonPath("$.email").value(user.getUsername()))
                .andExpect(jsonPath("$.authorFirstName").value(user.getFirstName()))
                .andExpect(jsonPath("$.authorLastName").value(user.getLastName()))
                .andExpect(jsonPath("$.phone").value(user.getPhone()));
    }

    @Test
    public void testGetAdsMeReturnsCorrectAdsList() throws Exception {
        mockMvc.perform(get("/ads/me")
                        .with(authentication(auth)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").exists())
                .andExpect(jsonPath("$.count").isNumber())
                .andExpect(jsonPath("$.results").isArray());
    }

    @Test
    public void testGetImage() throws Exception {
        image.setData("image".getBytes());
        image.setMediaType("image/jpeg");
        imageRepository.save(image);
        ads.setImage(image);
        adRepository.save(ads);

        mockMvc.perform(get("/ads/image/{id}", image.getId())
                        .contentType(MediaType.MULTIPART_FORM_DATA_VALUE)
                        .with(authentication(auth)))
                .andExpect(status().isOk())
                .andExpect(content().bytes(image.getData()));
    }



}


