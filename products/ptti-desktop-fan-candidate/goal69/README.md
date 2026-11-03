# Cinema 3.1 Safe Start

The original Alpha checks natural input idle immediately inside `run_gui()`.
A normal double-click is real input, so starting directly can fail its 60-second
gate. This optional entry accepts one explicit request and waits visibly for
actual system idle. It does not replace or modify the original EXE or shortcuts.

The waiting UI uses the approved local Python/Tk runtime. It polls read-only
`GetLastInputInfo`; any input naturally resets the reported idle. It does not
inject input, fake the clock, edit environment guards or use a service. The user
can cancel, close the window, or let the request expire after ten minutes.

At actual launch it checks the fixed release SHA, every payload file, exact EXE
SHA, RAM >=2.5 GiB, idle >=60 seconds, accessible Default input desktop and free
port 4212. A named mutex prevents two Safe Start requests. Only one child launch
is attempted. The original EXE independently runs its own unchanged guards.
The waiting window exits after a live child is observed; it never kills it.

Target: `0.1.11-grand-ab484d6` (San ab484d6, original Host 532975ad).
This helper does not rebuild, sign, update or activate that Alpha.

Install only to a new tool directory and create the separately named desktop
shortcut `PTTI Cinema 3.1 Safe Start`. The installer must refuse an existing
destination, preserve the three original PTTI shortcuts and record their hashes.
Never add startup registration or an ExecutionPolicy bypass.

Logs are local `logs/*.jsonl` plus original-child stdout/stderr; they contain
only this request's guard state, events, PID and errors. They do not inspect
Journal, videos or match databases. Close/cancel affects only this request.

Rollback: leave the new shortcut unused; original entries remain untouched.
No user configuration is migrated or cleaned. GUI acceptance is separate from
the offline state/identity checks: `python -B -m unittest discover -s tests -v`.
