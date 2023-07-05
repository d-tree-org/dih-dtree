------------------------------------------------------------
-- Materialized view to show table of aggregation of district chv supervisors count.
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS agg_chvs_and_supervisors_count;
CREATE MATERIALIZED VIEW agg_chvs_and_supervisors_count AS
(
  WITH chvs AS (
    SELECT
      district,
      'sex' AS disaggregation,
      sex AS disaggregation_value,
      count(chv._id) AS chvs_all_time,
      sum((retired IS NULL)::INT) AS chvs_now
    FROM useview_chv AS chv
    INNER JOIN useview_jna_locations AS location
      ON chv.catchment_area_uuid = location.catchment_area_uuid
    GROUP BY district,disaggregation,disaggregation_value
  ),

  supervisors AS (
    SELECT
      district,
      'sex' AS disaggregation,
      sex AS disaggregation_value,
      count(sup._id) AS supervisor_all_time,
      sum((retired IS NULL)::INT) AS supervisor_now
    FROM useview_supervisor AS sup
    INNER JOIN useview_supervisory_area AS area
      ON sup.supervisory_area_uuid = area._id
    GROUP BY district,disaggregation,disaggregation_value
  )

  SELECT
    date_trunc('month',current_date) as reported_month,
    chvs.district,
    chvs.disaggregation,
    chvs.disaggregation_value,
    chvs_all_time,
    chvs_now,
    supervisor_all_time,
    supervisor_now
  FROM chvs
  LEFT JOIN supervisors
    ON chvs.district = supervisors.district
      AND chvs.disaggregation_value = supervisors.disaggregation_value

);

CREATE UNIQUE INDEX IF NOT EXISTS agg_chvs_and_supervisors_count  ON  agg_chvs_and_supervisors_count USING btree(district);
-- Permissions
ALTER MATERIALIZED VIEW agg_chvs_and_supervisors_count OWNER TO full_access;
GRANT SELECT ON agg_chvs_and_supervisors_count TO dtree, periscope;





