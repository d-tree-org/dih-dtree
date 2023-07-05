------------------------------------------------------------
-- Materialized view to show table of aggregated chv activities.
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS agg_chv_activities;

CREATE MATERIALIZED VIEW agg_chv_activities AS
(
  WITH combos AS (
    SELECT t.* FROM (VALUES
      ('maternal_age', 'trimester'),
      ('child_age', 'sex'),
      ('default', 'default')
    ) AS t(cat_1, cat_2)
  ),

  category_options AS (
    SELECT co.* FROM ( VALUES
      (0, 0, 'default', 'default'),
      (1, 1, 'male', 'sex'),
      (2, 2, 'female', 'sex'),
      (1, 1, '1st_trimester', 'trimester'),
      (2, 2, '2nd_trimester', 'trimester'),
      (3, 20, '3rd_trimester', 'trimester'),
      (0, 5, '0_5months', 'child_age'),
      (6, 23, '6_23months', 'child_age'),
      (24, 59, '24_59months', 'child_age'),
      (15, 19, '15_19years', 'maternal_age'),
      (20, 24, '20_24years', 'maternal_age'),
      (25, 34, '25_34years', 'maternal_age'),
      (35, 49, '35_49years', 'maternal_age'),
      (50, 200, '50+years', 'maternal_age'))
      AS co(low, up, option, kind)
  ),

  category_options_combos AS (
    SELECT
      option_1.up AS cat_1_up,
      option_2.up AS cat_2_up,
      option_1.low AS cat_1_low,
      option_2.low AS cat_2_low,
      option_1.kind AS cat_1_kind,
      option_2.kind AS cat_2_kind,
      option_1.option AS cat_1_option,
      option_2.option AS cat_2_option
    FROM combos
    INNER JOIN category_options AS option_1
      ON option_1.kind = combos.cat_1
    INNER JOIN category_options AS option_2
      ON option_2.kind = combos.cat_2
  ),

  skeleton AS (
    SELECT DISTINCT
      ccombos.*,
      t.reported_month::DATE AS reported_month,
      loc.district,
      loc.shehia,
      loc.catchment_area_uuid
    FROM generate_series( TIMESTAMP '2019-07-01', current_date, INTERVAL '1 month') AS t(reported_month)
    INNER JOIN useview_jna_locations AS loc ON TRUE
    INNER JOIN category_options_combos AS ccombos ON TRUE
    ORDER BY loc.district, loc.shehia, reported_month
  ),

  houses AS (
    SELECT
      catchment_area_uuid,
      date_trunc('month', reported_date) AS reported_month,
      count(_id) AS houses
    FROM useview_household
    GROUP BY reported_month, catchment_area_uuid
  ),

  people AS (
    SELECT
      catchment_area_uuid,
      date_trunc('month', reported_date) AS reported_month,
      count(_id) AS people
    FROM useview_person
    GROUP BY reported_month, catchment_area_uuid
  ),

  infants AS (
    SELECT
      infant.catchment_area_uuid,
      cat.option AS child_age,
      infant.child_sex AS sex,
      date_trunc('month', infant.reported_date) AS reported_month,
      sum((infant.child_consent_today = 't')::INT) AS enrolled,
      sum((infant.child_consent_today = 't' OR infant.child_consent_today IS NULL)::INT) AS visits
    FROM useview_infant_child AS infant
    INNER JOIN category_options AS cat
      ON cat.kind = 'child_age'
        AND infant.age_days::INT / 30 BETWEEN cat.low AND cat.up
    GROUP BY reported_month, infant.catchment_area_uuid, child_age, sex
  ),

  pregnancy AS (
    SELECT
      pregnancy.catchment_area_uuid,
      cat.option AS marternal_age,
      date_trunc('month', pregnancy.reported_date) AS reported_month,
      sum((pregnancy.consent = 't')::INT) AS enrolled,
      sum((pregnancy.consent = 't' OR pregnancy.consent IS NULL)::INT) AS visits,
      coalesce(((40 * 7 - date_part('day', pregnancy.edd - pregnancy.reported_date)) / 90)::INT + 1,
        CASE
          WHEN pregnancy.visit_id = 'pregnancy_month_5_month_7_visit' THEN 2
          WHEN pregnancy.visit_id = 'pregnancy_over_7_months_visit' THEN 3
        END) AS trimester
    FROM useview_pregnancy AS pregnancy
    INNER JOIN category_options AS cat
      ON cat.kind = 'maternal_age'
        AND pregnancy.age_years BETWEEN cat.low AND cat.up
    GROUP BY reported_month, pregnancy.catchment_area_uuid, trimester, marternal_age

  ),

  group_counselling AS (
    SELECT
      catchment_area_uuid,
      date_trunc('month', reported_date) AS reported_month,
      count(_id) AS sessions
    FROM useview_group_counseling
    GROUP BY reported_month, catchment_area_uuid
  ),

  data AS (
    SELECT
      sk.reported_month AS reported_month,
      sk.district,
      sk.shehia,
      sk.cat_1_kind || ',' || sk.cat_2_kind AS disaggregation,
      sk.cat_1_option || ',' || sk.cat_2_option AS disaggregation_value,
      sum(h.houses) AS registrations_households,
      sum(p.people) AS registrations_people,
      sum(i.enrolled) AS enrollments_child,
      sum(pg.enrolled) AS enrollments_pregnancy,
      sum(i.visits) AS visits_child,
      sum(pg.visits) AS visits_pregnancy,
      sum(gc.sessions) AS group_counselling_sessions
    FROM skeleton AS sk
    LEFT JOIN houses AS h
      ON h.catchment_area_uuid = sk.catchment_area_uuid
        AND sk.reported_month = h.reported_month
        AND sk.cat_1_kind = 'default' AND sk.cat_2_kind = 'default'
    LEFT JOIN people AS p
      ON p.catchment_area_uuid = sk.catchment_area_uuid
        AND p.reported_month = sk.reported_month
        AND sk.cat_1_kind = 'default' AND sk.cat_2_kind = 'default'
    LEFT JOIN group_counselling AS gc
      ON gc.catchment_area_uuid = sk.catchment_area_uuid
        AND gc.reported_month = sk.reported_month
        AND sk.cat_1_kind = 'default' AND sk.cat_2_kind = 'default'
    LEFT JOIN infants AS i
      ON i.catchment_area_uuid = sk.catchment_area_uuid
        AND i.reported_month = sk.reported_month
        AND i.child_age = sk.cat_1_option
        AND i.sex = sk.cat_2_option
    -- AND sk.cat_1_kind='child_age' AND sk.cat_2_kind='sex'  --No need to have this?
    LEFT JOIN pregnancy AS pg
      ON pg.catchment_area_uuid = sk.catchment_area_uuid
        AND pg.reported_month = sk.reported_month
        AND pg.trimester BETWEEN sk.cat_2_low AND sk.cat_2_up
        AND pg.marternal_age = sk.cat_1_option
    -- AND sk.cat_1_kind='maternal_age' AND sk.cat_2_kind='trimester'  --No need to have this?
    GROUP BY sk.shehia, sk.district, sk.reported_month, disaggregation, disaggregation_value
  )

  SELECT *
  FROM data
  WHERE coalesce(registrations_households,
                 registrations_people,
                 enrollments_child, visits_child,
                 visits_pregnancy, group_counselling_sessions) IS NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS district_month_shehia ON agg_chv_activities USING btree(
  reported_month, district, shehia, disaggregation_value
);
ALTER MATERIALIZED VIEW agg_chv_activities OWNER TO full_access;
GRANT SELECT ON agg_chv_activities TO periscope, dtree;
