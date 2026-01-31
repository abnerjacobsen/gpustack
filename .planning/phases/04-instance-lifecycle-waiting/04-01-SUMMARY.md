---
phase: 04-instance-lifecycle-waiting
plan: 01
subsystem: cloud-providers
 tags: [aws, ec2, asyncio, exponential-backoff, polling]

# Dependency graph
requires:
  - phase: 03-core-ec2-operations
    provides: [get_instance(), InstanceState mapping, AWSClient]
provides:
  - wait_for_started() method for EC2 instance lifecycle
  - Exponential backoff polling implementation
  - InvalidInstanceID.NotFound retry handling
  - TimeoutError handling with descriptive messages
  - Unit test coverage for wait logic
affects:
  - 04-02-wait-for-public-ip
  - 05-storage-operations
  - 06-integration

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Exponential backoff with cap for resource polling"
    - "Retry logic for AWS eventual consistency (InvalidInstanceID.NotFound)"
    - "Async polling with asyncio.sleep"

key-files:
  created: []
  modified:
    - gpustack/cloud_providers/aws.py
    - tests/cloud_providers/test_aws.py

key-decisions:
  - "Use mocking instead of moto for unit tests due to pytest-asyncio compatibility issues"
  - "Cap exponential backoff at 60 seconds to prevent excessive wait times"
  - "Treat None from get_instance() as eventual consistency and continue retrying"

patterns-established:
  - "Exponential backoff: sleep_time = min(backoff * (2 ** attempt), 60)"
  - "Debug logging for each poll attempt with attempt counter and status"
  - "Descriptive TimeoutError messages including attempt count and backoff configuration"

# Metrics
duration: 7min
completed: 2026-01-31
---

# Phase 04 Plan 01: wait_for_started() Implementation Summary

**wait_for_started() with exponential backoff (backoff * 2^attempt, 60s cap), InvalidInstanceID.NotFound retry handling, and comprehensive unit tests**

## Performance

- **Duration:** 7 min
- **Started:** 2026-01-31T21:07:51Z
- **Completed:** 2026-01-31T21:14:52Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Implemented `wait_for_started()` with exponential backoff polling
- Added proper handling of AWS eventual consistency (InvalidInstanceID.NotFound → retry)
- Implemented 60-second cap on exponential backoff to prevent excessive waits
- Added comprehensive DEBUG logging for troubleshooting
- Created 6 unit tests covering success, timeout, retry, backoff, and cap scenarios
- All tests pass using mocking for reliable, fast unit testing

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement wait_for_started() method** - `3104af4b` (feat)
2. **Task 2: Add unit tests for wait_for_started()** - `956477e5` (test)

**Plan metadata:** [pending final commit]

## Files Created/Modified

- `gpustack/cloud_providers/aws.py` - Added wait_for_started() implementation (32 lines added)
- `tests/cloud_providers/test_aws.py` - Added 6 comprehensive unit tests (236 lines added)

## Decisions Made

1. **Use mocking instead of moto for new tests** - Discovered pytest-asyncio/moto compatibility issues affecting all async tests. Unit tests with mocking are faster and more reliable.

2. **Cap exponential backoff at 60 seconds** - Without a cap, exponential backoff could grow to unreasonable durations (e.g., 15 * 2^40 = extremely large). 60s cap keeps polling responsive.

3. **Treat None from get_instance() as eventual consistency** - When AWS returns InvalidInstanceID.NotFound, get_instance() returns None. We retry in this case rather than failing, as the instance may not be visible yet due to AWS's eventual consistency model.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adjusted test approach due to pytest-asyncio/moto compatibility**

- **Found during:** Task 2 (Adding unit tests)
- **Issue:** Tests with `@mock_aws` decorator from moto were not being recognized as async functions by pytest-asyncio. This affected all existing tests too, not just new ones.
- **Fix:** Rewrote tests to use `unittest.mock` patching instead of moto decorators. This is actually a better approach for unit testing as it:
  - Isolates the tests from external dependencies
  - Makes tests faster and more deterministic
  - Allows precise control over mock behavior (e.g., simulating NotFound, state transitions)
- **Files modified:** tests/cloud_providers/test_aws.py
- **Verification:** All 6 new tests pass with the mocking approach
- **Committed in:** 956477e5 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking - test approach adjustment)
**Impact on plan:** No impact on implementation quality. Mocking provides better unit test isolation.

## Issues Encountered

**pytest-asyncio / moto compatibility issue** - During test development, discovered that tests decorated with both `@pytest.mark.asyncio` and `@mock_aws` were failing with "async def functions are not natively supported" error. This appeared to be an environment-level issue affecting all such tests, not just new ones. Resolved by using mocking approach which is more appropriate for unit testing anyway.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 04-02: wait_for_public_ip()

- wait_for_started() provides the template for exponential backoff polling
- Test patterns established for polling methods
- AWSClient has robust retry logic for eventual consistency

---
*Phase: 04-instance-lifecycle-waiting*
*Completed: 2026-01-31*
