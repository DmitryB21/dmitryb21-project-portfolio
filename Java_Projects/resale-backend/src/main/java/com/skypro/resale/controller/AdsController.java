package com.skypro.resale.controller;

import com.skypro.resale.dto.AdDto;
import com.skypro.resale.dto.AdsDto;
import com.skypro.resale.dto.CreateOrUpdateAd;
import com.skypro.resale.dto.ExtendedAd;
import com.skypro.resale.service.AdsService;
import com.skypro.resale.service.impl.ImageServiceImpl;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.Collection;

@CrossOrigin(value = "http://localhost:3000")
@RestController
@RequiredArgsConstructor
@RequestMapping("/ads")
public class AdsController {

    private final AdsService adsService;
    private final ImageServiceImpl imageService;

    @Operation(
            summary = "Получить все объявления", tags = "Объявления",
            responses = {
                    @ApiResponse(
                            responseCode = "200", description = "OK",
                            content = {@Content(mediaType = "application/json",
                                    schema = @Schema(implementation = AdsDto.class))})
            }
    )
    @GetMapping
    public ResponseEntity<AdsDto> getAllAds() {
        return ResponseEntity.ok(adsService.getAllAds());
    }


    @Operation(
            summary = "Добавить новое объявление", tags = "Объявления",
            responses = {
                    @ApiResponse(
                            responseCode = "201", description = "Created",
                            content = {@Content(mediaType = "application/json",
                                    schema = @Schema(implementation = AdDto.class))}),
                    @ApiResponse(responseCode = "401", description = "Unauthorised")

            }
    )
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<AdDto> addAds(@RequestPart("image") MultipartFile image,
                                         @RequestPart("properties") CreateOrUpdateAd createOrUpdateAd,
                                        Authentication authentication) throws IOException {
        return ResponseEntity.status(HttpStatus.CREATED).body(adsService.addAds(image, createOrUpdateAd, authentication));
    }

    @Operation(
            summary = "Получение информации об объявлении", tags = "Объявления",
            responses = {
                    @ApiResponse(
                            responseCode = "200", description = "OK",
                            content = {@Content(mediaType = "application/json",
                                    schema = @Schema(implementation = ExtendedAd.class))}),
                    @ApiResponse(responseCode = "401", description = "Unauthorised"),
                    @ApiResponse(responseCode = "404", description = "Not found")
            }
    )
    @GetMapping("/{id}")
    public ResponseEntity<ExtendedAd> getAds(@PathVariable("id") Integer id) {
        return ResponseEntity.ok(adsService.getAdById(id));
    }


    @Operation(
            summary = "Удаление объявления", tags = "Объявления",
            responses = {
                    @ApiResponse(responseCode = "204", description = "No Content"),
                    @ApiResponse(responseCode = "401", description = "Unauthorised"),
                    @ApiResponse(responseCode = "403", description = "Forbidden"),
                    @ApiResponse(responseCode = "404", description = "Not found")
            }
    )

    @PreAuthorize("@adsServiceImpl.getAdsById(#id).getEmail() == authentication.name or hasRole('ROLE_ADMIN')")
    @DeleteMapping("/{id}")
    public ResponseEntity<?> removeAd(@PathVariable("id") Integer id) {
        adsService.removeAdById(id);
        return ResponseEntity.ok().build();
    }

    @Operation(
            summary = "Обновление информации об объявлении", tags = "Объявления",
            responses = {
                    @ApiResponse(
                            responseCode = "200", description = "OK",
                            content = {@Content(mediaType = "application/json",
                                    schema = @Schema(implementation = AdDto.class))}),
                    @ApiResponse(responseCode = "401", description = "Unauthorised"),
                    @ApiResponse(responseCode = "403", description = "Forbidden"),
                    @ApiResponse(responseCode = "404", description = "Not found")
            }
    )
    @PreAuthorize("@adsServiceImpl.getAdsById(#id).getEmail() == authentication.name or hasRole('ROLE_ADMIN')")
    @PatchMapping("/{id}")
    public ResponseEntity<AdDto> updateAds(@PathVariable("id") Integer id,
                                            @RequestBody CreateOrUpdateAd createOrUpdateAd) {
        return ResponseEntity.ok(adsService.updateAds(id, createOrUpdateAd));
    }


    @Operation(
            summary = "Обновить картинку объявления",tags = "Объявления",
            responses = {
                    @ApiResponse(
                            responseCode = "200", description = "OK",
                            content = { @Content(mediaType = "application/octet-stream",
                                    schema = @Schema(implementation = Collection.class))}),
                    @ApiResponse(responseCode = "401", description = "Unauthorized"),
                    @ApiResponse(responseCode = "404", description = "Not Found"),
                    @ApiResponse(responseCode = "403", description = "Forbidden")
            }
    )
    @PreAuthorize("@adsServiceImpl.getAdsById(#id).getEmail() == authentication.name or hasRole('ROLE_ADMIN')")
    @PatchMapping(value = "/{id}/image", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> updateImage(@PathVariable("id") Integer id,
                                            @RequestPart("image") MultipartFile imageFile) throws IOException {
        adsService.updateImage(id, imageFile);
        return ResponseEntity.ok().build();
    }
    @Operation(
            summary = "Получить объявления авторизованного пользователя", tags = "Объявления",
            responses = {
                    @ApiResponse(
                            responseCode = "200", description = "OK",
                            content = {@Content(mediaType = "application/json",
                                    schema = @Schema(implementation = AdsDto.class))}),
                    @ApiResponse(responseCode = "401", description = "Unauthorised", content = @Content),
            }
    )
    @GetMapping("/me")
    public ResponseEntity<AdsDto> getAdsMe(Authentication authentication) {
        return ResponseEntity.ok(adsService.getAdsMe(authentication));
    }

    @Operation(hidden = true)
    @GetMapping(value = "/image/{id}", produces = MediaType.MULTIPART_FORM_DATA_VALUE)
    public byte[] getImage(@PathVariable("id") Integer id) {
        return imageService.getImageById(id).getData();
    }

}
