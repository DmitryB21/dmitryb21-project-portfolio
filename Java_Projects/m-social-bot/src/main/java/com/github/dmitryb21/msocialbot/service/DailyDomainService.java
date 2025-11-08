package com.github.dmitryb21.msocialbot.service;

import com.github.dmitryb21.msocialbot.client.BackorderClient;
import com.github.dmitryb21.msocialbot.client.TelegramBotClient;
import com.github.dmitryb21.msocialbot.dto.DailyDomainDto;
import com.github.dmitryb21.msocialbot.entity.DailyDomain;
import com.github.dmitryb21.msocialbot.entity.User;
import com.github.dmitryb21.msocialbot.mapper.DailyDomainMapper;
import com.github.dmitryb21.msocialbot.repository.DailyDomainRepository;
import com.github.dmitryb21.msocialbot.repository.UserRepository;
import jakarta.transaction.Transactional;
import lombok.AllArgsConstructor;
import org.springframework.stereotype.Service;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.io.IOException;
import java.time.LocalDate;
import java.util.List;

@Service
public class DailyDomainService {

    private final DailyDomainRepository dailyDomainRepository;

    private final UserRepository userRepository;
    private final BackorderClient backorderClient;
    private final TelegramBotClient telegramBotClient;

    public DailyDomainService(DailyDomainRepository dailyDomainRepository, UserRepository userRepository, BackorderClient backorderClient, TelegramBotClient telegramBotClient) {
        this.dailyDomainRepository = dailyDomainRepository;
        this.userRepository = userRepository;
        this.backorderClient = backorderClient;
        this.telegramBotClient = telegramBotClient;
    }

    @Transactional
    public void fetchAndSaveDomains() {
        try {
            List<DailyDomainDto> dtos = backorderClient.read();
            List<DailyDomain> entities = dtos.stream()
                    .map(DailyDomainMapper::toEntity)
                    .toList();
            dailyDomainRepository.saveAll(entities);

            int count = entities.size();
            String today = LocalDate.now().toString();
            String message = String.format("%s. Собрано %d доменов", today, count);

            List<User> users = userRepository.findAll();

            for (User user : users) {
                Long chatId = user.getChatId();
                SendMessage sendMessage = new SendMessage(chatId.toString(), message);
                try {
                    telegramBotClient.execute(sendMessage);
                } catch (TelegramApiException e) {
                    System.err.printf("Не удалось отправить сообщение пользователю с chatId %d: %s%n", chatId, e.getMessage());
                    e.printStackTrace();
                }
            }



        } catch (IOException e) {
            throw new RuntimeException("Не удалось получить или сохранить домены", e);
        }
    }
}
