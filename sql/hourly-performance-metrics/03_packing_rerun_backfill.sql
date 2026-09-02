/*==============================================================================
  03 - Controlled re-run of the Packing hourly calculation

  Use AFTER the SP has been changed to combine the packing sub-types
  (see README - the root cause is a UniqueKey mismatch, not a missed run).
  Re-running the current, unfixed SP will just regenerate the same
  unmatchable keys.

  Date range: the 2-Sep catchup recorded both "from the 25th onward" (in the
  discussion) and "from the 26th onwards" (in the action item). The 25th is
  used below because that is the wider window and the SP's DELETE + INSERT
  makes re-running an already-correct day a no-op. Confirm with Aniket before
  running if that is not the intent.

  This script never writes performance values by hand. It takes a reversible
  snapshot, then lets dbo.spPerformance_Packing_Hourly01 regenerate the rows
  through its own business logic (the SP already does DELETE + INSERT per run,
  so re-running a date is idempotent).

  BEFORE RUNNING: confirm the SP's parameter names and types with script 02b
  and edit the EXEC line marked >>> EDIT <<< to match. Do not guess it.
==============================================================================*/

USE DCMetrics;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @FromDate date = '2026-08-25',
        @ToDate   date = '2026-09-02',   -- inclusive, last date to recalculate
        @Date     date,
        @Before   int,
        @After    int;

/*------------------------------------------------------------------
  3a. Reversible snapshot of the current Packing rows
------------------------------------------------------------------*/
IF OBJECT_ID('dbo.HourlyPerformanceMetrics_PackingBackup') IS NULL
BEGIN
    SELECT *
    INTO dbo.HourlyPerformanceMetrics_PackingBackup
    FROM dbo.HourlyPerformanceMetrics
    WHERE 1 = 0;

    ALTER TABLE dbo.HourlyPerformanceMetrics_PackingBackup
        ADD BackupTakenAt datetime2(0) NOT NULL DEFAULT SYSDATETIME();
END;

INSERT INTO dbo.HourlyPerformanceMetrics_PackingBackup
        (/* list columns explicitly if the table has an IDENTITY column */)
SELECT   /* matching column list */
FROM dbo.HourlyPerformanceMetrics
WHERE StartDateTime >= @FromDate
  AND StartDateTime <  DATEADD(DAY, 1, @ToDate)
  AND TaskType IN ('Packing', 'Manual Packing', 'ASRS Packing');
-- If HourlyPerformanceMetrics has no IDENTITY column, the two column lists
-- above can be replaced with a plain INSERT ... SELECT *.

/*------------------------------------------------------------------
  3b. Row counts before the re-run
------------------------------------------------------------------*/
SELECT
    'BEFORE' AS Phase,
    CAST(StartDateTime AS date) AS WorkDate,
    TaskType,
    COUNT(*) AS MetricRows
FROM dbo.HourlyPerformanceMetrics
WHERE StartDateTime >= @FromDate
  AND StartDateTime <  DATEADD(DAY, 1, @ToDate)
  AND TaskType IN ('Packing', 'Manual Packing', 'ASRS Packing')
GROUP BY CAST(StartDateTime AS date), TaskType
ORDER BY WorkDate, TaskType;

/*------------------------------------------------------------------
  3c. Re-run one date at a time, logging what each call produced
------------------------------------------------------------------*/
SET @Date = @FromDate;

WHILE @Date <= @ToDate
BEGIN
    SELECT @Before = COUNT(*)
    FROM dbo.HourlyPerformanceMetrics
    WHERE CAST(StartDateTime AS date) = @Date
      AND TaskType IN ('Packing', 'Manual Packing', 'ASRS Packing');

    BEGIN TRY
        -- >>> EDIT <<< match the real signature from script 02b, e.g.
        --   EXEC dbo.spPerformance_Packing_Hourly01 @StartDate = @Date, @EndDate = @Date;
        EXEC dbo.spPerformance_Packing_Hourly01 @Date;
    END TRY
    BEGIN CATCH
        RAISERROR('Packing recalc FAILED for %s : %s',
                  16, 1,
                  CONVERT(varchar(10), @Date, 23),
                  ERROR_MESSAGE()) WITH NOWAIT;
    END CATCH;

    SELECT @After = COUNT(*)
    FROM dbo.HourlyPerformanceMetrics
    WHERE CAST(StartDateTime AS date) = @Date
      AND TaskType IN ('Packing', 'Manual Packing', 'ASRS Packing');

    RAISERROR('%s : before=%d after=%d', 0, 1,
              CONVERT(varchar(10), @Date, 23), @Before, @After) WITH NOWAIT;

    SET @Date = DATEADD(DAY, 1, @Date);
END;

/*------------------------------------------------------------------
  3d. Row counts after - then re-run script 01b to confirm no MISSING METRIC
------------------------------------------------------------------*/
SELECT
    'AFTER' AS Phase,
    CAST(StartDateTime AS date) AS WorkDate,
    TaskType,
    COUNT(*) AS MetricRows
FROM dbo.HourlyPerformanceMetrics
WHERE StartDateTime >= @FromDate
  AND StartDateTime <  DATEADD(DAY, 1, @ToDate)
  AND TaskType IN ('Packing', 'Manual Packing', 'ASRS Packing')
GROUP BY CAST(StartDateTime AS date), TaskType
ORDER BY WorkDate, TaskType;

/*------------------------------------------------------------------
  3e. Rollback path, if the re-run produced worse data than it replaced
------------------------------------------------------------------*/
/*
BEGIN TRAN;

    DELETE FROM dbo.HourlyPerformanceMetrics
    WHERE StartDateTime >= '2026-08-27'
      AND StartDateTime <  '2026-09-03'
      AND TaskType IN ('Packing', 'Manual Packing', 'ASRS Packing');

    INSERT INTO dbo.HourlyPerformanceMetrics (/* columns */)
    SELECT /* columns */
    FROM dbo.HourlyPerformanceMetrics_PackingBackup
    WHERE StartDateTime >= '2026-08-27'
      AND StartDateTime <  '2026-09-03';

-- verify, then:
-- COMMIT TRAN;   /  ROLLBACK TRAN;
*/
