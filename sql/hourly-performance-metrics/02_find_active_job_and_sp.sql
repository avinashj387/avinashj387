/*==============================================================================
  02 - Which SP and which SQL Agent job actually own Packing?

  Answers, in order:
    2a. Which procedures touch Packing / HourlyPerformanceMetrics at all
        (there may be more than one, and an old one may still be scheduled)
    2b. The parameter signature of the Packing SP (needed before any re-run)
    2c. Which Agent job step calls it, and whether that job is enabled
    2d. The job's schedule
    2e. Job run history around the 27-Aug break, with failure messages
    2f. Whether the job/SP is executing right now
    2g. How far back msdb history actually goes (if it was purged, 2e proves
        nothing - say so rather than concluding "the job never ran")
==============================================================================*/

USE DCMetrics;
GO

SET NOCOUNT ON;

/*------------------------------------------------------------------
  2a. Every procedure that mentions Packing or the metrics table
------------------------------------------------------------------*/
SELECT
    SCHEMA_NAME(o.schema_id)                                        AS SchemaName,
    o.name                                                          AS ProcedureName,
    o.create_date,
    o.modify_date,
    CASE WHEN m.definition LIKE '%HourlyPerformanceMetrics%'
         THEN 1 ELSE 0 END                                          AS WritesOrReadsMetrics,
    CASE WHEN m.definition LIKE '%ASRS Packing%'   THEN 1 ELSE 0 END AS HandlesASRSPacking,
    CASE WHEN m.definition LIKE '%Manual Packing%' THEN 1 ELSE 0 END AS HandlesManualPacking,
    LEN(m.definition)                                               AS DefinitionLength
FROM sys.objects AS o
JOIN sys.sql_modules AS m
    ON m.object_id = o.object_id
WHERE o.type = 'P'
  AND (m.definition LIKE '%Packing%'
       OR m.definition LIKE '%HourlyPerformanceMetrics%')
ORDER BY o.modify_date DESC, o.name;
-- NOTE: o.modify_date is the tell. If a Packing SP was ALTERed on or just
--       before 27-Aug, that change is the prime suspect.

/*------------------------------------------------------------------
  2b. Parameter signature of the Packing SP
      Do not guess the parameters when re-running (script 04).
------------------------------------------------------------------*/
SELECT
    p.parameter_id,
    p.name                          AS ParameterName,
    TYPE_NAME(p.user_type_id)       AS DataType,
    p.max_length,
    p.is_output,
    p.has_default_value,
    p.default_value
FROM sys.parameters AS p
WHERE p.object_id = OBJECT_ID('dbo.spPerformance_Packing_Hourly01')
ORDER BY p.parameter_id;

-- Full text of the SP, if you want to re-read the DELETE/INSERT boundary:
-- EXEC sp_helptext 'dbo.spPerformance_Packing_Hourly01';

/*------------------------------------------------------------------
  2c. Agent job steps that call it - the "active job"
------------------------------------------------------------------*/
SELECT
    j.name                          AS JobName,
    j.enabled                       AS JobEnabled,
    js.enabled                      AS TargetServerEnabled,
    s.step_id,
    s.step_name,
    s.database_name,
    s.command,
    s.last_run_outcome,             -- 0 = failed, 1 = succeeded, 3 = cancelled
    s.last_run_date,
    s.last_run_time,
    s.last_run_duration
FROM msdb.dbo.sysjobs        AS j
JOIN msdb.dbo.sysjobsteps    AS s  ON s.job_id = j.job_id
LEFT JOIN msdb.dbo.sysjobservers AS js ON js.job_id = j.job_id
WHERE s.command LIKE '%spPerformance_Packing_Hourly01%'
   OR s.command LIKE '%HourlyPerformanceMetrics%'
   OR s.command LIKE '%Packing%'
ORDER BY j.name, s.step_id;
-- If JobEnabled = 0, that alone explains the gap.
-- If two different jobs call two different Packing SPs, note which one is
-- enabled: an enabled old job can be silently overwriting the new results.

