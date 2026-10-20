## Pull Request Description
A summary of the changes made and the motivation behind them.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Security hardening
- [ ] Documentation update

## Safety & Security Checklist
- [ ] All changes operate strictly on local host (`127.0.0.1`).
- [ ] No external cloud API calls, telemetry, or remote trackers are introduced.
- [ ] Approved root containment is strictly preserved.
- [ ] No automatic deletions or silent overwrites.
- [ ] Dry-run simulation remains strictly read-only.
- [ ] Safe reversible undo is supported for any new operation types.

## Verification & Tests
- [ ] Ran `powershell -File scripts/run_tests.ps1` with all checks passing.
- [ ] Pytest backend test suite passed (including `test_security_audit.py`).
- [ ] Frontend `npx tsc --noEmit` and `npm run lint` passed.
- [ ] Only synthetic data or `tmp_path` fixtures were used during testing.
