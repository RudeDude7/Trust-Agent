-- ============================================================
-- Phase 4: Live Threat & Breach Feed Migrations
-- Run this in your Supabase SQL Editor
-- ============================================================

CREATE TABLE IF NOT EXISTS watched_vendors (
    user_id UUID NOT NULL,
    vendor_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, vendor_name)
);

CREATE TABLE IF NOT EXISTS threat_alerts (
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
CREATE INDEX IF NOT EXISTS idx_threat_alerts_user ON threat_alerts(user_id, is_read);
