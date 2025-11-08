package com.skypro.resale.dto;

import lombok.Data;

import java.util.List;

@Data
public class CommentsDto {
    private Integer count;
    private List<CommentDto> results;
}
