# Release Checklist

Use this before merging or pushing a deployment branch.

## Scope Check

Confirm the branch contains only the intended work:

```powershell
git status --short --branch
git diff --stat origin/main...HEAD
git diff --name-only origin/main...HEAD
```

Review changed files for unrelated feature work. Deployment branches should not
include unfinished product features.

## Parked Feature Check

Search for features that are intentionally out of scope:

```powershell
rg -n "MFA|mfa|OTP|otp|django_otp|qrcode|TOTP|mfa/setup"
```

For now, active branches may mention MFA only in documentation that clearly says
it is a future option.

## Verification

Run the lightest relevant checks:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pytest -q
```

If the full suite is too slow for the change, run focused tests and state that
in the PR or handoff note.

## Deployment Branch Hygiene

- Keep deployment fixes separate from product features.
- Keep one branch per active purpose.
- Delete temporary local safety branches after their work is either committed,
  intentionally parked, or no longer needed.
- Do not rewrite or reset shared branches unless the team agrees first.

## Push Checklist

Before pushing:

```powershell
git log --oneline -5
git status --short --branch
```

Make sure the branch name, commit message, and changed files match the intended
release scope.

