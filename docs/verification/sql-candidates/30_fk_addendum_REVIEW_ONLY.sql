-- DESIGN-ONLY SQL. NOT VALIDATED BY A LIVE POSTGRESQL INSTANCE.
-- Review business semantics, existing data, and ON DELETE decision before adoption.
-- Apply after 10_schema_candidate.sql, on an isolated disposable database only.

ALTER TABLE retest_results
  ADD CONSTRAINT fk_g1_retest_results_proposal_id
  FOREIGN KEY (tenant_id, proposal_id)
  REFERENCES fix_proposals (tenant_id, id)
  ON DELETE RESTRICT;

ALTER TABLE retest_results
  ADD CONSTRAINT fk_g1_retest_results_scan_job_id
  FOREIGN KEY (tenant_id, scan_job_id)
  REFERENCES scan_jobs (tenant_id, id)
  ON DELETE RESTRICT;

ALTER TABLE scan_targets
  ADD CONSTRAINT fk_g1_scan_targets_site_id
  FOREIGN KEY (tenant_id, site_id)
  REFERENCES sites (tenant_id, id)
  ON DELETE RESTRICT;
