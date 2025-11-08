package com.skypro.resale.service.impl;

import com.skypro.resale.dto.*;
import com.skypro.resale.exception.AdsNotFoundException;
import com.skypro.resale.exception.IncorrectArgumentException;
import com.skypro.resale.mapper.AdsMapper;
import com.skypro.resale.model.Ad;
import com.skypro.resale.model.Image;
import com.skypro.resale.model.User;
import com.skypro.resale.repository.AdRepository;
import com.skypro.resale.service.AdsService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
@Transactional
@RequiredArgsConstructor
public class AdsServiceImpl implements AdsService {

    private final AdRepository adRepository;
    private final ImageServiceImpl imageService;
    private final AdsMapper adsMapper;
    private final UserServiceImpl userService;



    public AdsDto getAllAds() {
        List<Ad> adList = adRepository.findAll();
        Integer sizeList = adList.size();
        return adsMapper.adListToAdsDto(sizeList, adList);
    }


    public AdDto addAds(MultipartFile image, CreateOrUpdateAd createOrUpdateAd,  Authentication authentication) throws IOException {
        if (createOrUpdateAd.getTitle() == null || createOrUpdateAd.getTitle().isBlank()
                || createOrUpdateAd.getDescription() == null || createOrUpdateAd.getDescription().isBlank()
                || createOrUpdateAd.getPrice() == null) throw new IncorrectArgumentException();
        Ad ad = adsMapper.toModel(createOrUpdateAd);
        User user = userService.getUserByUsername(authentication.getName());
        ad.setAuthor(user);
        Image imageUpload = imageService.uploadImage(image);
        ad.setImage(imageUpload);
        return adsMapper.toDto(adRepository.save(ad));
    }

    public ExtendedAd getAdById(Integer id) {
        log.debug("Getting ad by id: {}", id);
        return adsMapper.toExtendedAd(findAdsById(id));
    }

    public Ad findAdsById(Integer id) {
        log.debug("Finding ad by id: {}", id);
        return adRepository.findById(id).orElseThrow(AdsNotFoundException::new);
    }


    public void removeAdById(Integer id) {
        Ad ad = findAdsById(id);
        adRepository.delete(ad);
    }



    public AdDto updateAds(Integer id, CreateOrUpdateAd createAds) {

        if (createAds.getTitle() == null || createAds.getTitle().isBlank()
                || createAds.getDescription() == null || createAds.getDescription().isBlank()
                || createAds.getPrice() == null) throw new IncorrectArgumentException();

        Ad ad = findAdsById(id);
        ad.setTitle(createAds.getTitle());
        ad.setDescription(createAds.getDescription());
        ad.setPrice(createAds.getPrice());
        adRepository.save(ad);
        log.info("Ad details updated for ad: {}", ad.getTitle());
        return adsMapper.toDto(ad);

    }

    public void updateImage(Integer id, MultipartFile imageFile) throws IOException {
      log.debug("Updating ad image by id: {}", id);
        Ad ad = findAdsById(id);
        if (ad.getImage() != null) {
            imageService.remove(ad.getImage());
        }
        ad.setImage(imageService.uploadImage(imageFile));
        adRepository.save(ad);
        log.debug("Avatar updated for ad: {}", ad.getTitle());
    }

    public List<CommentDto> getComments(Integer id) {
        return new ArrayList<>();
    }

    public CommentDto addComment(Integer id, CommentDto newCommentDto) {
        return new CommentDto();
    }

        public AdsDto getAdsMe(Authentication authentication) {
            List<Ad> adList = adRepository.findAllByAuthorId(userService.getUserByUsername(authentication.getName()).getId());
            Integer sizeList = adList.size();
            return adsMapper.adListToAdsDto(sizeList, adList);
        }



}
