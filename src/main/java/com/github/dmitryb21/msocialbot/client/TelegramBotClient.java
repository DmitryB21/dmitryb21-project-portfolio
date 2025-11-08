package com.github.dmitryb21.msocialbot.client;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.bots.DefaultAbsSender;
import org.telegram.telegrambots.bots.DefaultBotOptions;

@Component
public class TelegramBotClient extends DefaultAbsSender {

    protected TelegramBotClient(@Value("${bot.token}") String botToken) {
        super(new DefaultBotOptions(), botToken);
    }
}
