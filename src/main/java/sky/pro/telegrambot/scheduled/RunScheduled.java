package sky.pro.telegrambot.scheduled;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import sky.pro.telegrambot.listener.TelegramBotUpdatesListener;
import sky.pro.telegrambot.model.NotificationTask;
import sky.pro.telegrambot.repo.NotificationTaskRepository;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.Collection;

@Component
public class RunScheduled {

    @Autowired
    TelegramBotUpdatesListener telegramBotUpdatesListener;

    @Autowired
    private NotificationTaskRepository notificationTaskRepository;



    @Scheduled(cron = "0 0/1 * * * *")
    public void runScheduled() {
        Collection<NotificationTask> taskList =
                notificationTaskRepository.findNotificationTaskByTimeNotification(LocalDateTime.now().truncatedTo(ChronoUnit.MINUTES));

        for (NotificationTask notificationTask : taskList) {
            String sendMessage = notificationTask.getTimeNotification() + " " + notificationTask.getTextNotification();
            telegramBotUpdatesListener.sendMessage(notificationTask.getChatId(), sendMessage);
        }
    }
}
