-------------------------------------------------------------
--- Materialized view to show table of aggregated referrals.
-------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS agg_pregnancy_referrals;
CREATE MATERIALIZED VIEW agg_pregnancy_referrals AS
(
  WITH category_option_combos AS (
    SELECT co.* FROM (VALUES
      (15, 19, '15_19years', 'maternal_age'),
      (20, 24, '20_24years', 'maternal_age'),
      (25, 34, '25_34years', 'maternal_age'),
      (35, 49, '35_49years', 'maternal_age'),
      (50, 200, '50+years', 'maternal_age')
    )AS co(low, up, disaggregation_value, disaggregation)
  ),

  referral_cte AS (
    SELECT
      catchment_area_uuid,
      original_source_form,
      original_source_form_uuid,
      (max(went_to_facility::INT) = 0)::INT AS didnt_go_facility,
      max(reported_date) AS latest_followup_date,
      min(reported_date) AS first_followup_date,
      sum(went_to_facility::INT) AS went_to_facility,
      sum(got_services::INT) AS got_services,
      sum(complete_referral::INT) AS followup_cancelled,
      max(CASE WHEN refer_flag_pregnancy_danger_sign THEN got_services::INT END) AS pregnancy_danger_signs_got_services,
      max(CASE WHEN refer_flag_pregnancy_danger_sign THEN complete_referral::INT END) AS pregnancy_danger_signs_cancelled_followup,
      max(CASE WHEN refer_flag_pregnancy_danger_sign THEN went_to_facility::INT END) AS pregnancy_danger_signs_went_to_facility,
      max(CASE WHEN refer_flag_pregnancy_issues THEN got_services::INT END) AS pregnancy_issues_got_services,
      max(CASE WHEN refer_flag_pregnancy_issues THEN complete_referral::INT END) AS pregnancy_issues_cancelled_followup,
      max(CASE WHEN refer_flag_pregnancy_issues THEN went_to_facility::INT END) AS pregnancy_issues_went_to_facility,
      max(CASE WHEN refer_flag_pregnancy_complications THEN got_services::INT END) AS pregnancy_complications_got_services,
      max(CASE WHEN refer_flag_pregnancy_complications THEN complete_referral::INT END) AS pregnancy_complications_cancelled_followup,
      max(CASE WHEN refer_flag_pregnancy_complications THEN went_to_facility::INT END) AS pregnancy_complications_went_to_facility,
      max(CASE WHEN refer_flag_postpartum_danger_signs THEN got_services::INT END) AS postpartum_danger_signs_got_services,
      max(CASE WHEN refer_flag_postpartum_danger_signs THEN complete_referral::INT END) AS postpartum_danger_signs_cancelled_followup,
      max(CASE WHEN refer_flag_postpartum_danger_signs THEN went_to_facility::INT END) AS postpartum_danger_signs_went_to_facility,
      max(CASE WHEN refer_flag_postpartum_other_signs THEN got_services::INT END) AS postpartum_other_signs_got_services,
      max(CASE WHEN refer_flag_postpartum_other_signs THEN complete_referral::INT END) AS postpartum_other_signs_cancelled_followup,
      max(CASE WHEN refer_flag_postpartum_other_signs THEN went_to_facility::INT END) AS postpartum_other_signs_went_to_facility,
      max(CASE WHEN refer_flag_postpartum_pnc_visit THEN got_services::INT END) AS postpartum_pnc_visit_got_services,
      max(CASE WHEN refer_flag_postpartum_pnc_visit THEN complete_referral::INT END) AS postpartum_pnc_visit_cancelled_followup,
      max(CASE WHEN refer_flag_postpartum_pnc_visit THEN went_to_facility::INT END) AS postpartum_pnc_visit_went_to_facility,
      max(CASE WHEN refer_flag_anc_visit THEN got_services::INT END) AS anc_visit_got_services,
      max(CASE WHEN refer_flag_anc_visit THEN complete_referral::INT END) AS anc_visit_cancelled_followup,
      max(CASE WHEN refer_flag_anc_visit THEN went_to_facility::INT END) AS anc_visit_went_to_facility
    FROM useview_referral_follow_up AS r
    WHERE original_source_form IN ('pregnancy','postpartum')
    GROUP BY original_source_form,original_source_form_uuid,catchment_area_uuid
  )

  SELECT
    district,
    shehia,
    original_source_form,
    combo.disaggregation,
    combo.disaggregation_value,
    date_trunc('month',coalesce(pg.reported_date,ppt.reported_date)) AS issued_month,
    sum(pregnancy_danger_signs_cancelled_followup) AS pregnancy_danger_signs_cancelled_followup,
    sum(pregnancy_danger_signs_got_services) AS pregnancy_danger_signs_got_services,
    sum(pregnancy_danger_signs_went_to_facility) AS pregnancy_danger_signs_went_to_facility,
    sum((pregnancy_danger_signs_went_to_facility = 0)::INT) AS pregnancy_danger_signs_didnt_go_facility,
    sum(pregnancy_issues_went_to_facility) AS pregnancy_issues_went_to_facility,
    sum((pregnancy_issues_went_to_facility = 0)::INT) AS pregnancy_issues_didnt_go_facility,
    sum(pregnancy_issues_got_services) AS pregnancy_issues_got_services,
    sum(pregnancy_issues_cancelled_followup) AS pregnancy_issues_cancelled_followup,
    sum(pregnancy_complications_went_to_facility) AS pregnancy_complications_went_to_facility,
    sum((pregnancy_complications_went_to_facility = 0)::INT) AS pregnancy_complications_didnt_go_facility,
    sum(pregnancy_complications_got_services) AS pregnancy_complications_got_services,
    sum(postpartum_danger_signs_got_services) AS postpartum_danger_signs_got_services,
    sum(postpartum_danger_signs_cancelled_followup) AS postpartum_danger_signs_cancelled_followup,
    sum(postpartum_danger_signs_went_to_facility) AS postpartum_danger_signs_went_to_facility,
    sum((postpartum_danger_signs_went_to_facility = 0)::INT) AS postpartum_danger_signs_didnt_go_facility,
    sum(postpartum_other_signs_got_services) AS postpartum_other_signs_got_services,
    sum(postpartum_other_signs_cancelled_followup) AS postpartum_other_signs_cancelled_followup,
    sum(postpartum_other_signs_went_to_facility) AS postpartum_other_signs_went_to_facility,
    sum((postpartum_other_signs_went_to_facility = 0)::INT) AS postpartum_other_signs_didnt_go_facility,
    sum(postpartum_pnc_visit_got_services) AS postpartum_pnc_visit_got_services,
    sum(postpartum_pnc_visit_cancelled_followup) AS postpartum_pnc_visit_cancelled_followup,
    sum(postpartum_pnc_visit_went_to_facility) AS postpartum_pnc_visit_went_to_facility,
    sum((postpartum_pnc_visit_went_to_facility = 0)::INT) AS postpartum_pnc_visit_didnt_go_facility,
    sum(anc_visit_got_services) AS anc_visit_got_services,
    sum(anc_visit_cancelled_followup) AS anc_visit_cancelled_followup,
    sum(anc_visit_went_to_facility) AS anc_visit_went_to_facility,
    sum((anc_visit_went_to_facility = 0)::INT) AS anc_visit_didnt_go_facility,
    sum((pg.refer_flag_emergency_danger_sign = 't')::int) AS issued_referrals_pregnancy_danger_sign,
    sum((pg.refer_flag_pregnancy_issues = 't')::int) AS issued_referrals_pregnancy_issues,
    sum((pg.refer_flag_pregnancy_complications = 't')::int) AS issued_referrals_pregnancy_complications,
    sum((pg.refer_flag_anc_visit = 't')::int) AS issued_referrals_anc_visit,
    sum((ppt.refer_postpartum_emergency_danger_sign_flag = 't')::INT) AS issued_refer_postpartum_emergency_danger_sign_flag,
    sum((ppt.refer_postpartum_other_danger_sign_flag = 't')::INT) AS issued_refer_postpartum_other_danger_sign_flag,
    sum((ppt.refer_postpartum_pnc_visit = 't')::INT) AS issued_refer_postpartum_pnc_visit,
    sum((
      pg.refer_flag_emergency_danger_sign = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 3
    )::int) followup_within3days_missed_anc,
    sum((
      pg.refer_flag_emergency_danger_sign = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 7
    )::int) followup_within7days_missed_anc,
    sum((
      pg.refer_flag_emergency_danger_sign = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 3
    )::int) followup_within3days_pregnancy_danger_sign,
    sum((
      pg.refer_flag_emergency_danger_sign = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 7
    )::int) followup_within7days_pregnancy_danger_sign,
    sum((
      refer_flag_pregnancy_issues = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 3
    )::int) followup_within3days_pregnancy_issues,
    sum((
      refer_flag_pregnancy_issues = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 7
    )::int) followup_within7days_pregnancy_issues,
    sum((
      refer_flag_pregnancy_complications = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 3
    )::int) followup_within3days_pregnancy_complications,
    sum((
      refer_flag_pregnancy_complications = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 7
    )::int) followup_within7days_pregnancy_complications,
    sum((
      refer_postpartum_emergency_danger_sign_flag = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 3
    )::INT) AS followup_within3days_postpartum_emergency_danger_sign_flag,
    sum((
      refer_postpartum_emergency_danger_sign_flag = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 7
    )::INT) AS followup_within7days_postpartum_emergency_danger_sign_flag,
    sum((
      refer_postpartum_other_danger_sign_flag = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 3
    )::INT) AS followup_within3days_postpartum_other_danger_sign_flag,
    sum((
      refer_postpartum_other_danger_sign_flag = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 7
    )::INT) AS followup_within7days_postpartum_other_danger_sign_flag,
    sum((
      refer_postpartum_pnc_visit = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 3
    )::INT) AS followup_within3days_postpartum_pnc_visit,
    sum((
      refer_postpartum_pnc_visit = 't'
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',pg.reported_date - referral_cte.first_followup_date) <= 7
    )::INT) AS followup_within7days_postpartum_pnc_visit
  FROM referral_cte
  FULL OUTER JOIN useview_pregnancy AS pg
    ON pg._id = referral_cte.original_source_form_uuid
  FULL OUTER JOIN useview_postpartum AS ppt
    ON ppt._id = referral_cte.original_source_form_uuid
  INNER JOIN category_option_combos AS combo
    ON(
      (pg.age_years BETWEEN combo.low AND combo.up)
      OR (ppt.age_years BETWEEN combo.low AND combo.up)
    )
  INNER JOIN useview_jna_locations AS loc
    ON loc.catchment_area_uuid = referral_cte.catchment_area_uuid
      OR loc.catchment_area_uuid = pg.catchment_area_uuid
      OR loc.catchment_area_uuid = ppt.catchment_area_uuid
  GROUP BY
    district,shehia,issued_month,original_source_form,disaggregation,disaggregation_value
);
CREATE UNIQUE INDEX IF NOT EXISTS district_month_shehia_agg_pregnancy_referrals ON agg_pregnancy_referrals USING btree(district,shehia,issued_month,original_source_form,disaggregation_value);
ALTER MATERIALIZED VIEW agg_pregnancy_referrals OWNER TO full_access;
GRANT SELECT ON agg_pregnancy_referrals TO dtree;
