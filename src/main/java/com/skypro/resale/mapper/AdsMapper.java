package com.skypro.resale.mapper;

import com.skypro.resale.dto.AdDto;
import com.skypro.resale.dto.AdsDto;
import com.skypro.resale.dto.CreateOrUpdateAd;
import com.skypro.resale.dto.ExtendedAd;
import com.skypro.resale.model.Ad;
import com.skypro.resale.model.Image;
import org.mapstruct.InjectionStrategy;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.Named;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@Mapper(componentModel = "spring", injectionStrategy = InjectionStrategy.CONSTRUCTOR)
public interface AdsMapper {


    String ADS_IMAGE = "/ads/image/";

    @Mapping(target = "id", ignore = true)
    @Mapping(target = "author", ignore = true)
    @Mapping(target = "image", ignore = true)
    @Mapping(target = "comments", ignore = true)
    Ad toModel(CreateOrUpdateAd dto);

    @Mapping(target = "pk", source = "id")
    @Mapping(target = "author", source = "author.id")
    @Mapping(target = "image", source = "image", qualifiedByName = "imageMapping")
    AdDto toDto(Ad ad);

    @Mapping(target = "authorFirstName", source = "author.firstName")
    @Mapping(target = "authorLastName", source = "author.lastName")
    @Mapping(target = "phone", source = "author.phone")
    @Mapping(target = "email", source = "author.username")
    @Mapping(target = "image", source = "image", qualifiedByName = "imageMapping")
    @Mapping(target = "pk", source = "id")
    ExtendedAd toExtendedAd(Ad ad);
    @Named("imageMapping")
    default String imageMapping(Image image) {
        if (image == null) {
            return null;
        }
        return ADS_IMAGE + image.getId();
    }

    @Mapping(source = "sizeList", target = "count")
    @Mapping(source = "list", target = "results")
    AdsDto adListToAdsDto(Integer sizeList, List<Ad> list);

    List<AdDto> adListToAdDtoList(List<Ad> adsList);

}
