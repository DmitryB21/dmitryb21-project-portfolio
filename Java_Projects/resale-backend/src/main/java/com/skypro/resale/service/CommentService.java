package com.skypro.resale.service;

import com.skypro.resale.dto.CommentDto;
import com.skypro.resale.dto.CommentsDto;
import com.skypro.resale.dto.CreateOrUpdateComment;
import com.skypro.resale.model.Comment;
import org.springframework.security.core.Authentication;


import java.util.List;

public interface CommentService {
    CommentDto addComment(Integer id, CreateOrUpdateComment createOrUpdateComment, Authentication authentication);

    void deleteComment(Integer adId, Integer commentId);

    CommentDto updateComments(Integer adId, Integer commentId, CreateOrUpdateComment createOrUpdateComment);

    public CommentsDto getComments(Integer id);

    Comment getCommentById(Integer id);
}
