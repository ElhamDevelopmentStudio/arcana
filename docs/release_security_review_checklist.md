# Release Security Review Checklist

Use this checklist before each release to confirm security controls, evidence, and sign-offs are complete.

## Release Security Review Checklist

### Control 1: Threat model and scope revalidation
- objective: Reconfirm threat boundaries and high-risk flows affected by the release scope.
- required_inputs: release diff summary, data-flow impact map, trust-boundary updates, threat-model owner.
- completion_criteria: Updated threat assumptions are documented and approved for all changed surfaces.

### Control 2: Secrets and credential handling verification
- objective: Ensure secrets, API keys, and environment credentials are not exposed or mishandled by release changes.
- required_inputs: secret inventory, rotation status, redaction checks, env-var and config diffs.
- completion_criteria: No plaintext secrets are exposed in logs, exports, or configs; rotation and storage policies remain enforced.

### Control 3: Authorization boundary and data isolation checks
- objective: Validate access controls and project-tenant isolation behavior across modified endpoints and jobs.
- required_inputs: authz test results, principal-role matrix updates, cross-project isolation checks, failure-mode review.
- completion_criteria: Unauthorized requests are denied correctly and tenant/project isolation remains intact under regression tests.

### Control 4: Dependency and supply-chain vulnerability review
- objective: Review dependency updates and build/runtime artifacts for newly introduced vulnerability or integrity risk.
- required_inputs: dependency diff, vulnerability scan output, package integrity checks, remediation plan for findings.
- completion_criteria: No unapproved high/critical findings remain unresolved at release time.

### Control 5: Security testing and abuse-case validation
- objective: Execute targeted security regressions for high-risk behaviors (input handling, export integrity, privilege misuse).
- required_inputs: test plan, exploit/abuse scenarios, test execution logs, fix verification evidence.
- completion_criteria: Security regression suite passes and known abuse paths are either mitigated or explicitly risk-accepted.

### Control 6: Security sign-off, incident readiness, and audit trail
- objective: Capture final security approval, operational response readiness, and auditable release evidence.
- required_inputs: approver list, incident escalation path, monitoring/alert checklist, signed release record.
- completion_criteria: Release has explicit security sign-off with traceable evidence and on-call response readiness.
