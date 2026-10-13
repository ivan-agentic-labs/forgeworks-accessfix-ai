# AccessFix AI — Complete Detailed Project Specification

**Version:** 2.2.0-detailed-full  
**Date:** 2026-10-13  
**Status:** FINAL  

> AccessFix AI audits websites whose ownership has been verified, maps findings to source code only when confidence is high, proposes patches, requires human keyboard and screen-reader review, and creates draft pull requests. It never claims full WCAG conformance from automated results.

---

## 1. Executive Definition

AccessFix AI is designed for teams that want to find and fix accessibility issues without risking unverified scans or unreviewed code changes. Ownership proof is mandatory. Human review is mandatory before any pull request. Automated scanning and retesting support the process but do not replace human judgment for critical issues.

---

## 2. Detailed Workflow

1. User initiates a domain ownership challenge (DNS TXT or well-known file).
2. System verifies the challenge with retries and a 24-hour expiry.
3. Only after verification does the system allow a scan against an allowlisted HTTPS target.
4. Network policy blocks private IPs, metadata endpoints, and unsafe redirects.
5. Isolated browser runs Playwright + axe and records findings plus coverage.
6. Source mapping occurs only for high-confidence matches against the versioned support matrix (Next.js/React patterns).
7. Patch proposal is generated for high-confidence findings.
8. Retest runs on the patched page (targeted findings + lightweight full scan).
9. Reviewer completes the keyboard and screen-reader checklist.
10. Approval binds to the patch digest.
11. Draft pull request is created with a fixed template. No auto-merge.

---

## 3. Ownership Challenge Detail

DNS TXT: query `_accessfix-challenge.domain`, up to 3 retries, 30-second intervals, 5-minute total timeout.  
File method: fetch `/.well-known/accessfix-challenge.txt`, up to 2 retries.  
Success requires exact token match. Failed or expired challenges block all further actions.

---

## 4. Findings, Mapping, and Coverage

Finding includes rule id, impact, node selector, and source mapping confidence.  
Coverage = rules checked / rules applicable for the detected page type.  
Page type is determined by URL pattern + DOM heuristics (form, navigation, content, landing, other).  
Only high confidence generates a source patch. Medium/low produce finding-only results.

---

## 5. Human Review and Pull Request

Checklist items: keyboard navigation, logical focus order, correct screen-reader announcement (or explicit minor waiver), no new critical issues.  
Critical and serious findings cannot be waived.  
PR body must include findings list, coverage, patch digest, evidence link, and draft statement.  
Concurrent scans limited (default 2 per workspace).

---

## 6. Evidence and Limits

Evidence ZIP contains findings, coverage, patch diff, approval, and ownership proof. Retained 2 years.  
Rule matrix is versioned and recorded per scan.  
Permission revocation aborts the job safely.

---

## 7. Closing

All rules above are final for P0. AccessFix AI will not scan without ownership proof and will not open a pull request without recorded human review.

*End of AccessFix AI Complete Detailed Specification*
