package com.skypro.resale.service.impl;

import com.skypro.resale.exception.ImageNotFoundException;
import com.skypro.resale.model.Image;
import com.skypro.resale.repository.ImageRepository;
import com.skypro.resale.service.ImageService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;


import java.io.IOException;

@Slf4j
@Service
@Transactional
@RequiredArgsConstructor
public class ImageServiceImpl implements ImageService<Image> {

    private final ImageRepository imageRepository;


    @Override
    public void remove(Image image) {
        imageRepository.delete(image);
//        log.info("Image removed successfully");
    }

    @Override
    public Image uploadImage(MultipartFile imageFile) throws IOException {
        log.debug("Uploading image file: " + imageFile.getOriginalFilename());
        Image image = new Image();
        image.setMediaType(imageFile.getContentType());
        image.setFileSize(imageFile.getSize());
        image.setData(imageFile.getBytes());
        Image savedImage = imageRepository.save(image);
        log.info("Image successfully uploaded with id {}", savedImage.getId());
        return savedImage;
    }

    @Override
    public Image getImageById(Integer id) {
        log.debug("Getting image with id: {}", id);
        return imageRepository.findById(id).orElseThrow(ImageNotFoundException::new);
    }

}
