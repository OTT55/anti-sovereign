CREATE TABLE `capture_challenges` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`nonce` text NOT NULL,
	`issued_at` text DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')) NOT NULL,
	`expires_at` text NOT NULL,
	`used_at` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `capture_challenges_nonce_unique` ON `capture_challenges` (`nonce`);--> statement-breakpoint
CREATE TABLE `devices` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`handle` text NOT NULL,
	`public_key_spki` text NOT NULL,
	`created_at` text DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')) NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `devices_handle_unique` ON `devices` (`handle`);--> statement-breakpoint
CREATE TABLE `film_rushes` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`rush_id` text NOT NULL,
	`device_id` integer,
	`production` text NOT NULL,
	`roll_number` text,
	`scene_take` text,
	`file_name` text NOT NULL,
	`media_hash` text NOT NULL,
	`framerate` text,
	`dit_notes` text,
	`captured_at` text NOT NULL,
	`created_at` text DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')) NOT NULL,
	FOREIGN KEY (`device_id`) REFERENCES `devices`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `film_rushes_rush_id_unique` ON `film_rushes` (`rush_id`);--> statement-breakpoint
CREATE TABLE `manifests` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`manifest_id` text NOT NULL,
	`device_id` integer NOT NULL,
	`media_hash` text NOT NULL,
	`label` text,
	`challenge` text NOT NULL,
	`signature` text NOT NULL,
	`captured_at` text NOT NULL,
	`received_at` text DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')) NOT NULL,
	`watermark_secret` text,
	FOREIGN KEY (`device_id`) REFERENCES `devices`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `manifests_manifest_id_unique` ON `manifests` (`manifest_id`);