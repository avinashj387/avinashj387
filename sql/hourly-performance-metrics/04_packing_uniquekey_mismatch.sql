/*==============================================================================
  04 - Packing: the UniqueKey mismatch (CONFIRMED ROOT CAUSE)

  From the Win Dev catchup on 2-Sep-2026:
    "packing benchmarks were missing because manual packing and ASRS packing
     data were not being combined correctly ... the join between the
     productivity table and the performance table was failing because the
     unique keys did not match."

  So the rows are not necessarily absent from HourlyPerformanceMetrics. They
  are keyed per packing sub-type ('Manual Packing' / 'ASRS Packing') while the
  productivity side carries a single combined 'Packing' bucket, so the join
  drops them and the benchmark renders blank.

  Run 4a first - it tells you which of the two shapes you are in.

  Column names on the productivity side are not assumed: 4z lists them so you
  can adjust the joins below to match the real schema.
==============================================================================*/

USE DCMetrics;
GO

SET NOCOUNT ON;

DECLARE @FromDate date = '2026-08-25',
        @ToDate   date = '2026-09-03';   -- exclusive

/*------------------------------------------------------------------
  4z. Confirm the column names on both sides before trusting 4b/4c
------------------------------------------------------------------*/
SELECT TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME IN ('Hourly_KPI', 'HourlyPerformanceMetrics')
ORDER BY TABLE_NAME, ORDINAL_POSITION;

/*------------------------------------------------------------------
  4a. Which packing TaskType values exist on each side?
      This is the whole bug in one result set.
------------------------------------------------------------------*/
SELECT 'Hourly_KPI' AS Side, TaskType, COUNT(*) AS Rows_
FROM dbo.Hourly_KPI
WHERE StartDateTime >= @FromDate
  AND StartDateTime <  @ToDate
  AND TaskType LIKE '%Pack%'
GROUP BY TaskType

UNION ALL

SELECT 'HourlyPerformanceMetrics', TaskType, COUNT(*)
FROM dbo.HourlyPerformanceMetrics
WHERE StartDateTime >= @FromDate
  AND StartDateTime <  @ToDate
  AND TaskType LIKE '%Pack%'
GROUP BY TaskType
ORDER BY Side, TaskType;
-- Expected symptom: KPI side shows a single combined bucket while the metrics
-- side shows 'Manual Packing' and 'ASRS Packing' separately (or vice versa).
-- Whichever side splits is the side the SP has to combine.

/*------------------------------------------------------------------
  4b. Sample UniqueKey values from both sides, same hour
      Shows exactly where the two key strings diverge.
------------------------------------------------------------------*/
SELECT TOP (100)
    'Hourly_KPI' AS Side, StartDateTime, TaskType, UniqueKey
FROM dbo.Hourly_KPI
WHERE StartDateTime >= @FromDate
  AND StartDateTime <  @ToDate
  AND TaskType LIKE '%Pack%'
ORDER BY StartDateTime, TaskType;

SELECT TOP (100)
    'HourlyPerformanceMetrics' AS Side, StartDateTime, TaskType, UniqueKey
FROM dbo.HourlyPerformanceMetrics
WHERE StartDateTime >= @FromDate
  AND StartDateTime <  @ToDate
  AND TaskType LIKE '%Pack%'
ORDER BY StartDateTime, TaskType;
-- If the TaskType is embedded in UniqueKey, the split sub-types can never
-- match the combined bucket. That is the join failure.

/*------------------------------------------------------------------
  4c. Unmatched keys, both directions
      Every row here is a benchmark that renders blank on the dashboard.
------------------------------------------------------------------*/
SELECT
    k.StartDateTime,
    k.TaskType      AS KPI_TaskType,
    k.UniqueKey     AS KPI_UniqueKey,
    'KPI row with no performance match' AS Issue
FROM dbo.Hourly_KPI AS k
WHERE k.StartDateTime >= @FromDate
  AND k.StartDateTime <  @ToDate
  AND k.TaskType LIKE '%Pack%'
  AND NOT EXISTS
      (
          SELECT 1
          FROM dbo.HourlyPerformanceMetrics AS h
          WHERE h.UniqueKey = k.UniqueKey
      )

UNION ALL

SELECT
    h.StartDateTime,
    h.TaskType,
    h.UniqueKey,
    'Performance row with no KPI match'
FROM dbo.HourlyPerformanceMetrics AS h
WHERE h.StartDateTime >= @FromDate
  AND h.StartDateTime <  @ToDate
  AND h.TaskType LIKE '%Pack%'
  AND NOT EXISTS
      (
          SELECT 1
          FROM dbo.Hourly_KPI AS k
          WHERE k.UniqueKey = h.UniqueKey
      )
ORDER BY StartDateTime, KPI_TaskType;
-- Both directions populated on the same hour = the classic split-vs-combined
-- mismatch, not missing data.

/*------------------------------------------------------------------
  4d. What the combined packing row should look like
      Aggregates the packing sub-types the way the SP needs to, so you can
      sanity-check the totals before changing the SP.
------------------------------------------------------------------*/
SELECT
    CAST(di.StartDateTime AS date)      AS WorkDate,
    DATEPART(HOUR, di.StartDateTime)    AS WorkHour,
    'Packing'                           AS CombinedTaskType,
    COUNT(*)                            AS RecordCount,
    SUM(di.PickQuantity)                AS TotalUnits,
    SUM(CASE WHEN di.TaskType = 'Manual Packing' THEN di.PickQuantity ELSE 0 END) AS ManualPackingUnits,
    SUM(CASE WHEN di.TaskType = 'ASRS Packing'   THEN di.PickQuantity ELSE 0 END) AS ASRSPackingUnits,
    SUM(CASE WHEN di.TaskType = 'Packing'        THEN di.PickQuantity ELSE 0 END) AS PackingUnits
FROM dbo.DCMImport AS di
WHERE di.StartDateTime >= @FromDate
  AND di.StartDateTime <  @ToDate
  AND di.TaskType IN ('Packing', 'Manual Packing', 'ASRS Packing')
GROUP BY
    CAST(di.StartDateTime AS date),
    DATEPART(HOUR, di.StartDateTime)
ORDER BY WorkDate, WorkHour;
-- Caution on the SP change: combining the sub-types means EstimatedTime and
-- ActualTime must be summed across them BEFORE PerformancePercentage is
-- derived. Averaging the two sub-type percentages gives a different, wrong
-- number whenever the volumes differ.
