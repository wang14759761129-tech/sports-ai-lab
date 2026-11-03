# GOAL16.7 Desktop selector release approval

**Disposition: READY_FOR_APPROVAL**

**Requested operation:** replace exactly `<LOCAL_USER_ROOT>\PTTI\Launcher\Start-PTTI.ps1` with the reviewed candidate, using an atomic same-volume replacement.
**Execution status:** not applied. No supported approval submission channel is exposed in this environment; the earlier production replacement was blocked by policy. No retry or alternate write method was used.

## Fixed identities

| Artifact | SHA-256 | Evidence |
|---|---|---|
| Current formal selector and rollback original | `277069C5BD9BC4D95780EDC38BF1866978B48DECA03B4E0ADAA6A84E4C3BF2B1` | Current file was read and hashed; rollback copy is byte-identical. |
| Proposed selector candidate | `8B82070ECFD42EE83EBC70AA3357041734C0E81BA13736DE3E53F5EC86070356` | Full candidate source is included in `candidate/Start-PTTI.ps1.candidate`. |
| Full current-to-candidate unified diff | `A03E54610682C7BC751F6037BD886D79A9AFF43B9C29D1EBF4A865393582F4CC` | `selector-change.diff` |
| GOAL16.6 original patch, preserved from commit `1d3af88ccc1bbcbc4ed8eff5b925c8777bd92f2d` | `B741DE36C038383E8E3238E85F575AE7D92BBEAE3EFF7004D0480CA9471D1005` | `evidence/GOAL16.6-original-process-identity.patch` |
| 0.1.4 `release.json` | `FFD47565DB68482542AFD543E74A751F5EE08AEE3E57960EE6DFC4A34CEE8E32` | Candidate package manifest, 175 payload files verified with zero hash mismatches. |
| 0.1.4 Desktop Host EXE | `EDC7EFC5416DC5F53337CD1276B4EE6DF08DDBB04119A6745247784DA76C190D` | Candidate binary; it was not rebuilt or changed in this handoff. |

The 0.1.4 manifest pins `native_selector_sha256` to `277069C5BD9BC4D95780EDC38BF1866978B48DECA03B4E0ADAA6A84E4C3BF2B1`, matching the formal selector at the start of this review. The independent selector candidate is an approval artifact paired to that exact base. The running 0.1.4 GUI process remains the existing build and does not incorporate this source patch.

## Candidate review and test evidence

The previous selector used `Name -like 'PTTI*.exe'`, which matched both Fan versions. The candidate requires the known R4 SHA-256 plus live process path and PID inspection. It hashes the verified target once per dispatch. Same-basename processes at alternate paths are identified by their content hash; an unreadable same-basename process blocks launch safely. Snapshot acquisition now occurs inside the helper after identity verification. The selector repeats the RAM guard and process snapshot immediately before dispatch.

The candidate temporarily opens `current-preview.json` and the existing `previous-preview.json` with read sharing only. This prevents pointer mutation/replacement through the verify-and-launch sequence; the lease closes when dispatch exits. If a writer is active, the launch fails closed. A process started manually after the final snapshot can still race with launch because it does not share the selector mutex; this residual is not represented as eliminated.

Tests in `evidence/test-output.txt`:

- PowerShell parse: candidate and test scripts PASS.
- Process identity: 11 simulated cases PASS (Fan only, R4 exact path, coexistence, impostor path, unreadable path, exit/PID reuse, hash drift, alternate same-hash path, unavailable snapshot).
- Pointer lease: write/replacement blocked while leased; allowed after release, PASS.
- QA database isolation: 7 Python tests PASS using synthetic test databases only.
- No official selector invocation, R4 launch, or live database access occurred during this review.

The 0.1.4 release package remains version `0.1.4-fan-072c57a`, San commit `072c57a4d16c4e7fead452a22eb378f2a7a9f633`. Current read-only process/port snapshot: PID 7532 owns 4201 and PID 14052 owns 4200. No second instance was started. The prior GUI acceptance remains the evidence for 0.1.4; this handoff did not repeat GUI testing. Fan → R4 → return remains NOT_TESTED.

## QA database isolation and cleanup

Candidate QA preparation creates a UUID session below `%TEMP%\PTTI-GOAL16-R4-QA\`, copies the configured preview database through SQLite read-only backup, verifies `PRAGMA quick_check`, and sets `PTTI_PREVIEW_QA_DB`, `PTTI_DB`, `PTTI_ENV=test`, and an isolated `LOCALAPPDATA` profile. The R4 code enforces that the QA database path is under the system temporary directory. The tests verify changes to a synthetic QA clone do not change the synthetic source database.

The host currently does not auto-delete the QA session when its window closes. That is deliberate for safety: separately launched R4 can outlive the Fan host. Cleanup is only safe after the exact R4 process is verified exited; then an authorized operator can remove that session folder. No real QA session or DB copy was created in this review, and the live DB was not read, copied, hashed, or modified.

## Risks and rollback

- The desktop EXE is still marked `UNSIGNED_CANDIDATE`; fixed hashes provide integrity identity, not publisher signature validation.
- External/manual R4 starts can race after the last process snapshot. The selector's mutex serializes selector requests only.
- The pointer lease briefly prevents a release updater from replacing the two pointer files; a conflict fails closed and can be retried after the other operation finishes.
- Current baseline mismatch is a hard stop; do not apply this diff to a selector whose hash differs from `277069C5BD9BC4D95780EDC38BF1866978B48DECA03B4E0ADAA6A84E4C3BF2B1`.

Rollback file: `rollback/Start-PTTI.ps1.original`, SHA-256 `277069C5BD9BC4D95780EDC38BF1866978B48DECA03B4E0ADAA6A84E4C3BF2B1`, byte-identical to the currently protected selector. Approved executor must recheck the live baseline immediately before change; stage candidate and backup beside the target on the same volume; perform one atomic replace; verify the new SHA; preserve the original backup. If post-replacement verification fails, restore the rollback file by the same atomic operation and verify `277069C5BD9BC4D95780EDC38BF1866978B48DECA03B4E0ADAA6A84E4C3BF2B1`. Do not use direct truncation, non-atomic writes, a second dispatcher, or an alternate execution path.

## Minimum acceptance after approval

1. Confirm formal selector SHA still equals `277069C5BD9BC4D95780EDC38BF1866978B48DECA03B4E0ADAA6A84E4C3BF2B1`; atomically replace and confirm `8B82070ECFD42EE83EBC70AA3357041734C0E81BA13736DE3E53F5EC86070356`.
2. Click the real desktop selector: Fan opens; select Native once; verify R4 opens and return to Fan works. Record screenshots and selector/host logs.
3. Verify the QA R4 DB path is in the unique temp session and run `PRAGMA quick_check` on the isolated copy; verify the live DB remains unchanged through the authorized integrity check.
4. Close and reopen the Fan candidate; verify Favorites, Watch, Notes and JSON export/import persist.
5. Execute the documented atomic rollback once in a controlled check; confirm the selector returns to `277069C5BD9BC4D95780EDC38BF1866978B48DECA03B4E0ADAA6A84E4C3BF2B1` and R4 remains available.

Approval is still external. Until approval and real acceptance, this package is **READY_FOR_APPROVAL**, not COMPLETE.
