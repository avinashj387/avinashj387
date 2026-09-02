/*==============================================================================
  05 - The fix: stop splitting #FinalResult by packing sub-type

  This is the final SELECT ... INTO #FinalResult inside
  dbo.spPerformance_Packing_Hourly01.

  THE BUG IS "GROUP BY hn.Hour, fd.TaskType".

  Grouping by TaskType emits one row per hour PER SUB-TYPE - a separate
  'Manual Packing' row and 'ASRS Packing' row for the same hour. The
  productivity side carries one combined packing bucket, so the UniqueKey
  built from these rows can never match and the join drops them.

  Note the inconsistency that makes the symptom look intermittent:
      ISNULL(fd.TaskType, 'Packing')
  An hour with NO packing data misses the LEFT JOIN, gets TaskType = NULL,
  and is relabelled 'Packing' - which DOES match. So empty hours join and
  busy hours don't. That is why the dashboard looks like data "stopped"
  rather than like a keying fault.
==============================================================================*/

/*------------------------------------------------------------------
  CURRENT (broken) - splits per sub-type
------------------------------------------------------------------*/
/*
SELECT
    ISNULL(fd.TaskType, 'Packing') AS TaskType,
    FORMAT(DATEADD(hour, hn.Hour, CAST(@Parm AS DATETIME)), 'HH:00') + ' - ' +
    FORMAT(DATEADD(hour, hn.Hour + 1, CAST(@Parm AS DATETIME)), 'HH:00') AS TimeSlot,
    ISNULL(SUM(fd.FinalEstimatedTime), 0) AS TotalEstimatedTime,
    ISNULL(SUM(fd.FinalActualTime), 0) AS TotalActualTime,
    CASE
        WHEN ISNULL(SUM(fd.FinalActualTime), 0) <= 0 THEN 0.00
        ELSE (ISNULL(SUM(fd.FinalEstimatedTime), 0) / SUM(fd.FinalActualTime)) * 100
    END AS PerformancePercentage,
    @StartDate1 AS StartDate
INTO #FinalResult
FROM HourNumbers hn
LEFT JOIN FinalData fd ON hn.Hour = fd.ActivityHour
GROUP BY hn.Hour, fd.TaskType          -- <== the fault
ORDER BY hn.Hour;
*/

/*------------------------------------------------------------------
  FIXED - one combined 'Packing' row per hour
------------------------------------------------------------------*/
SELECT
    'Packing' AS TaskType,
    FORMAT(DATEADD(hour, hn.Hour, CAST(@Parm AS DATETIME)), 'HH:00') + ' - ' +
    FORMAT(DATEADD(hour, hn.Hour + 1, CAST(@Parm AS DATETIME)), 'HH:00') AS TimeSlot,
    ISNULL(SUM(fd.FinalEstimatedTime), 0) AS TotalEstimatedTime,
    ISNULL(SUM(fd.FinalActualTime), 0) AS TotalActualTime,
    CASE
        WHEN ISNULL(SUM(fd.FinalActualTime), 0) <= 0 THEN 0.00
        ELSE (ISNULL(SUM(CAST(fd.FinalEstimatedTime AS decimal(18,4))), 0)
              / SUM(CAST(fd.FinalActualTime AS decimal(18,4)))) * 100
    END AS PerformancePercentage,
    @StartDate1 AS StartDate
INTO #FinalResult
FROM HourNumbers hn
LEFT JOIN FinalData fd ON hn.Hour = fd.ActivityHour
GROUP BY hn.Hour;

/*
  Two changes only:
    1. fd.TaskType removed from GROUP BY; the literal 'Packing' selected
       instead of ISNULL(fd.TaskType, 'Packing').
    2. The CAST to decimal - see "integer division" below. Harmless no-op if
       FinalEstimatedTime / FinalActualTime are already decimal or float.

  ORDER BY was dropped: it does nothing useful on SELECT ... INTO, since a
  heap has no guaranteed retrieval order. Keep it if house style prefers it -
  it is not the bug either way.

  The percentage math needs no other change and MUST NOT be "simplified" into
  an average. It already sums estimated and actual across the group and then
  divides, which is the correct way to combine the sub-types. Averaging the
  Manual and ASRS percentages gives a different, wrong number any time the two
  volumes differ.
==============================================================================*/


/*==============================================================================
  Before applying - four things to confirm
==============================================================================*/

/*--- 1. Does FinalData actually carry all three sub-types? -------------------
  This fix only combines what FinalData already contains. If the CTE or temp
  table that builds FinalData filters TaskType upstream, nothing here helps.
  Add this immediately before the SELECT above and run the SP for one date:
*/
-- SELECT TaskType, ActivityHour, COUNT(*) AS Rows_,
--        SUM(FinalEstimatedTime) AS Est, SUM(FinalActualTime) AS Act
-- FROM FinalData
-- GROUP BY TaskType, ActivityHour
-- ORDER BY ActivityHour, TaskType;

/*--- 2. Integer division ----------------------------------------------------
  If FinalEstimatedTime and FinalActualTime are int, then
  SUM(est) / SUM(act) truncates to 0 or 1 and PerformancePercentage can only
  ever be 0 or 100. Check the types:
*/
-- SELECT c.name, TYPE_NAME(c.user_type_id) AS DataType, c.precision, c.scale
-- FROM sys.columns c
-- WHERE c.object_id = OBJECT_ID('dbo.HourlyPerformanceMetrics');
--   (and check however FinalEstimatedTime / FinalActualTime are derived)

/*--- 3. @Parm vs @StartDate1 ------------------------------------------------
  TimeSlot is built from @Parm, StartDate is written from @StartDate1. If
  those two ever hold different dates, TimeSlot and StartDate describe
  different days and any UniqueKey built from the pair is wrong regardless of
  the TaskType fix. Confirm they are the same date, or make TimeSlot use
  @StartDate1 too.
*/

/*--- 4. TimeSlot string must match the productivity side exactly ------------
  FORMAT(..., 'HH:00') wraps hour 24 back to '00:00', so the last slot reads
  "23:00 - 00:00". If Hourly_KPI writes "23:00 - 24:00", the 23:00 bucket
  stays unmatched even after this fix - a second, separate mismatch.
*/
-- SELECT DISTINCT TimeSlot FROM dbo.Hourly_KPI
-- WHERE TaskType LIKE '%Pack%' ORDER BY TimeSlot;
-- SELECT DISTINCT TimeSlot FROM dbo.HourlyPerformanceMetrics
-- WHERE TaskType LIKE '%Pack%' ORDER BY TimeSlot;


/*==============================================================================
  After applying: script 03 to delete and re-run from 25-Aug, then script 04
  to confirm no unmatched keys remain.

  The SP's own DELETE already covers
      TaskType IN ('Manual Packing', 'Packing', 'ASRS Packing')
  so the old split rows are cleared for every date re-run. Split rows OUTSIDE
  the re-run window will survive - which is the argument for re-running the
  full 25-Aug-onward range rather than only the visibly broken days.
==============================================================================*/
