# Verification Protocol

## Mandatory Architect Verification

**HARD RULE: Never claim completion without Architect approval.**

1. Complete all work
2. Spawn Architect verify
3. WAIT for result
4. If APPROVED → done
5. If REJECTED → fix and re-verify

## Verification-Before-Completion Protocol

**Iron Law:** NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE

| Claim | Required Evidence |
|-------|-------------------|
| "Fixed" | Test showing it passes now |
| "Implemented" | lsp_diagnostics clean + build pass |
| "Refactored" | All tests still pass |
| "Debugged" | Root cause identified with file:line |

## Continuation Enforcement

Before concluding ANY session, verify:
- [ ] TODO LIST: Zero pending/in_progress tasks
- [ ] FUNCTIONALITY: All requested features work
- [ ] TESTS: All tests pass (if applicable)
- [ ] ERRORS: Zero unaddressed errors
- [ ] ARCHITECT: Verification passed

**If ANY unchecked → CONTINUE WORKING.**
