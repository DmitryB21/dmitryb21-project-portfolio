package com.github.dmitryb21.msocialbot;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class MSocialBotApplication {

	public static void main(String[] args) {
		SpringApplication.run(MSocialBotApplication.class, args);
	}

}
