# Packing hourly performance metrics — missing benchmarks

Scope: **Packing only** (`Packing`, `Manual Packing`, `ASRS Packing`).
Owners: Sakshi Nayan and Avinash Jadhav, per the Win Dev catchup on 2-Sep-2026.

## Root cause (confirmed in the 2-Sep catchup)

Packing benchmarks render blank because **`Manual Packing` and `ASRS Packing`
are not being combined**, so the **join between the productivity table and the
performance table fails — the `UniqueKey` values don't match**.

This is a keying problem, not a job or execution problem. The performance rows
may well exist in `HourlyPerformanceMetrics`, keyed per packing sub-type, while
the productivity side carries one combined packing bucket. The join drops them
and the dashboard shows nothing.

Two consequences worth being explicit about:

- **Re-running the SP as it stands fixes nothing.** It will regenerate the same
  unmatchable keys. The SP change comes first, the re-run second.
- **The rows are probably not missing.** Before deleting anything, confirm with
  script `04` whether you are looking at absent rows or unjoinable ones — the
  remediation is the same, but the verification afterwards is different.

## Agreed remediation

1. Modify `dbo.spPerformance_Packing_Hourly01` to combine the packing
   sub-types so the emitted `UniqueKey` matches the productivity side.
2. Delete packing records from **25-Aug** onward and re-run.
3. Verify the join now resolves for every packing hour.

Note the date discrepancy in the meeting record: the discussion says *"from the
25th onward"*, the action item says *"from the 26th onwards"*. Scripts default
to the 25th (wider window; re-running an already-correct day is a no-op given
the SP's own DELETE + INSERT). Confirm with Aniket if that is wrong.

## Scripts

| Script | Purpose |
|---|---|
| `04_packing_uniquekey_mismatch.sql` | **Start here.** Proves the mismatch and shows which side splits the sub-types |
| `01_packing_source_vs_metrics.sql` | Confirms DCMImport has the packing hours, so the fix is downstream of the import |
| `02_find_active_job_and_sp.sql` | Locates the owning SP and Agent job — needed for the SP's parameter signature (2b) before the re-run |
| `03_packing_rerun_backfill.sql` | Reversible re-run, **after** the SP change |

Run order: `04` → `01` → `02b` → *SP change* → `03` → `04` again to verify no
unmatched keys remain.

## The trap in the SP change

Combining the sub-types means summing `EstimatedTime` and `ActualTime` across
`Manual Packing` and `ASRS Packing` **before** deriving
`PerformancePercentage`. Averaging the two sub-type percentages produces a
different — and wrong — number any time the two volumes differ. Script `04d`
prints the per-hour split so the combined totals can be checked against the
sub-type totals.

Also confirm what the combined row's `TaskType` should be written as
(`'Packing'` vs something else), since that value likely feeds `UniqueKey`
construction and therefore the join itself.

## Rules

- Do not `UPDATE`/`INSERT` `HourlyPerformanceMetrics` by hand — every value
  comes from the SP.
- Do not change `Hourly_KPI.TaskType`.
- Take the snapshot in `03a` before the delete/re-run; `03e` is the rollback.
- Confirm the SP's parameter signature (`02b`) before editing the `EXEC` in
  `03c`.

## Open items — not Packing, deliberately not addressed here

- **Manual Picking** — KPI rows exist, metric rows missing. Check
  `Manual Picking` vs `Manual Picking - Direct` naming first; this may be the
  same class of keying bug as Packing.
- **ASRS Picking** — `spPerformance_Picking_Hourly_Detailed_Calculation`
  filters `di.TaskType = 'Manual Picking'` only, so ASRS Picking is never
  calculated at all. Either another SP owns it, or the picking calculation
  needs extending — a business-logic change needing sign-off.
