package com.skypro.resale.dto;

import lombok.Data;

@Data
public class CreateOrUpdateAd {
    private String title;
    private String description;
    private Integer price;
}
