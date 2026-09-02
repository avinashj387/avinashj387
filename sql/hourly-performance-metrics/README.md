# Packing hourly performance metrics — missing benchmarks

Scope: **Packing only** (`Packing`, `Manual Packing`, `ASRS Packing`).
Owners: Sakshi Nayan and Avinash Jadhav, per the Win Dev catchup on 2-Sep-2026.

## Root cause (confirmed in the 2-Sep catchup)

Packing benchmarks render blank because **`Manual Packing` and `ASRS Packing`
are not being combined**, so the **join between the productivity table and the
performance table fails — the `UniqueKey` values don't match**.

**Located, in the SP's final `SELECT ... INTO #FinalResult`:**

```sql
GROUP BY hn.Hour, fd.TaskType     -- emits a row per hour PER SUB-TYPE
```

Grouping by `TaskType` writes a separate `Manual Packing` row and `ASRS
Packing` row for the same hour. The productivity side carries one combined
packing bucket, so the `UniqueKey` built from those rows can never match.

The rows are therefore **not missing** — they are in
`HourlyPerformanceMetrics`, sub-typed and unjoinable.

One detail explains why the symptom looks like data that *stopped* rather than
data that is mis-keyed. The same statement selects
`ISNULL(fd.TaskType, 'Packing')`, so an hour with **no** packing data misses
the `LEFT JOIN`, comes back `NULL`, and is relabelled `'Packing'` — which
matches fine. Empty hours join; busy hours don't.

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
| `05_packing_sp_fix.sql` | **The fix.** Corrected `#FinalResult` statement, plus four things to confirm before applying |
| `04_packing_uniquekey_mismatch.sql` | Proves the mismatch and shows which side splits the sub-types |
| `01_packing_source_vs_metrics.sql` | Confirms DCMImport has the packing hours, so the fix is downstream of the import |
| `02_find_active_job_and_sp.sql` | Locates the owning SP and Agent job — needed for the SP's parameter signature (2b) before the re-run |
| `03_packing_rerun_backfill.sql` | Reversible re-run, **after** the SP change |

Run order: `04` → `02b` → `05` (apply) → `03` (delete + re-run from 25-Aug) →
`04` again to verify no unmatched keys remain. `01` is only needed if `04`
suggests the source itself is short.

## The change

Two lines, in `05`: drop `fd.TaskType` from the `GROUP BY`, and select the
literal `'Packing'` instead of `ISNULL(fd.TaskType, 'Packing')`.

The percentage math needs no other change and **must not** be turned into an
average — it already sums estimated and actual across the group before
dividing, which is the correct way to combine sub-types. Averaging the Manual
and ASRS percentages gives a wrong number whenever the two volumes differ.

Four things to confirm before applying, all detailed in `05`:

1. **Does `FinalData` carry all three sub-types?** The fix only combines what
   is already there; an upstream filter would defeat it.
2. **Integer division.** If `FinalEstimatedTime` / `FinalActualTime` are `int`,
   `SUM(est) / SUM(act)` truncates and the percentage can only be 0 or 100.
3. **`@Parm` vs `@StartDate1`.** `TimeSlot` is built from one, `StartDate`
   written from the other. If they ever differ, the key is wrong regardless of
   the `TaskType` fix.
4. **`TimeSlot` string equality.** `FORMAT(..., 'HH:00')` wraps hour 24 to
   `00:00`, giving `"23:00 - 00:00"`. If `Hourly_KPI` writes `"23:00 - 24:00"`,
   the 23:00 bucket stays unmatched — a second, independent mismatch.

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
