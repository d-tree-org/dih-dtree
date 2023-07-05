------------------------------------------------------------
-- Materialized view to show table of aggregation of pregnancy outcome forms.
------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS agg_outcome_pregnancy;
CREATE MATERIALIZED VIEW agg_outcome_pregnancy AS
(
  WITH other_visits_cte AS (
    SELECT
      po.patient_id,
      po._id AS po_uuid,
      max(pg.reported_date) AS last_pregnancy_visit_date,
      min(pp.reported_date) AS first_postpartum_visit_date
    FROM useview_pregnancy_outcomes AS po
    INNER JOIN useview_pregnancy AS pg
      ON pg.patient_id = po.patient_id
        AND pg.reported_date < po.reported_date
    LEFT JOIN useview_postpartum AS pp
      ON pp.patient_id = po.patient_id
        AND pp.reported_date > po.reported_date
    GROUP BY po.patient_id, po_uuid
  ),

  categories AS (
    SELECT cat.* FROM (VALUES
      (15, 19, '15_19years', 'woman'),
      (20, 24, '20_24years', 'woman'),
      (25, 34, '25_34years', 'woman'),
      (35, 49, '35_49years', 'woman'),
      (50, 200, '50+years', 'woman'))
      AS cat(low, up, category, kind)
  ),

  agg_client_records AS (
    SELECT
      district,
      shehia,
      categories.category AS disaggregation_value,
      date_trunc('month',enrollment_end_date) AS end_month,
      count(cer.*) AS end_of_pregnancy
    FROM client_enrollment_record AS cer
    INNER JOIN useview_pregnancy AS pg
      ON pg.patient_id = cer.patient_id
        AND pg.reported_date = cer.enrollment_start_date
    INNER JOIN useview_jna_locations AS loc
      ON pg.catchment_area_uuid = loc.catchment_area_uuid
    INNER JOIN categories
      ON pg.age_years BETWEEN categories.low AND categories.up
    WHERE service = 'pregnancy'
    GROUP BY district,shehia,end_month,disaggregation_value
  ),

  outcomes AS (
    SELECT
      loc.district,
      loc.shehia,
      'marternal_age' AS disaggregation,
      categories.category AS disaggregation_value,
      date_trunc('month', po.reported_date) AS reported_month,
      sum(coalesce(po.live_birth::INT, 0)) AS live_births,
      sum(coalesce((po.live_birth AND po.delivery_location='home')::INT, 0)) AS live_births_home,
      sum(coalesce((po.live_birth AND po.delivery_location='facility')::INT, 0)) AS live_births_facility,
      sum(coalesce((po.live_birth AND po.delivery_location='other')::INT, 0)) AS live_births_other,
      sum(coalesce((po.miscarriage_or_stillbirth = 'stillbirth')::INT, 0)) AS stillbirths,
      sum(coalesce((po.miscarriage_or_stillbirth = 'stillbirth' and po.delivery_location = 'home')::INT, 0)) AS stillbirths_home,
      sum(coalesce((po.miscarriage_or_stillbirth = 'stillbirth' and po.delivery_location = 'facility')::INT, 0)) AS stillbirths_facility,
      sum(coalesce((po.miscarriage_or_stillbirth = 'stillbirth' and po.delivery_location = 'other')::INT, 0)) AS stillbirths_other,
      sum(coalesce((po.miscarriage_or_stillbirth = 'miscarriage')::INT, 0)) AS miscarriages,
      sum(coalesce((po.delivery_location = 'facility')::INT, 0)) AS woman_delivery_facility,
      sum(coalesce((po.delivery_location = 'home')::INT, 0)) AS woman_delivery_home,
      sum(coalesce((po.delivery_location = 'in_transit')::INT, 0)) AS woman_delivery_in_transit,
      sum((po.delivery_location = 'home')::INT * coalesce(po.num_live_births,po.live_birth::INT)) AS infants_born_home_alive,
      sum((po.delivery_location = 'home')::INT * coalesce(po.num_babies_delivered,1)) AS all_infants_born_home,
      sum((po.delivery_location IS NOT NULL)::INT * coalesce(po.num_live_births,po.live_birth::INT)) AS all_infants_born_alive,
      sum((po.delivery_location IS NOT NULL)::INT * coalesce(po.num_babies_delivered,1)) AS all_infants_born,
      sum(coalesce((pg.num_anc_visits = 0)::INT, 0)) AS anc_0,
      sum(coalesce((pg.num_anc_visits = 1)::INT, 0)) AS anc_1,
      sum(coalesce((pg.num_anc_visits = 2)::INT, 0)) AS anc_2,
      sum(coalesce((pg.num_anc_visits = 3)::INT, 0)) AS anc_3,
      sum(coalesce((pg.num_anc_visits >= 4)::INT, 0)) AS anc_4,
      sum(coalesce(pp.has_attended_facility_pnc_within_48hrs::INT, 0)) AS pp_care_2_days

    FROM useview_pregnancy_outcomes AS po
    INNER JOIN useview_jna_locations AS loc
      ON po.catchment_area_uuid = loc.catchment_area_uuid
    INNER JOIN other_visits_cte AS ov
      ON ov.po_uuid = po._id
    INNER JOIN useview_pregnancy AS pg
      ON pg.patient_id = ov.patient_id
        AND pg.reported_date = ov.last_pregnancy_visit_date
    INNER JOIN categories
      ON po.age_years BETWEEN categories.low AND categories.up
    LEFT JOIN useview_postpartum AS pp
      ON pp.patient_id = ov.patient_id
        AND pp.reported_date = ov.first_postpartum_visit_date
    GROUP BY reported_month, loc.shehia, loc.district, disaggregation_value
  )

  SELECT
    coalesce(outcomes.district,ce_records.district) AS district,
    coalesce(outcomes.shehia,ce_records.shehia) AS shehia,
    coalesce(outcomes.reported_month,ce_records.end_month) AS reported_month,
    'marternal_age' AS disaggregation,
    coalesce(outcomes.disaggregation_value,ce_records.disaggregation_value) AS disaggregation_value,
    outcomes.live_births,
    outcomes.live_births_home,
    outcomes.live_births_facility,
    outcomes.live_births_other,
    outcomes.stillbirths,
    outcomes.stillbirths_home,
    outcomes.stillbirths_facility,
    outcomes.stillbirths_other,
    outcomes.miscarriages,
    outcomes.woman_delivery_facility,
    outcomes.woman_delivery_home,
    outcomes.woman_delivery_in_transit,
    outcomes.infants_born_home_alive,
    outcomes.all_infants_born_home,
    outcomes.all_infants_born_alive,
    outcomes.all_infants_born,
    outcomes.anc_0,
    outcomes.anc_1,
    outcomes.anc_2,
    outcomes.anc_3,
    outcomes.anc_4,
    outcomes.pp_care_2_days,
    ce_records.end_of_pregnancy
  FROM outcomes
  FULL OUTER JOIN agg_client_records AS ce_records
    ON ce_records.end_month = outcomes.reported_month
      AND ce_records.shehia = outcomes.shehia
      AND ce_records.district = outcomes.district
      AND ce_records.disaggregation_value = outcomes.disaggregation_value
  WHERE end_month <= current_date

);

CREATE UNIQUE INDEX IF NOT EXISTS agg_outcome_pregnancy_month_shehia ON agg_outcome_pregnancy USING btree(
  reported_month, shehia, district, disaggregation_value
);
-- Permissions
ALTER MATERIALIZED VIEW agg_outcome_pregnancy OWNER TO full_access;
GRANT SELECT ON agg_outcome_pregnancy TO dtree, periscope;
