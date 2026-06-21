CREATE TABLE IF NOT EXISTS `wordcloud_images` (
    `year` INT NOT NULL,
    `filename` VARCHAR(255) NOT NULL,
    `mime_type` VARCHAR(64) NOT NULL,
    `img` LONGBLOB NOT NULL,
    PRIMARY KEY (`year`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
