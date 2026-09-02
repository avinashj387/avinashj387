# Packing hourly performance metrics — missing rows from 27-Aug

Scope: **Packing only** (`Packing`, `Manual Packing`, `ASRS Packing`).
The Manual Picking / ASRS Picking findings are recorded at the bottom as open
items, not worked here.

## Symptom

| Layer | 25–26 Aug | 27 Aug onward |
|---|---|---|
| `Hourly_KPI` | present | present |
| `HourlyPerformanceMetrics` | present | missing hours |

`Hourly_KPI` is **not** to be modified. `HourlyPerformanceMetrics` is **not**
to be hand-populated — `EstimatedTime`, `ActualTime` and
`PerformancePercentage` must come out of
`dbo.spPerformance_Packing_Hourly01`, which already handles all three packing
task types and does its own `DELETE` + `INSERT` per run.

## Run order

| Script | Answers |
|---|---|
| `01_packing_source_vs_metrics.sql` | Is the gap in DCMImport or in the calculation? |
| `02_find_active_job_and_sp.sql` | Which SP and which Agent job own Packing, is the job enabled, did it run? |
| `03_packing_rerun_backfill.sql` | Reversible re-run of the SP for the affected dates |

Script 01 query **1b** is the one that decides everything — it full-joins the
source hours against the metric hours and labels each bucket.

## Decision tree

```
01b Diagnosis column
│
├─ HasSource = 0 for the missing hours
│     -> nothing to calculate; the break is upstream of the SP.
│        Investigate the DCMImport feed for 27-Aug, not the performance SP.
│
└─ HasSource > 0, MetricRows = 0   ("MISSING METRIC")
      -> source is fine, run 02.
      │
      ├─ 2c: JobEnabled = 0
      │     -> job was disabled. Re-enable, then backfill with 03.
      │
      ├─ 2e: no history rows on/after 27-Aug
      │     -> job stopped firing. Check 2g first: if msdb history was
      │        purged, this proves nothing. Check 2d date_modified for a
      │        schedule change. Then backfill with 03.
      │
      ├─ 2e: run_status = 0 (failed), read h.message
      │     -> real error. Fix the cause first; a backfill will just fail
      │        the same way.
      │
      └─ 2e: run_status = 1 (succeeded) every day, rows still missing
            -> the job ran and the SP produced an empty #FinalResult.
               This is an SP-logic problem, not a scheduling one. Prime
               suspects, in order:
                 1. 2a o.modify_date — was a Packing SP ALTERed around
                    27-Aug? That change is the cause until proven otherwise.
                 2. The SP's date parameter / default window — if it only
                    processes "yesterday" and the job start time moved, a
                    day falls between two runs.
                 3. A join in the SP that drops rows: a standards/UPH
                    lookup, a shift or roster table, or an employee mapping
                    with no row for the new period. An inner join to a
                    standards table with no 27-Aug-onward entry produces
                    exactly this symptom — source present, output empty,
                    job green.
                 4. A new value appearing in a filtered column from 27-Aug
                    (a fourth packing TaskType, a new zone/site code).
```

To test suspect 3 or 4 without changing anything, run the SP's own source
`SELECT` (the part that populates its working temp table) for 26-Aug and for
28-Aug and compare row counts — the join that drops to zero is the culprit.

## Rules for this fix

- Do not `UPDATE`/`INSERT` `HourlyPerformanceMetrics` by hand.
- Do not change `Hourly_KPI.TaskType`.
- Take the snapshot in 03a before any re-run; 03e is the rollback.
- Confirm the SP's parameter signature (02b) before editing the `EXEC` in 03c.

## Open items (not Packing, deliberately not addressed here)

- **Manual Picking** — KPI rows exist, metric rows missing. Needs a
  `Manual Picking` vs `Manual Picking - Direct` naming check before anything
  else; may be a mapping issue rather than a calculation one.
- **ASRS Picking** — `spPerformance_Picking_Hourly_Detailed_Calculation`
  filters `di.TaskType = 'Manual Picking'` only, so ASRS Picking is never
  calculated. Search for another SP; if none exists, the picking calculation
  has to be extended, which is a change to business logic and needs sign-off.
