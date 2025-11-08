-- liquibase formatted sql

-- changeset dblyukherov:1
CREATE TABLE notification_task (
                       id SERIAL,
                       chat_id BIGINT,
                       user_name TEXT,
                       text_notification TEXT,
                       time_Notification TIMESTAMP

)