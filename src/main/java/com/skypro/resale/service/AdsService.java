package com.skypro.resale.service;

import com.skypro.resale.dto.AdDto;
import com.skypro.resale.dto.AdsDto;
import com.skypro.resale.dto.CreateOrUpdateAd;
import com.skypro.resale.dto.ExtendedAd;
import org.springframework.security.core.Authentication;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;

public interface AdsService {
    AdsDto getAllAds();

    AdDto addAds(MultipartFile imageFiles, CreateOrUpdateAd createOrUpdateAd, Authentication authentication) throws IOException;

    ExtendedAd getAdById(Integer id);

    void removeAdById(Integer id);

    AdDto updateAds(Integer id, CreateOrUpdateAd createOrUpdateAd);

    void updateImage(Integer id, MultipartFile imageFile) throws IOException;

    AdsDto getAdsMe(Authentication authentication);
}