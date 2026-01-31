---
phase: 01-foundation
plan: 01
subsystem: schema
tags: [pydantic, aws, cloud-provider, schema, validation]

# Dependency graph
requires: []
provides:
  - ClusterProvider.AWS enum member for provider selection
  - AWSConfig Pydantic schema with field validation
  - CloudCredential AWS compatibility documentation
  - Foundation for all subsequent AWS provider work
affects:
  - 01-foundation (plans 02, 03)
  - 02-ssh-keys
  - 03-ec2-operations
  - 04-wait-logic
  - 05-storage
  - 06-integration

# Tech tracking
tech-stack:
  added: [pydantic SecretStr for credential handling]
  patterns:
    - "Enum-based provider selection (follows DigitalOcean pattern)"
    - "Pydantic validators for AWS-specific format validation"
    - "SecretStr for sensitive credential storage"
    - "ConfigDict(extra=ignore) for forward compatibility"

key-files:
  created:
    - gpustack/schemas/aws.py - AWSConfig schema with validation
  modified:
    - gpustack/schemas/clusters.py - Added AWS to ClusterProvider enum, documented field mapping

key-decisions:
  - "AWS access key format: validates AKIA (long-term) or ASIA (temporary) prefix + 16 alphanumeric"
  - "AWS region format: validates lowercase pattern like us-east-1, eu-west-1"
  - "Secret_key uses SecretStr for secure handling in memory"
  - "CloudCredential.options dict stores AWS-specific settings (vpc_id, subnet_id, security_group_id)"

patterns-established:
  - "Provider enum extension: add to ClusterProvider following existing naming"
  - "Provider schema creation: create separate file in schemas/ following DigitalOcean pattern"
  - "Sensitive fields: use Pydantic SecretStr for keys/tokens"
  - "Validation: use field_validator for provider-specific format requirements"

# Metrics
duration: 1min
completed: 2026-01-31
---

# Phase 01 Plan 01: AWS Schema Foundation Summary

**AWS configuration schema with Pydantic validation, ClusterProvider enum extension, and SecretStr credential handling establishing the type foundation for AWS EC2 GPU integration**

## Performance

- **Duration:** 1 min
- **Started:** 2026-01-31T18:32:48Z
- **Completed:** 2026-01-31T18:33:53Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Extended ClusterProvider enum with AWS = "AWS" member following DigitalOcean pattern
- Created AWSConfig Pydantic schema with proper type hints and validators
- Implemented region format validation (lowercase with hyphens pattern)
- Implemented access key validation (AKIA/ASIA prefix + 16 alphanumeric)
- Used SecretStr for secret_key field for secure in-memory handling
- Added ConfigDict(extra="ignore") for forward compatibility
- Documented CloudCredential field mapping for AWS provider

## Task Commits

Each task was committed atomically:

1. **Task 1: Add AWS to ClusterProvider enum** - `6bfd17a` (feat)
2. **Task 2: Create AWSConfig schema** - `3dbba61` (feat)
3. **Task 3: Update CloudCredential options type support** - `2308b58` (docs)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `gpustack/schemas/aws.py` - New AWSConfig Pydantic model with:
  - Required fields: access_key, secret_key (SecretStr), region
  - Optional fields: vpc_id, subnet_id, security_group_id
  - Field validators for region format and access key format
  - ConfigDict for forward compatibility

- `gpustack/schemas/clusters.py` - Modified:
  - Added `AWS = "AWS"` to ClusterProvider enum (line 158)
  - Updated CloudCredentialBase docstring with AWS field mapping documentation

## Decisions Made

- **Access key validation pattern:** Used regex `^(AKIA|ASIA)[A-Z0-9]{16}$` to validate AWS access key format (20 chars, starts with AKIA for long-term or ASIA for temporary credentials)
- **Region validation pattern:** Used regex `^[a-z]{2}-[a-z]+-\d$` to validate AWS region format (e.g., us-east-1, eu-west-2)
- **Secret handling:** Used Pydantic SecretStr for secret_key to prevent accidental logging/exposure in memory
- **Options storage:** AWS-specific settings (vpc_id, subnet_id, security_group_id) stored in CloudCredential.options JSON field for flexibility

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed without issues.

## User Setup Required

None - no external service configuration required for schema foundation.

## Next Phase Readiness

- ✅ AWS enum member ready for provider selection logic
- ✅ AWSConfig schema ready for credential validation
- ✅ Field mapping documented for CloudCredential usage
- ✅ Type foundation complete for Phase 01 Plan 02 (AWS client)

Ready for `01-02-PLAN.md` - AWS client foundation with aiobotocore.

---
*Phase: 01-foundation*
*Completed: 2026-01-31*
