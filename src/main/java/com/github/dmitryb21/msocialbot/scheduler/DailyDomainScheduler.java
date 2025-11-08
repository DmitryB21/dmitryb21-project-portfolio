package com.github.dmitryb21.msocialbot.scheduler;

import com.github.dmitryb21.msocialbot.service.DailyDomainService;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class DailyDomainScheduler {

    private final DailyDomainService dailyDomainService;

    public DailyDomainScheduler(DailyDomainService dailyDomainService) {
        this.dailyDomainService = dailyDomainService;
    }

    // Запуск каждый день в 07:00 утра
    //@Scheduled(fixedDelay = 60_000) // каждую минуту
    @Scheduled(cron = "0 0 7 * * *")
    public void scheduleDailyDomainFetch() {
        dailyDomainService.fetchAndSaveDomains();
    }
}
