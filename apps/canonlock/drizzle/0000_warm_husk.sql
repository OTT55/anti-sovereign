CREATE TABLE `creators` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`handle` text NOT NULL,
	`display_name` text NOT NULL,
	`created_at` text DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')) NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `creators_handle_unique` ON `creators` (`handle`);--> statement-breakpoint
CREATE TABLE `merkle_checkpoints` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`leaf_count` integer NOT NULL,
	`merkle_root` text NOT NULL,
	`signature` text NOT NULL,
	`created_at` text DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')) NOT NULL
);
--> statement-breakpoint
CREATE TABLE `registrations` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`registry_id` text NOT NULL,
	`creator_id` integer NOT NULL,
	`filename` text NOT NULL,
	`file_hash` text NOT NULL,
	`description` text,
	`leaf_index` integer NOT NULL,
	`signature` text NOT NULL,
	`tsa_server` text,
	`tsa_granted_at` text,
	`tsa_token` text,
	`tsa_status` text NOT NULL,
	`created_at` text DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')) NOT NULL,
	FOREIGN KEY (`creator_id`) REFERENCES `creators`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `registrations_registry_id_unique` ON `registrations` (`registry_id`);--> statement-breakpoint
CREATE UNIQUE INDEX `registrations_file_hash_unique` ON `registrations` (`file_hash`);--> statement-breakpoint
CREATE INDEX `idx_registrations_creator` ON `registrations` (`creator_id`);--> statement-breakpoint
CREATE UNIQUE INDEX `uq_registrations_leaf_index` ON `registrations` (`leaf_index`);