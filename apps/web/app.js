const FIXTURE_ORIGIN = "http://fixture.local";
const SITE_ID = "22222222-2222-2222-2222-222222222222";
const REPOSITORY_ID = "33333333-3333-3333-3333-333333333333";
const DEFAULT_COMMIT = "a".repeat(40);

const $ = (selector) => document.querySelector(selector);
const output = $("#output");
const errorState = $("#error-state");
const errorTitle = $("#error-title");
const errorDetail = $("#error-detail");
const overallStatus = $("#overall-status");

class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body || {};
  }
}

function setOverall(label, kind) {
  overallStatus.textContent = label;
  overallStatus.className = `pill ${kind}`;
}

function setStep(name, label, kind = "idle") {
  const row = document.querySelector(`[data-step="${name}"]`);
  if (!row) return;
  row.dataset.state = kind;
  row.querySelector(".step-status").textContent = label;
}

function showError(error, context = "Request failed") {
  const body = error instanceof ApiError ? error.body : {};
  const code = body.code || (error.status ? `HTTP_${error.status}` : "CLIENT_ERROR");
  const detail = body.detail || error.message || "The workflow stopped without making further requests.";
  errorTitle.textContent = code === "REMOTE_BROWSER_BLOCKED" ? "Remote scan blocked (fail-closed)" : context;
  errorDetail.textContent = `${code}: ${detail}`;
  errorState.hidden = false;
  setOverall("STOPPED", "blocked");
}

function clearError() {
  errorState.hidden = true;
  errorTitle.textContent = "Fail-closed error";
  errorDetail.textContent = "";
}

function fixtureOrigin() {
  const value = $("#fixture-origin").value.trim();
  if (value !== FIXTURE_ORIGIN) {
    throw new Error(`Only ${FIXTURE_ORIGIN} is allowed; remote targets are disabled.`);
  }
  return value;
}

function apiBase() {
  const raw = $("#api-base").value.trim();
  const url = new URL(raw);
  if (!/^https?:$/.test(url.protocol)) throw new Error("API base must use HTTP or HTTPS.");
  if (!["127.0.0.1", "localhost"].includes(url.hostname)) {
    throw new Error("The fixture console only calls a local API; remote API hosts are disabled.");
  }
  return url.href.replace(/\/$/, "");
}

function bearer() {
  const value = $("#bearer-token").value.trim();
  if (!value) throw new Error("A local development bearer token is required.");
  return value.startsWith("Bearer ") ? value : `Bearer ${value}`;
}

function commitSha() {
  const value = $("#repo-sha").value.trim();
  if (!/^[0-9a-fA-F]{40,64}$/.test(value)) throw new Error("Commit SHA must be 40–64 hexadecimal characters.");
  return value;
}

function key(label) {
  const suffix = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
  return `accessfix-ui-${label}-${suffix}`;
}

async function request(path, options = {}) {
  const headers = {
    Accept: "application/json",
    Authorization: bearer(),
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers || {}),
  };
  let response;
  try {
    response = await fetch(`${apiBase()}${path}`, { ...options, headers });
  } catch (error) {
    throw new ApiError(`API is unreachable: ${error.message}`, 0, { code: "API_UNREACHABLE" });
  }
  const text = await response.text();
  let body = {};
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text };
    }
  }
  const challengeToken = response.headers.get("X-Development-Challenge-Token");
  if (challengeToken) body._development_challenge_token = challengeToken;
  if (!response.ok) {
    throw new ApiError(body.detail || `API returned HTTP ${response.status}`, response.status, body);
  }
  output.textContent = JSON.stringify(body, null, 2);
  return body;
}

function json(body) {
  return JSON.stringify(body);
}

async function waitForJob(jobId) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const result = await request(`/v1/jobs/${jobId}`);
    if (["SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"].includes(result.state)) return result;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("The fixture worker did not finish the job within the local wait window.");
}

