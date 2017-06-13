

CREATE TABLE "databases" (
"id" INTEGER PRIMARY KEY AUTOINCREMENT,
"db_name" TEXT,
"db_type" TEXT,
"address" TEXT,
"port" TEXT,
"username" TEXT,
"password" TEXT,
"user_id" TEXT REFERENCES "users"("id"),
"status" TEXT,
"token" TEXT
);


CREATE TABLE "network_configs" (
"id" INTEGER PRIMARY KEY AUTOINCREMENT,
"name" TEXT,
"ssid" TEXT,
"anonymous_id" TEXT,
"username" TEXT,
"password" TEXT,
"probe_id" INTEGER REFERENCES "probes"("id")
);


CREATE TABLE "probes" (
"id" INTEGER PRIMARY KEY AUTOINCREMENT,
"name" TEXT,
"custom_id" TEXT,
"location" TEXT,
"port" INTEGER,
"pub_key" TEXT,
"host_key" TEXT,
"association_period_start" INTEGER,
"associated" INTEGER,
"has_been_updated" INTEGER,
"last_updated" TEXT,
"user_id" INTEGER REFERENCES "users"("id")
);


CREATE TABLE "scripts" (
"id" INTEGER PRIMARY KEY AUTOINCREMENT,
"description" TEXT,
"args" TEXT,
"minute_interval" INTEGER,
"enabled" INTEGER,
"required" INTEGER,
"probe_id" INTEGER REFERENCES "probes"("id")
);


CREATE TABLE "users" (
"id" INTEGER PRIMARY KEY AUTOINCREMENT,
"username" TEXT,
"pw_hash" TEXT,
"contact_person" TEXT,
"contact_email" TEXT,
"admin" INTEGER,
"oauth_id" TEXT
);

