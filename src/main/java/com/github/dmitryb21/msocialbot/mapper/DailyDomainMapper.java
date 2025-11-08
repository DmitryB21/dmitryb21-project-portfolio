package com.github.dmitryb21.msocialbot.mapper;

import com.github.dmitryb21.msocialbot.dto.DailyDomainDto;
import com.github.dmitryb21.msocialbot.entity.DailyDomain;

public class DailyDomainMapper {
    public static DailyDomain toEntity(DailyDomainDto dto) {
        DailyDomain entity = new DailyDomain();
        entity.setDomainname(dto.getDomainName());
        entity.setHotness(dto.getHotness());
        entity.setPrice(dto.getPrice());
        entity.setxValue(dto.getxValue());
        entity.setYandexTic(dto.getYandexTic());
        entity.setLinks(dto.getLinks());
        entity.setVisitors(dto.getVisitors());
        entity.setRegistrar(dto.getRegistrar());
        entity.setOld(dto.getOld());
        entity.setDeleteDate(dto.getDeleteDate());
        entity.setRkn(dto.isRkn());
        entity.setJudicial(dto.isJudicial());
        entity.setBlock(dto.isBlock());
        return entity;
    }
}
