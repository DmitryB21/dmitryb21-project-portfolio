package com.github.dmitryb21.msocialbot.repository;

import com.github.dmitryb21.msocialbot.entity.UserMessage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface MessageRepository extends JpaRepository<UserMessage, Long> {


}