/*------------------------------------------------------------------
  2d. Schedule attached to those jobs
------------------------------------------------------------------*/
SELECT
    j.name                  AS JobName,
    j.enabled               AS JobEnabled,
    sch.name                AS ScheduleName,
    sch.enabled             AS ScheduleEnabled,
    sch.freq_type,          -- 4 = daily, 8 = weekly
    sch.freq_interval,
    sch.freq_subday_type,   -- 1 = at the specified time, 4 = minutes, 8 = hours
    sch.freq_subday_interval,
    sch.active_start_time,
    sch.active_end_time,
    sch.date_created,
    sch.date_modified
FROM msdb.dbo.sysjobs           AS j
JOIN msdb.dbo.sysjobsteps       AS s   ON s.job_id  = j.job_id
JOIN msdb.dbo.sysjobschedules   AS jsc ON jsc.job_id = j.job_id
JOIN msdb.dbo.sysschedules      AS sch ON sch.schedule_id = jsc.schedule_id
WHERE s.command LIKE '%Packing%'
GROUP BY j.name, j.enabled, sch.name, sch.enabled, sch.freq_type,
         sch.freq_interval, sch.freq_subday_type, sch.freq_subday_interval,
         sch.active_start_time, sch.active_end_time,
         sch.date_created, sch.date_modified;
-- sch.date_modified near 27-Aug = someone changed the schedule.

/*------------------------------------------------------------------
  2e. Run history around the break (25-Aug onward)
------------------------------------------------------------------*/
SELECT
    j.name                                              AS JobName,
    h.step_id,
    h.step_name,
    msdb.dbo.agent_datetime(h.run_date, h.run_time)      AS RunDateTime,
    h.run_status,        -- 0 failed, 1 succeeded, 2 retry, 3 cancelled, 4 in progress
    h.run_duration,      -- HHMMSS as an integer
    h.retries_attempted,
    h.message
FROM msdb.dbo.sysjobhistory AS h
JOIN msdb.dbo.sysjobs       AS j ON j.job_id = h.job_id
WHERE EXISTS
      (
          SELECT 1
          FROM msdb.dbo.sysjobsteps AS s
          WHERE s.job_id = j.job_id
            AND s.command LIKE '%Packing%'
      )
  AND msdb.dbo.agent_datetime(h.run_date, h.run_time) >= '2026-08-25'
ORDER BY RunDateTime DESC;
-- Read it as: did the job stop firing on 27-Aug (no rows), start failing
-- (run_status = 0 with a message), or keep succeeding (run_status = 1)?
-- Succeeding + missing rows = the SP produced an empty #FinalResult, which
-- points at the SP's own filters/joins, not at the Agent.

/*------------------------------------------------------------------
  2f. Is it running right now?
------------------------------------------------------------------*/
SELECT
    r.session_id,
    r.status,
    r.start_time,
    r.command,
    DB_NAME(r.database_id)  AS DatabaseName,
    r.blocking_session_id,
    r.wait_type,
    r.wait_time,
    t.text                  AS SQLText
FROM sys.dm_exec_requests AS r
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) AS t
WHERE t.text LIKE '%Packing%'
   OR t.text LIKE '%HourlyPerformanceMetrics%';

-- Jobs currently executing (survives the case where the SP is blocked, not running):
SELECT
    j.name                      AS JobName,
    a.start_execution_date,
    a.last_executed_step_id,
    a.stop_execution_date
FROM msdb.dbo.sysjobactivity AS a
JOIN msdb.dbo.sysjobs        AS j ON j.job_id = a.job_id
WHERE a.start_execution_date IS NOT NULL
  AND a.stop_execution_date  IS NULL
ORDER BY a.start_execution_date DESC;

/*------------------------------------------------------------------
  2g. How far back does msdb history go?
      If the oldest entry is after 27-Aug, history was purged and 2e cannot
      prove the job did or did not run.
------------------------------------------------------------------*/
SELECT
    MIN(msdb.dbo.agent_datetime(run_date, run_time)) AS OldestHistoryEntry,
    MAX(msdb.dbo.agent_datetime(run_date, run_time)) AS NewestHistoryEntry,
    COUNT(*)                                         AS HistoryRows
FROM msdb.dbo.sysjobhistory;
