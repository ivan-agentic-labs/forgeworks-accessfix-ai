-- REVIEW CANDIDATE ONLY. SQLAlchemy PostgreSQL dialect compilation, NO live PostgreSQL.
-- NOT APPROVED AS EXECUTABLE MIGRATION. fw_accessfix_ai_rw must be created with NOLOGIN,
-- checked grants and no table ownership or BYPASSRLS. A distinct migration
-- owner deploys schema. API service must authenticate membership, set SET LOCAL
-- app.tenant_id within transaction, and never pass SQL through to users.
-- Global tenants/users need dedicated authorization rules (not generic RLS).
-- No automatic fw_accessfix_ai_rw GRANT is provided; least-privilege permissions undecided.
-- Audit events require retention controls and legal review.
-- PostgreSQL version/vendor and migration ordering are not yet approved.

CREATE TABLE tenants (
	id UUID NOT NULL, 
	slug TEXT NOT NULL, 
	status TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (slug)
)

;


CREATE TABLE users (
	id UUID NOT NULL, 
	issuer TEXT NOT NULL, 
	subject TEXT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_users_issuer_sub UNIQUE (issuer, subject)
)

;


CREATE TABLE artifact_references (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	object_key TEXT NOT NULL, 
	sha256 CHAR(64) NOT NULL, 
	media_type TEXT NOT NULL, 
	status TEXT NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_artifact_references PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_artifact_references_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_artifact_key UNIQUE (tenant_id, object_key)
)

;


