# GPUStack AWS Cloud Provider - Project State

**Project:** AWS EC2 GPU Integration for GPUStack  
**Current Phase:** 2 - SSH Key Management  
**Last Updated:** 2026-01-31  
**Status:** In Progress - Phase 1 Complete, ready for Phase 2

---

## Project Reference

**Core Value:** Users can provision and manage GPU-enabled EC2 instances on AWS directly from GPUStack

**Key Decisions:**
- **AWS SDK:** aiobotocore 3.1.1 for native async support
- **Pattern:** Follow existing DigitalOcean provider implementation
- **Scope:** v1 covers EC2, EBS, basic networking; v2 adds Spot, cost optimization
- **Factory Registration:** AWSClient registered with credential extraction lambda
- **Credential Validation:** EC2 describe_regions for lightweight auth check
- **Testing:** moto mock_aws decorator for AWS API mocking

**Constraints:**
- Python 3.10+, async codebase (FastAPI, SQLModel)
- Black (88 char), flake8, type hints required
- pytest with moto for AWS mocking

---

## Current Position

**Active Phase:** Phase 2 - SSH Key Management (2 of 6)

**Previous Phase:** Phase 1 - Foundation & Configuration ✓ **COMPLETE**

**Phase 1 Plans:**
| Plan | Status | Key Deliverable |
|------|--------|-----------------|
| 01-01 | ✓ Complete | AWSConfig schema, ClusterProvider.AWS enum |
| 01-02 | ✓ Complete | AWSClient with aiobotocore integration |
| 01-03 | ✓ Complete | Factory integration, credential validation, tests |

**Next Plan:** 02-01 - SSH Key Management (EC2 key pair operations)

**Status:** Phase 1 complete, ready for Phase 2

**Last activity:** 2026-01-31 - Completed 01-03-PLAN.md (Factory Integration)

**Phase Progress:**
```
Overall: [████░░░░░░] 33% (1/6 phases complete, 1 in progress)
Phase 1: [██████████] 100% (3/3 plans complete) ✓
Phase 2: [░░░░░░░░░░] 0% (Not started)
Phase 3: [░░░░░░░░░░] 0% (Not started)
Phase 4: [░░░░░░░░░░] 0% (Not started)
Phase 5: [░░░░░░░░░░] 0% (Not started)
Phase 6: [░░░░░░░░░░] 0% (Not started)
```

**Current Focus:** Phase 2 - SSH key pair management for AWS EC2

---

## Performance Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Requirements mapped | 39/39 | 39/39 ✓ |
| Phases defined | 6 | 6 ✓ |
| Success criteria defined | 27 | 27 ✓ |
| Phase 1 complete | ✓ | ✓ |
| AWSClient implemented | ✓ | ✓ |
| Factory integration | ✓ | ✓ |
| Test coverage | TBD | >80% |
| AWS integration | In Progress | Complete |
| Phase 2 started | Pending | In Progress |

---

## Accumulated Context

### Key Technical Decisions (Confirmed)

| Decision | Options | Status |
|----------|---------|--------|
| Async AWS SDK | aiobotocore vs boto3+to_thread | → aiobotocore selected |
| Instance families | p3, p4d, g4dn, g5 | → All four for v1 |
| AMI strategy | Deep Learning AMI vs custom | → DL AMI per region |
| Network defaults | Default VPC vs custom | → Default VPC for v1 |
| Access key format | AKIA/ASIA prefix + 16 alphanumeric | → Implemented in 01-01 |
| Region format | lowercase-hyphen pattern | → Implemented in 01-01 |
| Secret handling | SecretStr vs plain string | → SecretStr selected |
| Retry policy | max_attempts=10 with adaptive mode | → Implemented in 01-02 |
| Factory registration | Lambda extraction from CloudCredential | → Implemented in 01-03 |
| Credential validation | EC2 describe_regions | → Implemented in 01-03 |
| Testing approach | moto mock_aws | → Implemented in 01-03 |

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| AWS eventual consistency | High | Exponential backoff in WAIT phase (max_attempts=10 configured) |
| Rate limiting | Medium | Retry policy (10 attempts) configured in AWSClient |
| IAM permissions | High | Document minimum permissions, test with restricted role |
| AMI compatibility | Medium | Validate GPU accessibility in Phase 3 |

### Open Questions

1. **AMI maintenance:** How are AMI IDs kept current across regions?
2. **IAM testing:** Need restricted role for permission validation
3. **Cost concerns:** Real AWS testing costs in Phase 6

### Blockers

None currently.

---

## Phase History

| Phase | Status | Completed | Key Outcomes |
|-------|--------|-----------|--------------|
| Planning | Complete | 2026-01-31 | Roadmap created, 6 phases defined |
| Phase 1 | **Complete** | 2026-01-31 | AWS Schema, AWSClient, Factory integration, Tests |
| Phase 2 | Pending | - | SSH key management |
| Phase 3 | Pending | - | Core EC2 operations |
| Phase 4 | Pending | - | Instance waiting logic |
| Phase 5 | Pending | - | EBS storage |
| Phase 6 | Pending | - | Integration & testing |

---

## Session Continuity

**Last Action:** Completed 01-03-PLAN.md - Factory Integration

**Next Actions:**
1. Begin `02-ssh-keys-PLAN.md` - SSH Key Management for AWS EC2
2. Implement create_ssh_key() and delete_ssh_key() methods in AWSClient
3. Add EC2 key pair operations with moto tests

**Context for Next Session:**
- Phase 1 Foundation is complete ✓
- AWSClient registered in factory with `ClusterProvider.AWS`
- Credential validation working via `validate_credentials()`
- Unit tests established with moto mocking
- Files created: `gpustack/schemas/aws.py`, `gpustack/cloud_providers/aws.py`, `tests/cloud_providers/test_aws.py`
- Files modified: `gpustack/schemas/clusters.py`, `gpustack/cloud_providers/common.py`, `pyproject.toml`

---

*State file: Auto-updated throughout project lifecycle*
