/*==============================================================================
  01 - Packing: is the gap in the SOURCE or in the CALCULATION?

  Question answered:
    For every date/hour that has Packing work in DCMImport, does a matching
    row exist in HourlyPerformanceMetrics?

  How to read the result:
    HasSource = 1, HasMetrics = 0  -> source is fine, the calculation/job did
                                      not produce the row  -> go to script 02
    HasSource = 0                  -> nothing to calculate for that hour, the
                                      "missing" metric row is expected
                                      -> problem is upstream of the SP (import)

  Adjust @FromDate / @ToDate as needed. @ToDate is exclusive.
==============================================================================*/

USE DCMetrics;
GO

SET NOCOUNT ON;

DECLARE @FromDate date = '2026-08-25',
        @ToDate   date = '2026-09-03';   -- exclusive

DECLARE @PackingTypes TABLE (TaskType varchar(100) PRIMARY KEY);
INSERT INTO @PackingTypes (TaskType)
VALUES ('Packing'), ('Manual Packing'), ('ASRS Packing');

/*------------------------------------------------------------------
  1a. Raw source volume per date / hour / task type
------------------------------------------------------------------*/
SELECT
    CAST(di.StartDateTime AS date)      AS WorkDate,
    DATEPART(HOUR, di.StartDateTime)    AS WorkHour,
    di.TaskType,
    COUNT(*)                            AS RecordCount,
    SUM(di.PickQuantity)                AS TotalUnits,
    COUNT(DISTINCT di.UserID)           AS DistinctUsers   -- drop if column differs
FROM dbo.DCMImport AS di
WHERE di.StartDateTime >= @FromDate
  AND di.StartDateTime <  @ToDate
  AND di.TaskType IN (SELECT TaskType FROM @PackingTypes)
GROUP BY
    CAST(di.StartDateTime AS date),
    DATEPART(HOUR, di.StartDateTime),
    di.TaskType
ORDER BY WorkDate, WorkHour, di.TaskType;

/*------------------------------------------------------------------
  1b. Side-by-side gap matrix: source hour vs calculated metric row
      This is the query that actually pinpoints the failure.
------------------------------------------------------------------*/
WITH src AS
(
    SELECT
        CAST(di.StartDateTime AS date)   AS WorkDate,
        DATEPART(HOUR, di.StartDateTime) AS WorkHour,
        di.TaskType,
        COUNT(*)                         AS SourceRows,
        SUM(di.PickQuantity)             AS SourceUnits
    FROM dbo.DCMImport AS di
    WHERE di.StartDateTime >= @FromDate
      AND di.StartDateTime <  @ToDate
      AND di.TaskType IN (SELECT TaskType FROM @PackingTypes)
    GROUP BY
        CAST(di.StartDateTime AS date),
        DATEPART(HOUR, di.StartDateTime),
        di.TaskType
),
mtr AS
(
    SELECT
        CAST(hpm.StartDateTime AS date)   AS WorkDate,
        DATEPART(HOUR, hpm.StartDateTime) AS WorkHour,
        hpm.TaskType,
        COUNT(*)                          AS MetricRows
    FROM dbo.HourlyPerformanceMetrics AS hpm
    WHERE hpm.StartDateTime >= @FromDate
      AND hpm.StartDateTime <  @ToDate
      AND hpm.TaskType IN (SELECT TaskType FROM @PackingTypes)
    GROUP BY
        CAST(hpm.StartDateTime AS date),
        DATEPART(HOUR, hpm.StartDateTime),
        hpm.TaskType
)
SELECT
    COALESCE(src.WorkDate, mtr.WorkDate) AS WorkDate,
    COALESCE(src.WorkHour, mtr.WorkHour) AS WorkHour,
    COALESCE(src.TaskType, mtr.TaskType) AS TaskType,
    ISNULL(src.SourceRows, 0)            AS SourceRows,
    ISNULL(src.SourceUnits, 0)           AS SourceUnits,
    ISNULL(mtr.MetricRows, 0)            AS MetricRows,
    CASE
        WHEN src.WorkDate IS NOT NULL AND mtr.WorkDate IS NULL
            THEN 'MISSING METRIC - source exists, calculation did not run/produce'
        WHEN src.WorkDate IS NULL AND mtr.WorkDate IS NOT NULL
            THEN 'ORPHAN METRIC - metric exists with no source'
        ELSE 'OK'
    END                                  AS Diagnosis
FROM src
FULL OUTER JOIN mtr
    ON  mtr.WorkDate = src.WorkDate
    AND mtr.WorkHour = src.WorkHour
    AND mtr.TaskType = src.TaskType
ORDER BY WorkDate, WorkHour, TaskType;

/*------------------------------------------------------------------
  1c. Per-day roll-up - the fastest way to see where 27-Aug breaks
------------------------------------------------------------------*/
SELECT
    d.WorkDate,
    SUM(d.SourceRows)  AS SourceRows,
    SUM(d.MetricRows)  AS MetricRows,
    SUM(CASE WHEN d.SourceRows > 0 AND d.MetricRows = 0 THEN 1 ELSE 0 END)
                       AS MissingHourBuckets
FROM
(
    SELECT
        CAST(di.StartDateTime AS date)   AS WorkDate,
        DATEPART(HOUR, di.StartDateTime) AS WorkHour,
        di.TaskType,
        COUNT(*)                         AS SourceRows,
        0                                AS MetricRows
    FROM dbo.DCMImport AS di
    WHERE di.StartDateTime >= @FromDate
      AND di.StartDateTime <  @ToDate
      AND di.TaskType IN (SELECT TaskType FROM @PackingTypes)
    GROUP BY CAST(di.StartDateTime AS date),
             DATEPART(HOUR, di.StartDateTime), di.TaskType

    UNION ALL

    SELECT
        CAST(hpm.StartDateTime AS date),
        DATEPART(HOUR, hpm.StartDateTime),
        hpm.TaskType,
        0,
        COUNT(*)
    FROM dbo.HourlyPerformanceMetrics AS hpm
    WHERE hpm.StartDateTime >= @FromDate
      AND hpm.StartDateTime <  @ToDate
      AND hpm.TaskType IN (SELECT TaskType FROM @PackingTypes)
    GROUP BY CAST(hpm.StartDateTime AS date),
             DATEPART(HOUR, hpm.StartDateTime), hpm.TaskType
) AS d
GROUP BY d.WorkDate
ORDER BY d.WorkDate;
