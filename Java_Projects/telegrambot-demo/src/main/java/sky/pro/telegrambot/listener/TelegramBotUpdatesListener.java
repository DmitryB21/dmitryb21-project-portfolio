package sky.pro.telegrambot.listener;

import com.pengrad.telegrambot.TelegramBot;
import com.pengrad.telegrambot.UpdatesListener;
import com.pengrad.telegrambot.model.BotCommand;
import com.pengrad.telegrambot.model.Message;
import com.pengrad.telegrambot.model.Update;
import com.pengrad.telegrambot.request.SendMessage;
import com.pengrad.telegrambot.request.SetMyCommands;
import com.pengrad.telegrambot.response.SendResponse;
import lombok.SneakyThrows;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import sky.pro.telegrambot.model.NotificationTask;
import sky.pro.telegrambot.repo.NotificationTaskRepository;

import javax.annotation.PostConstruct;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class TelegramBotUpdatesListener implements UpdatesListener {

    private final Logger logger = LoggerFactory.getLogger(TelegramBotUpdatesListener.class);

    String HELP_TEXT = "Этот бот принимает от пользователя сообщения в формате 01.01.2022 20:00 Сделать домашнюю работу" +
            " \nи присылает пользователю сообщение в 20:00 1 января 2022 года с текстом : Сделать домашнюю работу\n\n" +
            "Отправте сообщение в указанном формате:\n\n" +
            "/start - start the bot\n" +
            "/help - help menu";

    @Autowired
    private NotificationTaskRepository notificationTaskRepository;

    private final TelegramBot telegramBot;

    public TelegramBotUpdatesListener(TelegramBot telegramBot) {
        this.telegramBot = telegramBot;

        telegramBot.execute(new SetMyCommands(
                new BotCommand("/start", "start bot"),
                new BotCommand("/help", "bot info")
        ));
    }

    @PostConstruct
    public void init() {
        telegramBot.setUpdatesListener(this);
    }

    @Override
    public int process(List<Update> updates) {
        updates.forEach(update -> {

            //Получаем апдейт и фиксируем в лог его данные.
            logger.info("Processing update: {}", update);

            //проверяем, что сообщение не пустое
            Message msg = update.message();
            if (msg != null) {

                //Достаем из переданного сообщения ID чата и текст сообщения
                Long chatId = update.message().chat().id();
                String inputText = update.message().text();
                String memberName = update.message().chat().firstName();
                //Проверяем, не является ли этот текст командой "/start"
                //В случае успешного сравнения создает сообщение в ответ и отправляет его в чат, с полученным ранее ID
                switch (inputText) {
                    case "/start" -> startBot(chatId, memberName);
                    case "/help" -> sendMessage(chatId, HELP_TEXT);
                    default -> sendMessage(chatId, parseMessage(inputText, memberName, chatId));
                }
            }
        });
        return UpdatesListener.CONFIRMED_UPDATES_ALL;
    }


    @SneakyThrows
    private String parseMessage(String inputText, String memberName, Long chatId) {
        Pattern pattern = Pattern.compile("([0-9\\.\\:\\s]{16})(\\s)([\\W+]+)");
        Matcher matcher = pattern.matcher(inputText);
        String date = "";
        String item = "";
        if (matcher.matches()) {
            date = matcher.group(1);
            item = matcher.group(3);
        } else {
            return "Сообщение не соответствует формату 01.01.2022 20:00 \"Сделать домашнюю работу\"," +
                    " пожалуйста, поправте сообщение";
        }
        LocalDateTime localDate;
        try {
            localDate = LocalDateTime.parse(date, DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm"));
        }
        catch (DateTimeParseException e) {
            throw new IllegalArgumentException("Invalid format for date", e);
        }


        if (LocalDateTime.now().isAfter(localDate)) {
            return "Вы ввели дату и время, которое уже прошло";
        }

        NotificationTask notificationTask = new NotificationTask();
        notificationTask.setChatId(chatId);
        notificationTask.setUserName(memberName);
        notificationTask.setTimeNotification(localDate);
        notificationTask.setTextNotification(item);

        notificationTaskRepository.save(notificationTask);

        return "Задача добавлена : " + localDate + " " + item;
    }


    private void startBot(Long chatId, String memberName) {
        String answer = "Salute, " + memberName + "\n для работы с ботом воспользуйтесь /help";
        sendMessage(chatId, answer);
    }

    public void sendMessage(long chatId, String textToSend) {
        SendMessage message = new SendMessage(chatId, textToSend);
        SendResponse sendResponse = telegramBot.execute(message);
        boolean ok = sendResponse.isOk();
        Message msg = sendResponse.message();
        logger.info("SendMessage: {}, {}", ok, msg);
    }
}
