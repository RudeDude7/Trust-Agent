-- ============================================================
-- Phase 4: Live Threat & Breach Feed Migrations
-- Run this in your Supabase SQL Editor
-- ============================================================

-- Drop the tables in case they were previously created with a different schema
DROP TABLE IF EXISTS threat_alerts CASCADE;
DROP TABLE IF EXISTS watched_vendors CASCADE;

CREATE TABLE watched_vendors (
    user_id UUID NOT NULL,
    vendor_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, vendor_name)
);

CREATE TABLE threat_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    vendor_name TEXT NOT NULL,
    alert_title TEXT NOT NULL,
    alert_summary TEXT NOT NULL,
    source_url TEXT,
    severity TEXT NOT NULL, -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for quick lookups
CREATE INDEX idx_threat_alerts_user ON threat_alerts(user_id, is_read);
