package com.github.dmitryb21.msocialbot.listener;

import com.github.dmitryb21.msocialbot.client.TelegramBotClient;
import com.github.dmitryb21.msocialbot.entity.User;
import com.github.dmitryb21.msocialbot.entity.UserMessage;
import com.github.dmitryb21.msocialbot.repository.MessageRepository;
import com.github.dmitryb21.msocialbot.repository.UserRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.Message;
import org.telegram.telegrambots.meta.api.objects.MessageEntity;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.exceptions.TelegramApiRequestException;
import org.telegram.telegrambots.meta.generics.BotOptions;
import org.telegram.telegrambots.meta.generics.LongPollingBot;
import org.telegram.telegrambots.util.WebhookUtils;

import java.time.Instant;

@Component
public class MSocialBot implements LongPollingBot {

    private final TelegramBotClient telegramBotClient;
    private final UserRepository userRepository;
    private final MessageRepository messageRepository;

    private final String botToken;

    private final String botUsername;

    public MSocialBot(TelegramBotClient telegramBotClient,
                      UserRepository userRepository,
                      MessageRepository messageRepository,
                      @Value("${bot.token}")String botToken,
                      @Value("${bot.username}")String botUsername) {
        this.telegramBotClient = telegramBotClient;
        this.userRepository = userRepository;
        this.messageRepository = messageRepository;
        this.botToken = botToken;
        this.botUsername = botUsername;
    }

    @Override
    public void onUpdateReceived(Update update) {
        if (update.hasMessage() && update.getMessage().hasText()) {
            Message message = update.getMessage();
            Long chatId = message.getChatId();
            String text = message.getText();

            // 1. Найти пользователя или создать нового
            User user = userRepository.findByChatId(chatId)
                    .orElseGet(() -> {
                        User newUser = new User();
                        newUser.setChatId(chatId);
                        newUser.setLastMessageAt(Instant.now());
                        return userRepository.save(newUser);
                    });

            // 2. Обновить lastMessageAt
            user.setLastMessageAt(Instant.now());
            userRepository.save(user);

            // 3. Создать ответ
            String response = "Вы написали: " + text;

            // 4. Сохранить сообщение
            UserMessage msg = new UserMessage();
            msg.setUser(user);
            msg.setRequest(text);
            msg.setResponse(response);
            messageRepository.save(msg);

            // 5. Отправить ответ
            SendMessage sendMessage = new SendMessage(chatId.toString(), response);
            try {
                telegramBotClient.execute(sendMessage);
            } catch (TelegramApiException e) {
                e.printStackTrace();
            }
        }
    }


    @Override
    public BotOptions getOptions() {
        return telegramBotClient.getOptions();
    }

    @Override
    public void clearWebhook() throws TelegramApiRequestException {
        WebhookUtils.clearWebhook(telegramBotClient);

    }

    @Override
    public String getBotUsername() {
        return botUsername;
    }

    @Override
    public String getBotToken() {
        return botToken;
    }
}
