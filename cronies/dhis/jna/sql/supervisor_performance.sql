------------------------------------------------------------
-- Materialized view to show table of supervisor performance.
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS supervisor_performance;

CREATE MATERIALIZED VIEW supervisor_performance AS
(
  WITH skeleton AS (
    SELECT
      district,
      sarea.name as facility,
      supervisor._id,
      supervisory_area_uuid,
      reported_month::DATE
    FROM generate_series(
      TIMESTAMP '2019-07-01',
      current_date,
      interval '1 month') AS t(reported_month)
    INNER JOIN useview_supervisor AS supervisor ON reported_month >= supervisor.reported_date
      AND supervisor.retired IS NULL
    INNER JOIN useview_supervisory_area sarea
    ON supervisor.supervisory_area_uuid=sarea._id
    ORDER BY _id,reported_month
  ),

  chv_performance_CTE AS (
    SELECT
      supervisory_area_uuid,
      reported_month,
      coalesce(round(sum(total_enrollments)::DECIMAL / count(chv_uuid),1),0) AS average_enrollments_per_chv,
      coalesce(round(sum(total_visits)::DECIMAL / count(chv_uuid),1),0) AS average_visits_per_chv
    FROM chv_performance
    GROUP BY supervisory_area_uuid,reported_month
  ),

  group_session_CTE AS (
    SELECT
      supervisory_area_uuid,
      count(_id) AS num_group_sessions,
      date_trunc('month',reported_date)::date AS reported_month
    FROM useview_group_session
    GROUP BY supervisory_area_uuid, reported_month
  ),

  old_daily_meetings_CTE AS (
    SELECT
      supervisory_area_uuid,
      date_trunc('day',reported_date) AS day_reported,
      sum((confirm_meeting IN('my_supervisor_is','my_supervisor_is_attending'))::INT) AS num_individual_chv_meetings,
      max((confirm_meeting = 'iam_attending')::INT) AS chv_meetings
    FROM useview_confirm_meeting
    GROUP BY supervisory_area_uuid,day_reported
  ),

  old_monthly_meetings_CTE AS (
    SELECT
      supervisory_area_uuid,
      date_trunc('month',day_reported) AS reported_month,
      sum(num_individual_chv_meetings) AS chv_field_visits,
      sum(chv_meetings) AS monthly_meetings
    FROM old_daily_meetings_CTE
    GROUP BY supervisory_area_uuid,reported_month
  ),

  monthly_meeting_CTE AS (
    SELECT
      supervisory_area_uuid,
      count(_id) AS monthly_meetings,
      date_trunc('month',reported_date)::date AS reported_month
    FROM useview_monthly_meeting
    GROUP BY supervisory_area_uuid, reported_month
  ),

  quality_monitoring_CTE AS (
    SELECT
      supervisory_area_uuid,
      count(_id) AS chv_field_visits,
      date_trunc('month',reported_date)::date AS reported_month
    FROM useview_chv_quality_monitoring
    GROUP BY supervisory_area_uuid, reported_month
  )

  SELECT
    skeleton.district,
    skeleton.facility,
    skeleton._id AS supervisor_uuid,
    skeleton.supervisory_area_uuid,
    skeleton.reported_month,
    coalesce(gs.num_group_sessions,0) AS num_group_sessions,
    coalesce(meeting.monthly_meetings,old_meeting.monthly_meetings,0) AS monthly_meetings,
    coalesce(qm.chv_field_visits,old_meeting.chv_field_visits,0) AS chv_field_visits,
    coalesce(cp.average_enrollments_per_chv,0) AS average_enrollments_per_chv,
    coalesce(cp.average_visits_per_chv,0) AS average_visits_per_chv
  FROM skeleton
  LEFT JOIN chv_performance_CTE AS cp
    ON skeleton.supervisory_area_uuid = cp.supervisory_area_uuid
      AND skeleton.reported_month = cp.reported_month
  LEFT JOIN group_session_CTE AS gs
    ON skeleton.supervisory_area_uuid = gs.supervisory_area_uuid
      AND skeleton.reported_month = gs.reported_month
  LEFT JOIN old_monthly_meetings_CTE AS old_meeting
    ON skeleton.supervisory_area_uuid = old_meeting.supervisory_area_uuid
      AND skeleton.reported_month = old_meeting.reported_month
  LEFT JOIN monthly_meeting_CTE AS meeting
    ON skeleton.supervisory_area_uuid = meeting.supervisory_area_uuid
      AND skeleton.reported_month = meeting.reported_month
  LEFT JOIN quality_monitoring_CTE AS qm
    ON skeleton.supervisory_area_uuid = qm.supervisory_area_uuid
      AND skeleton.reported_month = qm.reported_month
);

CREATE UNIQUE INDEX IF NOT EXISTS supervisor_uuid_month ON supervisor_performance USING btree(supervisor_uuid,reported_month);
ALTER MATERIALIZED VIEW supervisor_performance OWNER TO full_access;
GRANT SELECT ON supervisor_performance TO dtree;