CREATE TABLE audit_events (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	actor_key TEXT NOT NULL, 
	action TEXT NOT NULL, 
	resource_key TEXT NOT NULL, 
	data_class TEXT NOT NULL, 
	trace_id TEXT, 
	payload JSONB NOT NULL, 
	CONSTRAINT pk_audit_events PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_audit_events_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE idempotency_records (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	actor_key TEXT NOT NULL, 
	command_name TEXT NOT NULL, 
	idempotency_key TEXT NOT NULL, 
	request_sha256 CHAR(64) NOT NULL, 
	response_status INTEGER, 
	response_json JSONB, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_idempotency_records PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_idempotency_records_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_idempotency_scope UNIQUE (tenant_id, actor_key, command_name, idempotency_key)
)

;


CREATE TABLE inbox_receipts (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	consumer_name TEXT NOT NULL, 
	event_key TEXT NOT NULL, 
	processed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_inbox_receipts PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_inbox_receipts_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_inbox_dedupe UNIQUE (tenant_id, consumer_name, event_key)
)

;


CREATE TABLE jobs (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	kind TEXT NOT NULL, 
	status TEXT NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	created_by UUID, 
	CONSTRAINT pk_jobs PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_jobs_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE memberships (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	user_id UUID NOT NULL, 
	role TEXT NOT NULL, 
	status TEXT NOT NULL, 
	CONSTRAINT pk_memberships PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_memberships_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_memberships_user FOREIGN KEY(user_id) REFERENCES users (id), 
	CONSTRAINT uq_memberships_user UNIQUE (tenant_id, user_id)
)

;


CREATE TABLE outbox_events (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	event_type TEXT NOT NULL, 
	event_version INTEGER DEFAULT 1 NOT NULL, 
	payload JSONB NOT NULL, 
	event_key TEXT NOT NULL, 
	delivered_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_outbox_events PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_outbox_events_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_outbox_key UNIQUE (tenant_id, event_key)
)

;


CREATE TABLE retest_results (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	proposal_id UUID NOT NULL, 
	scan_job_id UUID NOT NULL, 
	tool_version TEXT NOT NULL, 
	before_violations INTEGER NOT NULL, 
	after_violations INTEGER NOT NULL, 
	evidence_sha256 CHAR(64) NOT NULL, 
	status TEXT NOT NULL, 
	CONSTRAINT pk_retest_results_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_retest_results_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_retest_results_tenant_id_proposal_id_scan_job_id_t_9488a9a0 UNIQUE (tenant_id, proposal_id, scan_job_id, tool_version)
)

;


CREATE TABLE scan_targets (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	site_id UUID NOT NULL, 
	origin TEXT NOT NULL, 
	normalized_url TEXT NOT NULL, 
	scope_digest CHAR(64) NOT NULL, 
	crawl_depth INTEGER DEFAULT 0 NOT NULL, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_scan_targets_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_scan_targets_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_scan_targets_tenant_id_site_id_normalized_url UNIQUE (tenant_id, site_id, normalized_url)
)

;


CREATE TABLE sites (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	canonical_origin TEXT NOT NULL, 
	repository_id UUID NOT NULL, 
	verification_status TEXT NOT NULL, 
	verified_until TIMESTAMP WITH TIME ZONE, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_sites_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_sites_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_sites_tenant_id_canonical_origin UNIQUE (tenant_id, canonical_origin)
)

;


CREATE TABLE scan_jobs (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	site_id UUID NOT NULL, 
	repo_commit_sha TEXT NOT NULL, 
	network_policy_sha256 CHAR(64) NOT NULL, 
	status TEXT NOT NULL, 
	budget_pages INTEGER NOT NULL, 
	CONSTRAINT pk_scan_jobs_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_scan_jobs_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_scan_jobs_tenant_id_site_id FOREIGN KEY(tenant_id, site_id) REFERENCES sites (tenant_id, id)
)

;


CREATE TABLE verification_challenges (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	site_id UUID NOT NULL, 
	token_sha256 CHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	used_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_verification_challenges_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_verification_challenges_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_verification_challenges_tenant_id_site_id FOREIGN KEY(tenant_id, site_id) REFERENCES sites (tenant_id, id), 
	CONSTRAINT uq_verification_challenges_tenant_id_token_sha256 UNIQUE (tenant_id, token_sha256)
)

;


CREATE TABLE findings (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	scan_id UUID NOT NULL, 
	rule_id TEXT NOT NULL, 
	selector TEXT NOT NULL, 
	fingerprint CHAR(64) NOT NULL, 
	severity TEXT NOT NULL, 
	CONSTRAINT pk_findings_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_findings_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_findings_tenant_id_scan_id FOREIGN KEY(tenant_id, scan_id) REFERENCES scan_jobs (tenant_id, id), 
	CONSTRAINT uq_findings_tenant_id_scan_id_fingerprint UNIQUE (tenant_id, scan_id, fingerprint)
)

;


CREATE TABLE fix_proposals (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	finding_id UUID NOT NULL, 
	base_sha TEXT NOT NULL, 
	patch_sha256 CHAR(64) NOT NULL, 
	retest_status TEXT NOT NULL, 
	visual_status TEXT NOT NULL, 
	CONSTRAINT pk_fix_proposals_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_fix_proposals_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_fix_proposals_tenant_id_finding_id FOREIGN KEY(tenant_id, finding_id) REFERENCES findings (tenant_id, id), 
	CONSTRAINT uq_fix_proposals_tenant_id_finding_id_patch_sha256 UNIQUE (tenant_id, finding_id, patch_sha256), 
	CONSTRAINT ck_fix_proposals_version CHECK (version >= 1)
)

;


CREATE TABLE source_mappings (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	finding_id UUID NOT NULL, 
	repository_path TEXT NOT NULL, 
	line_number INTEGER NOT NULL, 
	confidence NUMERIC(4, 3) NOT NULL, 
	evidence_hash CHAR(64) NOT NULL, 
	CONSTRAINT pk_source_mappings_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_source_mappings_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_source_mappings_tenant_id_finding_id FOREIGN KEY(tenant_id, finding_id) REFERENCES findings (tenant_id, id)
)

;


CREATE TABLE manual_reviews (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	proposal_id UUID NOT NULL, 
	reviewer_id UUID NOT NULL, 
	proposal_version INTEGER NOT NULL, 
	reviewed_patch_sha256 CHAR(64) NOT NULL, 
	decision TEXT NOT NULL, 
	manual_check_status TEXT NOT NULL, 
	reviewed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_manual_reviews_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_manual_reviews_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_manual_reviews_tenant_id_proposal_id FOREIGN KEY(tenant_id, proposal_id) REFERENCES fix_proposals (tenant_id, id), 
	CONSTRAINT ck_manual_reviews_proposal_version CHECK (proposal_version >= 1)
)

;

-- INDEXES
CREATE INDEX "ix_scan_jobs_tenant_id_site_id_created_at_DESC" ON scan_jobs (tenant_id, site_id, created_at DESC);

-- RLS POLICIES (candidate, role not yet provisioned)
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY p_memberships_tenant ON memberships FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY p_jobs_tenant ON jobs FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_events FORCE ROW LEVEL SECURITY;
CREATE POLICY p_outbox_events_tenant ON outbox_events FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE inbox_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE inbox_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY p_inbox_receipts_tenant ON inbox_receipts FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_records FORCE ROW LEVEL SECURITY;
CREATE POLICY p_idempotency_records_tenant ON idempotency_records FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
-- Audit is append-only for the application role; owner/retention procedure is separate.
CREATE POLICY p_audit_events_read ON audit_events FOR SELECT TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY p_audit_events_append ON audit_events FOR INSERT TO fw_accessfix_ai_rw WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE artifact_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifact_references FORCE ROW LEVEL SECURITY;
CREATE POLICY p_artifact_references_tenant ON artifact_references FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE sites FORCE ROW LEVEL SECURITY;
CREATE POLICY p_sites_tenant ON sites FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE verification_challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_challenges FORCE ROW LEVEL SECURITY;
CREATE POLICY p_verification_challenges_tenant ON verification_challenges FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE scan_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY p_scan_jobs_tenant ON scan_jobs FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE findings FORCE ROW LEVEL SECURITY;
CREATE POLICY p_findings_tenant ON findings FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE source_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_mappings FORCE ROW LEVEL SECURITY;
CREATE POLICY p_source_mappings_tenant ON source_mappings FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE fix_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE fix_proposals FORCE ROW LEVEL SECURITY;
CREATE POLICY p_fix_proposals_tenant ON fix_proposals FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE manual_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE manual_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY p_manual_reviews_tenant ON manual_reviews FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE scan_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_targets FORCE ROW LEVEL SECURITY;
CREATE POLICY p_scan_targets_tenant ON scan_targets FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE retest_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE retest_results FORCE ROW LEVEL SECURITY;
CREATE POLICY p_retest_results_tenant ON retest_results FOR ALL TO fw_accessfix_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
