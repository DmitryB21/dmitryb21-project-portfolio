package com.skypro.resale.repository;

import com.skypro.resale.model.Avatar;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
@Repository
public interface AvatarRepository extends JpaRepository<Avatar, Integer> {
}
