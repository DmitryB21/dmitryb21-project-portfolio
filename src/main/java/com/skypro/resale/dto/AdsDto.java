package com.skypro.resale.dto;

import lombok.Data;

import java.util.List;

@Data
public class AdsDto {
    private Integer count;
    private List<AdDto> results;
}
