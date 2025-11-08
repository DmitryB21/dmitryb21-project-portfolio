package com.github.dmitryb21.msocialbot.service;

import com.github.dmitryb21.msocialbot.repository.MessageRepository;
import lombok.AllArgsConstructor;
import org.springframework.stereotype.Service;

@Service
public class MessageService {

    private final MessageRepository messajeReposiyory;

    public MessageService(MessageRepository messajeReposiyory) {
        this.messajeReposiyory = messajeReposiyory;
    }
}
