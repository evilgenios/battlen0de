"""Independent marketplace schema, frozen at revision 0007. PostgreSQL only.

Only website user identities are referenced; no operational game data.
"""
from alembic import op

revision = '0007_marketplace'
down_revision = '0006_player_scout_access'
branch_labels = depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE marketplace_listings (
	id UUID NOT NULL, 
	seller_id UUID NOT NULL, 
	title VARCHAR(100) NOT NULL, 
	description TEXT NOT NULL, 
	commander_name VARCHAR(60) NOT NULL, 
	commander_id VARCHAR(40) NOT NULL, 
	server INTEGER NOT NULL, 
	strength BIGINT NOT NULL, 
	commander_level INTEGER NOT NULL, 
	collector_level INTEGER NOT NULL, 
	airspace INTEGER NOT NULL, 
	vip INTEGER NOT NULL, 
	composition VARCHAR(24) NOT NULL, 
	research INTEGER NOT NULL, 
	price_cents INTEGER NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	evidence TEXT NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	review_note TEXT NOT NULL, 
	stats_reviewed BOOLEAN NOT NULL, 
	control_demonstrated BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_marketplace_listings PRIMARY KEY (id), 
	CONSTRAINT ck_marketplace_listings_marketplace_listing_status CHECK (status IN ('draft','pending_review','active','paused','removed')), 
	CONSTRAINT ck_marketplace_listings_marketplace_listing_values CHECK (price_cents >= 100 AND strength >= 0 AND version > 0), 
	CONSTRAINT uq_marketplace_commander UNIQUE (server, commander_id), 
	CONSTRAINT fk_marketplace_listings_seller_id_users FOREIGN KEY(seller_id) REFERENCES users (id) ON DELETE CASCADE
)
    """)
    op.execute("""
CREATE INDEX ix_marketplace_listings_airspace ON marketplace_listings (airspace)
    """)
    op.execute("""
CREATE INDEX ix_marketplace_listings_price_cents ON marketplace_listings (price_cents)
    """)
    op.execute("""
CREATE INDEX ix_marketplace_listings_seller_id ON marketplace_listings (seller_id)
    """)
    op.execute("""
CREATE INDEX ix_marketplace_listings_server ON marketplace_listings (server)
    """)
    op.execute("""
CREATE INDEX ix_marketplace_listings_status ON marketplace_listings (status)
    """)
    op.execute("""
CREATE INDEX ix_marketplace_listings_strength ON marketplace_listings (strength)
    """)
    op.execute("""
CREATE TABLE marketplace_notifications (
	id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	text VARCHAR(300) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_marketplace_notifications PRIMARY KEY (id), 
	CONSTRAINT fk_marketplace_notifications_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)
    """)
    op.execute("""
CREATE INDEX ix_marketplace_notifications_user_id ON marketplace_notifications (user_id)
    """)
    op.execute("""
CREATE TABLE marketplace_profiles (
	user_id UUID NOT NULL, 
	display_name VARCHAR(60) NOT NULL, 
	seller_enabled BOOLEAN NOT NULL, 
	staff_role VARCHAR(24) NOT NULL, 
	restricted BOOLEAN NOT NULL, 
	CONSTRAINT pk_marketplace_profiles PRIMARY KEY (user_id), 
	CONSTRAINT fk_marketplace_profiles_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)
    """)
    op.execute("""
CREATE TABLE marketplace_audit_events (
	id UUID NOT NULL, 
	actor_id UUID, 
	listing_id UUID, 
	action VARCHAR(60) NOT NULL, 
	detail JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_marketplace_audit_events PRIMARY KEY (id), 
	CONSTRAINT fk_marketplace_audit_events_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_marketplace_audit_events_listing_id_marketplace_listings FOREIGN KEY(listing_id) REFERENCES marketplace_listings (id) ON DELETE SET NULL
)
    """)
    op.execute("""
CREATE TABLE marketplace_conversations (
	id UUID NOT NULL, 
	listing_id UUID NOT NULL, 
	buyer_id UUID NOT NULL, 
	seller_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_marketplace_conversations PRIMARY KEY (id), 
	CONSTRAINT uq_marketplace_conversation UNIQUE (listing_id, buyer_id), 
	CONSTRAINT fk_marketplace_conversations_listing_id_marketplace_listings FOREIGN KEY(listing_id) REFERENCES marketplace_listings (id) ON DELETE CASCADE, 
	CONSTRAINT fk_marketplace_conversations_buyer_id_users FOREIGN KEY(buyer_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_marketplace_conversations_seller_id_users FOREIGN KEY(seller_id) REFERENCES users (id) ON DELETE CASCADE
)
    """)
    op.execute("""
CREATE INDEX ix_marketplace_conversations_buyer_id ON marketplace_conversations (buyer_id)
    """)
    op.execute("""
CREATE INDEX ix_marketplace_conversations_seller_id ON marketplace_conversations (seller_id)
    """)
    op.execute("""
CREATE TABLE marketplace_favorites (
	user_id UUID NOT NULL, 
	listing_id UUID NOT NULL, 
	CONSTRAINT pk_marketplace_favorites PRIMARY KEY (user_id, listing_id), 
	CONSTRAINT fk_marketplace_favorites_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_marketplace_favorites_listing_id_marketplace_listings FOREIGN KEY(listing_id) REFERENCES marketplace_listings (id) ON DELETE CASCADE
)
    """)
    op.execute("""
CREATE TABLE marketplace_reports (
	id UUID NOT NULL, 
	listing_id UUID NOT NULL, 
	reporter_id UUID NOT NULL, 
	reason TEXT NOT NULL, 
	resolved BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_marketplace_reports PRIMARY KEY (id), 
	CONSTRAINT fk_marketplace_reports_listing_id_marketplace_listings FOREIGN KEY(listing_id) REFERENCES marketplace_listings (id) ON DELETE CASCADE, 
	CONSTRAINT fk_marketplace_reports_reporter_id_users FOREIGN KEY(reporter_id) REFERENCES users (id) ON DELETE CASCADE
)
    """)
    op.execute("""
CREATE TABLE marketplace_messages (
	id UUID NOT NULL, 
	conversation_id UUID NOT NULL, 
	sender_id UUID NOT NULL, 
	body TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_marketplace_messages PRIMARY KEY (id), 
	CONSTRAINT fk_marketplace_messages_conversation_id_marketplace_con_eb52 FOREIGN KEY(conversation_id) REFERENCES marketplace_conversations (id) ON DELETE CASCADE, 
	CONSTRAINT fk_marketplace_messages_sender_id_users FOREIGN KEY(sender_id) REFERENCES users (id) ON DELETE CASCADE
)
    """)
    op.execute("""
CREATE INDEX ix_marketplace_messages_conversation_id ON marketplace_messages (conversation_id)
    """)


def downgrade():
    op.drop_table('marketplace_messages')
    op.drop_table('marketplace_reports')
    op.drop_table('marketplace_favorites')
    op.drop_table('marketplace_conversations')
    op.drop_table('marketplace_audit_events')
    op.drop_table('marketplace_profiles')
    op.drop_table('marketplace_notifications')
    op.drop_table('marketplace_listings')
