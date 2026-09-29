# FL-6 Launch Acceptance

Issue: #49  
Branch: `feature/fl-6-launch-hardening`  
Customer app: `Main/`  
Date: 2026-09-29

Status values are only:

- **AUTOMATED — PASS** when a test or static export in this package exercised the behaviour
- **MANUAL — PASS** when a person completed the live flow
- **UNVERIFIED — BLOCKER** when it was not exercised, or a required policy fact is unpublished

Nothing is marked verified because the code “looks right”.

## Launch blockers requiring owner action

These are unpublished **policy** facts. The routes exist; the product must not invent the missing commitments.

1. **CV / personal-data retention period** — Engine contract V1.2 §22 says retention must be defined before production launch. Not defined in the repo.
2. **Deletion schedule and customer deletion / access process** — same contract requirement; no published process or contact channel.
3. **Consent / lawful-basis wording** — not an approved legal text in the repo.
4. **Refund eligibility, window, and method** — R159 one-time Paystack charge is implemented; a refund rule is not.
5. **Public support contact** — no email, phone, or ticket address exists in the repo.
6. **Live Paystack Test Mode + mailbox confirmation** — this environment cannot complete a real Paystack charge or confirm-email.

Until 1–5 are approved and 6 is walked by an owner, this is **not a production-legal launch**.

## Happy-path flows

| Flow | Result | Evidence |
|---|---|---|
| Anonymous assessment → preview | AUTOMATED — PASS | `assessment-form-test.tsx` submit → preview; `preview-summary-test.tsx` free fields only |
| Preview → auth → claim | AUTOMATED — PASS | `flow-test.ts` routes to auth without session; claim continuation; `auth-screen-test.tsx` resume after sign-in |
| Sign-up + confirmation → resume | UNVERIFIED — BLOCKER | Needs live mailbox / Supabase confirm-email. Automated coverage stops at `confirm_email` UI (`auth-screen-test.tsx`, `auth-test.ts`) |
| Sign-in → resume | AUTOMATED — PASS | `auth-screen-test.tsx` resumes payment for original assessment; `auth-test.ts` caches token |
| Claim → checkout | AUTOMATED — PASS | `flow-test.ts` claimed → checkout; `payment-waiting-test.tsx` order summary then Continue |
| Checkout opened → waiting | AUTOMATED — PASS | `payment-waiting-test.tsx` starts checkout once, then waiting; does not auto-start |
| Waiting → delayed | AUTOMATED — PASS | `auth-checkout-recovery-test.ts` `shouldMarkPaymentDelayed(20, 20, true)`; copy in `payment.tsx` says do not pay again |
| Payment confirmation → unlocked report (client rule) | AUTOMATED — PASS | `payment-waiting-test.tsx` replace to report only after `checkReportUnlock` unlocked; `flow-test.ts` REPORT_LOCKED stays waiting |
| Live Paystack Test Mode charge → webhook unlock | UNVERIFIED — BLOCKER | Requires owner on Test Mode Paystack + deployed API |
| Report refresh | AUTOMATED — PASS | Report screen loads via `checkReportUnlock` / `GET .../report` (`report-screen-test.tsx`) |
| Close browser → sign in → My Reports → purchased report (client) | AUTOMATED — PASS | `my-reports-test.tsx` list from `GET /api/v1/assessments`; `loadPendingAssessment` never called; UNLOCKED opens `/report` |
| Same flow on live account after a real purchase | UNVERIFIED — BLOCKER | Requires owner on deployed API + mailbox |
| Sign out → protected report → auth → resume | AUTOMATED — PASS | Report screen replaces unsigned users to sign-in with `next=report`; `auth-resume.ts` tested |

## Blocked / failure paths

