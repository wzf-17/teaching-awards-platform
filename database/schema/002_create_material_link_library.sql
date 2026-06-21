CREATE TABLE IF NOT EXISTS `material_link_library` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `province` VARCHAR(32) NOT NULL,
    `year` INT NOT NULL,
    `award_level` VARCHAR(32) NOT NULL,
    `award_name` VARCHAR(512) NOT NULL,
    `material_url` VARCHAR(1024) NOT NULL,
    `is_valid` TINYINT(1) NOT NULL DEFAULT 1,
    `remark` VARCHAR(255) NULL,
    PRIMARY KEY (`id`),
    KEY `idx_material_links_query` (`province`, `year`, `award_level`, `is_valid`),
    KEY `idx_material_links_name` (`award_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