async function waitForFinding(scanId) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const result = await request(`/v1/scans/${scanId}/findings`);
    if (result.items?.length) return result;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("The fixture worker did not produce a finding within the local wait window.");
}

async function runFlow() {
  clearError();
  $("#run-flow").disabled = true;
  setOverall("RUNNING", "running");
  ["ownership", "scan", "findings", "retest", "review"].forEach((step) => setStep(step, "Not started", "idle"));
  try {
    const origin = fixtureOrigin();
    const sha = commitSha();
    setStep("ownership", "Requesting challenge", "running");
    const challenge = await request("/v1/sites/verification-challenges", {
      method: "POST",
      headers: { "Idempotency-Key": key("challenge") },
      body: json({ canonical_origin: origin, repository_id: REPOSITORY_ID }),
    });
    const challengeToken = challenge._development_challenge_token || "";
    const responseToken = challengeToken || window.prompt("Paste the development challenge token returned by the API:");
    if (!responseToken) throw new Error("Challenge token is required to complete ownership verification.");
    const verified = await request(`/v1/sites/${SITE_ID}/verify`, {
      method: "POST",
      headers: { "Idempotency-Key": key("verify") },
      body: json({ challenge_id: challenge.id, evidence_token: responseToken }),
    });
    setStep("ownership", `Verified until ${verified.verified_until || "server response"}`, "passed");

    setStep("scan", "Queueing fixture scan", "running");
    const scan = await request(`/v1/sites/${SITE_ID}/scans`, {
      method: "POST",
      headers: { "Idempotency-Key": key("scan") },
      body: json({ repo_commit_sha: sha, paths: ["/"] }),
    });
    setStep("scan", `Accepted ${scan.id}`, "passed");

    setStep("findings", "Polling fixture job", "running");
    const job = await waitForJob(scan.job_id);
    if (job.state !== "SUCCEEDED") throw new Error(`Fixture job stopped: ${job.state}`);
    const findings = await waitForFinding(scan.id);
    const finding = findings.items[0];
    setStep("findings", `${findings.items.length} finding(s) returned`, "passed");

    const proposal = await request(`/v1/findings/${finding.id}/fix-proposals`, {
      method: "POST",
      headers: { "Idempotency-Key": key("proposal") },
      body: json({ source_mapping_id: finding.source_mapping.id, alt_text: $("#alt-text").value }),
    });

    setStep("retest", "Queueing base-revision retest", "running");
    const retest = await request(`/v1/fix-proposals/${proposal.id}/retests`, {
      method: "POST",
      headers: { "Idempotency-Key": key("retest") },
      body: json({ repo_commit_sha: proposal.base_sha, expected_version: proposal.version }),
    });
    setStep("retest", `Accepted: ${retest.retest_status}`, "passed");

    setStep("review", "Recording manual review", "running");
    const review = await request(`/v1/fix-proposals/${proposal.id}/reviews`, {
      method: "POST",
      headers: { "Idempotency-Key": key("review") },
      body: json({
        patch_sha256: proposal.patch_sha256,
        decision: "approve",
        manual_check_status: "passed",
        expected_version: retest.version,
      }),
    });
    setStep("review", `Recorded: ${review.status}`, "passed");
    output.textContent = JSON.stringify({ challenge, verified, scan, job, findings, proposal, retest, review }, null, 2);
    setOverall("COMPLETE", "passed");
  } catch (error) {
    const failedStep = ["review", "retest", "findings", "scan", "ownership"].find((name) => document.querySelector(`[data-step="${name}"]`)?.dataset.state === "running");
    if (failedStep) setStep(failedStep, "Stopped (fail-closed)", "blocked");
    showError(error);
  } finally {
    $("#run-flow").disabled = false;
  }
}

$("#run-flow").addEventListener("click", runFlow);
$("#dismiss-error").addEventListener("click", clearError);
$("#repo-sha").addEventListener("change", () => {
  if (!$("#repo-sha").value.trim()) $("#repo-sha").value = DEFAULT_COMMIT;
});