| Flow | Result | Evidence |
|---|---|---|
| Wrong owner | AUTOMATED — PASS | `report-screen-test.tsx`; `flow-test.ts` blocks payment on wrong-owner |
| Locked report | AUTOMATED — PASS | `flow-test.ts` REPORT_LOCKED; report screen locked PageState |
| Invalid CV | AUTOMATED — PASS | `assessment-form-test.tsx` rejects non PDF/DOCX |
| Oversized / unsupported CV | AUTOMATED — PASS | `validatePickedCv` 10 MB; form test |
| Malformed evidence URL | AUTOMATED — PASS | `assessment-workspace-test.ts`; form blocks submit |
| REVIEW_REQUIRED | AUTOMATED — PASS | `assessment-form-test.tsx` no payment CTA |
| NOT_SCORABLE | AUTOMATED — PASS | same |
| Offline / network failure | AUTOMATED — PASS | `api-client-test.ts` maps fetch failure to `ASSESSMENT_SERVICE_UNAVAILABLE` |
| API unavailable | AUTOMATED — PASS | same; My Reports PageState `my-reports-test.tsx` |
| Delayed payment | AUTOMATED — PASS | workspace helper + payment copy |
| Payment-init failure | AUTOMATED — PASS | `flow-test.ts` blocked/error checkout paths; duplicate init blocked |
| Expired session | AUTOMATED — PASS | My Reports and report `next=reports` / `next=report`; auth screens |
| Missing preview | AUTOMATED — PASS | preview/payment recovery PageState in app screens; flow blocked statuses |
| Missing assessment | AUTOMATED — PASS | API error codes preserved; PageState pattern |
| 404 | AUTOMATED — PASS | `legal-surfaces-test.tsx` not-found PageState |
| Mobile layout (code constraints) | AUTOMATED — PASS | compact preview/report type; workspace stacks under tablet; overflow-wrap CSS; `export:web` includes legal routes |
| Mobile layout on a physical phone | UNVERIFIED — BLOCKER | Owner visual pass at ~390px |
| Keyboard-only (primitive semantics) | AUTOMATED — PASS | accordion `accessibilityState.expanded`; radios `checked`; skip link; focus-visible CSS; field errors with the control |
| Keyboard-only tour of every launch screen | UNVERIFIED — BLOCKER | Owner Tab/Enter pass: assessment, auth, checkout, report accordion, account menu, legal |
| Reduced motion (CSS + hook) | AUTOMATED — PASS | `foundations-test.tsx` hook; report bars determinate; landing/foundations CSS disable motion |
| Reduced motion visual pass on landing + report | UNVERIFIED — BLOCKER | Owner `prefers-reduced-motion` check |

## Payment rules (locked)

| Rule | Result | Evidence |
|---|---|---|
| Checkout never auto-launches | AUTOMATED — PASS | `payment-waiting-test.tsx` |
| Duplicate initialization blocked | AUTOMATED — PASS | `payment-workspace.ts` + `flow-test.ts` in-flight lock |
| Return from Paystack is not payment proof | AUTOMATED — PASS | waiting/locked until report 200 |
| Delayed confirmation says do not pay again | AUTOMATED — PASS | `payment.tsx` delayed copy |
| Only backend-confirmed entitlement unlocks paid content | AUTOMATED — PASS | report 200 / `readiness.report.v1` |
| Paystack Test Mode unchanged | AUTOMATED — PASS | no Server files in this package |

## Report / account

| Rule | Result | Evidence |
|---|---|---|
| Paid content only after protected report 200 | AUTOMATED — PASS | `report-screen-test.tsx` |
| My Reports after fresh login without pending storage | AUTOMATED — PASS | `my-reports-test.tsx` |
| PREVIEW cannot masquerade as purchased | AUTOMATED — PASS | locked badge + payment continuation |
| UNLOCKED still fetches protected report | AUTOMATED — PASS | View report → `/report` + bearer GET |
| Wrong owner fails closed | AUTOMATED — PASS | no `full-report` |
| Priority actions backend-ordered | AUTOMATED — PASS | `readiness-report-test.tsx` |
| No frontend rescoring | AUTOMATED — PASS | view maps backend fields only |
| Strength / Areas to strengthen overlap is explanatory | AUTOMATED — PASS | overlap copy; source arrays unchanged |

## Legal routes

| Route | Result | Evidence |
|---|---|---|
| `/privacy` | AUTOMATED — PASS | `legal-surfaces-test.tsx`; unpublished retention called out |
| `/terms` | AUTOMATED — PASS | same |
| `/refunds` | AUTOMATED — PASS | unpublished refund rule called out |
| `/support` | AUTOMATED — PASS | unpublished contact channel called out |
| Footer + landing legal hrefs | AUTOMATED — PASS | footer hrefs; `MARKETING_FOOTER_LINKS` `/privacy` `/terms` `/refunds` `/support`; CV Privacy notice |
| `/map-pack` honest placeholder | AUTOMATED — PASS | no fake checkout |

## What the owner still has to do

On **Paystack Test Mode**, with the deployed API and a real mailbox:

1. Complete anonymous assessment → preview on web (desktop and a ~390px phone).
2. Sign up, confirm email, resume to checkout.
3. Pay R159 in Paystack Test Mode once; confirm waiting does not unlock; confirm webhook/backend unlocks; open report; refresh report.
4. Close the browser, sign in later, open My Reports, reopen the purchased report.
5. Sign out, hit the report URL, sign in, land back on the report.
6. Keyboard-only pass: assessment, auth, checkout, report accordion, account menu, legal pages.
7. `prefers-reduced-motion` visual pass on landing + report bars.
8. Approve or write: retention, deletion/access process, refund rule, support address — then replace the unpublished banners.

Do not treat this document as green for production until those owner steps and policy decisions are done.
