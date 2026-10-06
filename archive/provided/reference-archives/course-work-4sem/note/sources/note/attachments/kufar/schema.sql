-- Database schema, PostgreSQL 16

CREATE TYPE platform AS ENUM ('KUFAR', 'ONLINER', 'DEAL_BY', 'WILDBERRIES', 'OZ_BY', 'TWENTYONE_VEK', 'AV_BY');

CREATE TYPE productcategory AS ENUM ('ELECTRONICS', 'TOOLS', 'FURNITURE', 'CLOTHING', 'AUTO', 'SPORTS', 'HOUSEHOLD', 'KIDS', 'GARDEN', 'OTHER', 'BICYCLE', 'LAPTOP', 'APARTMENT');

CREATE TYPE conditionpreference AS ENUM ('ANY', 'WORKING', 'LIKE_NEW');

CREATE TYPE flexibilitylevel AS ENUM ('STRICT', 'MODERATE', 'FLEXIBLE');

CREATE TYPE attributetype AS ENUM ('TEXT', 'NUMBER', 'BOOLEAN', 'RANGE');

CREATE TYPE attributepriority AS ENUM ('MUST_HAVE', 'NICE_TO_HAVE', 'INFORMATIONAL');

CREATE TYPE userreaction AS ENUM ('INTERESTED', 'NOT_INTERESTED', 'BOUGHT');

CREATE TABLE kufar_attributes (
	id SERIAL NOT NULL,
	category_id INTEGER NOT NULL,
	p VARCHAR(100) NOT NULL,
	pu VARCHAR(20) NOT NULL,
	label VARCHAR(255) NOT NULL,
	seen_count INTEGER NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_kufar_attr UNIQUE (category_id, p)
);

CREATE INDEX ix_kufar_attributes_category_id ON kufar_attributes (category_id);

CREATE TABLE listings (
	id SERIAL NOT NULL,
	platform platform NOT NULL,
	external_id VARCHAR(255) NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	price_byn FLOAT,
	currency VARCHAR(10) NOT NULL,
	url TEXT NOT NULL,
	images JSON NOT NULL,
	location VARCHAR(255),
	seller_info JSON,
	condition VARCHAR(50),
	raw_data JSON,
	posted_at TIMESTAMP WITHOUT TIME ZONE,
	first_seen_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	last_seen_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_listings_external_id ON listings (external_id);
CREATE INDEX ix_listings_platform_external_id ON listings (platform, external_id);

CREATE TABLE price_references (
	id SERIAL NOT NULL,
	product_query VARCHAR(255) NOT NULL,
	platform platform NOT NULL,
	min_price FLOAT,
	avg_price FLOAT,
	max_price FLOAT,
	sample_count INTEGER NOT NULL,
	fetched_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_price_references_product_query ON price_references (product_query);

CREATE TABLE users (
	id SERIAL NOT NULL,
	telegram_id BIGINT NOT NULL,
	username VARCHAR(255),
	first_name VARCHAR(255),
	language VARCHAR(10) NOT NULL,
	is_active BOOLEAN NOT NULL,
	notification_enabled BOOLEAN NOT NULL,
	email VARCHAR(255),
	email_verified BOOLEAN DEFAULT false NOT NULL,
	email_notifications BOOLEAN DEFAULT false NOT NULL,
	email_code_hash VARCHAR(64),
	email_code_expires_at TIMESTAMP WITHOUT TIME ZONE,
	email_code_sent_at TIMESTAMP WITHOUT TIME ZONE,
	email_code_attempts INTEGER DEFAULT 0 NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_telegram_id ON users (telegram_id);

CREATE TABLE kufar_attribute_values (
	id SERIAL NOT NULL,
	attribute_id INTEGER NOT NULL,
	value_code VARCHAR(50) NOT NULL,
	value_label VARCHAR(255) NOT NULL,
	parent_code VARCHAR(50),
	seen_count INTEGER NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_kufar_attr_value UNIQUE (attribute_id, value_code),
	FOREIGN KEY(attribute_id) REFERENCES kufar_attributes (id) ON DELETE CASCADE
);

CREATE INDEX ix_kufar_attribute_values_attribute_id ON kufar_attribute_values (attribute_id);

CREATE TABLE tracked_products (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	name VARCHAR(255) NOT NULL,
	category productcategory NOT NULL,
	min_price_byn FLOAT NOT NULL,
	max_price_byn FLOAT,
	condition_preference conditionpreference NOT NULL,
	flexibility flexibilitylevel NOT NULL,
	search_keywords JSON NOT NULL,
	exclude_keywords JSON NOT NULL,
	kufar_filters JSON NOT NULL,
	min_deal_score FLOAT NOT NULL,
	is_active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_tracked_products_user_id ON tracked_products (user_id);

CREATE TABLE custom_attributes (
	id SERIAL NOT NULL,
	tracked_product_id INTEGER NOT NULL,
	attribute_name VARCHAR(100) NOT NULL,
	attribute_type attributetype NOT NULL,
	value TEXT NOT NULL,
	priority attributepriority NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tracked_product_id) REFERENCES tracked_products (id) ON DELETE CASCADE
);

CREATE INDEX ix_custom_attributes_tracked_product_id ON custom_attributes (tracked_product_id);

CREATE TABLE matches (
	id SERIAL NOT NULL,
	tracked_product_id INTEGER NOT NULL,
	listing_id INTEGER NOT NULL,
	deal_score FLOAT NOT NULL,
	match_details JSON NOT NULL,
	notified_at TIMESTAMP WITHOUT TIME ZONE,
	notify_attempts INTEGER DEFAULT 0 NOT NULL,
	notify_error VARCHAR(255),
	email_notified_at TIMESTAMP WITHOUT TIME ZONE,
	email_attempts INTEGER DEFAULT 0 NOT NULL,
	user_reaction userreaction,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tracked_product_id) REFERENCES tracked_products (id) ON DELETE CASCADE,
	FOREIGN KEY(listing_id) REFERENCES listings (id) ON DELETE CASCADE
);

CREATE INDEX ix_matches_listing_id ON matches (listing_id);
CREATE INDEX ix_matches_tracked_product_id ON matches (tracked_product_id);

CREATE TABLE sent_notifications (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	tracked_product_id INTEGER NOT NULL,
	listing_id INTEGER NOT NULL,
	match_id INTEGER,
	listing_external_id VARCHAR(255) NOT NULL,
	platform platform NOT NULL,
	price_byn FLOAT,
	market_avg_byn FLOAT,
	discount_pct FLOAT,
	deal_score FLOAT,
	sent_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
	FOREIGN KEY(tracked_product_id) REFERENCES tracked_products (id) ON DELETE CASCADE,
	FOREIGN KEY(listing_id) REFERENCES listings (id),
	FOREIGN KEY(match_id) REFERENCES matches (id) ON DELETE SET NULL
);

CREATE INDEX ix_sent_notifications_listing_external_id ON sent_notifications (listing_external_id);
CREATE INDEX ix_sent_notifications_tracked_product_id ON sent_notifications (tracked_product_id);
CREATE INDEX ix_sent_notifications_user_id ON sent_notifications (user_id);

