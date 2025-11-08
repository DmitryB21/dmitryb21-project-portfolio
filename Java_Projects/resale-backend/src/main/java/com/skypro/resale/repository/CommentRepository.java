package com.skypro.resale.repository;

import com.skypro.resale.model.Comment;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface CommentRepository extends JpaRepository<Comment, Integer> {

    Optional<Comment> findByIdAndAdsId(Integer commentId, Integer adId);
    List<Comment> findAllByAdsId (Integer id);

}
