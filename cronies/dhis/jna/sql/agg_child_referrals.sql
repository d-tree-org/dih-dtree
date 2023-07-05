-------------------------------------------------------------
--- Materialized view to show table of aggregated referrals.
-------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS agg_child_referrals;
CREATE MATERIALIZED VIEW agg_child_referrals AS
(
  WITH combos AS (
    SELECT t.* FROM (VALUES
      ('child_age', 'sex'),
      ('default', 'default')
    ) AS t(cat_1, cat_2)
  ),

  category_options AS (
    SELECT co.* FROM (VALUES
      (0, 0, 'default', 'default'),
      (1, 1, 'male', 'sex'),
      (2, 2, 'female', 'sex'),
      (0, 5, '0_5months', 'child_age'),
      (6, 23, '6_23months', 'child_age'),
      (24, 59, '24_59months', 'child_age')
    )AS co(low, up, option, kind)
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

  referral_cte AS (
    SELECT
      catchment_area_uuid,
      original_source_form,
      original_source_form_uuid,
      max(reported_date) AS latest_followup_date,
      min(reported_date) AS first_followup_date,
      max(went_to_facility::INT) AS went_to_facility,
      max(got_services::INT) AS got_services,
      max(complete_referral::INT) AS followup_cancelled,
      max(CASE WHEN refer_flag_small_baby THEN went_to_facility::INT END) AS small_baby_went_to_facility,
      max(CASE WHEN refer_flag_small_baby THEN got_services::INT END) AS small_baby_got_services,
      max(CASE WHEN refer_flag_small_baby THEN complete_referral::INT END) AS small_baby_cancelled_followup,
      max(CASE WHEN refer_neonatal_danger_sign_flag THEN went_to_facility::INT END) AS neonatal_danger_sign_went_to_facility,
      max(CASE WHEN refer_neonatal_danger_sign_flag THEN got_services::INT END) AS neonatal_danger_sign_got_services,
      max(CASE WHEN refer_neonatal_danger_sign_flag THEN complete_referral::INT END) AS neonatal_danger_sign_cancelled_followup,
      max(CASE WHEN refer_secondary_neonatal_danger_sign_flag THEN went_to_facility::INT END) AS secondary_neonatal_danger_sign_went_to_facility,
      max(CASE WHEN refer_secondary_neonatal_danger_sign_flag THEN got_services::INT END) AS secondary_neonatal_danger_sign_got_services,
      max(CASE WHEN refer_secondary_neonatal_danger_sign_flag THEN complete_referral::INT END) AS secondary_neonatal_danger_sign_cancelled_followup,
      max(CASE WHEN refer_child_danger_sign_flag THEN got_services::INT END) AS child_danger_sign_got_services,
      max(CASE WHEN refer_child_danger_sign_flag THEN complete_referral::INT END) AS child_danger_sign_cancelled_followup,
      max(CASE WHEN refer_child_danger_sign_flag THEN went_to_facility::INT END) AS child_danger_sign_went_to_facility,
      max(CASE WHEN refer_child_other_danger_sign_flag THEN got_services::INT END) AS child_other_danger_sign_got_services,
      max(CASE WHEN refer_child_other_danger_sign_flag THEN complete_referral::INT END) AS child_other_danger_sign_cancelled_followup,
      max(CASE WHEN refer_child_other_danger_sign_flag THEN went_to_facility::INT END) AS child_other_danger_sign_went_to_facility,
      max(CASE WHEN refer_muac_flag THEN got_services::INT END) AS muac_got_services,
      max(CASE WHEN refer_muac_flag THEN complete_referral::INT END) AS muac_cancelled_followup,
      max(CASE WHEN refer_muac_flag THEN went_to_facility::INT END) AS muac_went_to_facility,
      max(CASE WHEN refer_palm_pallor_flag THEN got_services::INT END) AS palm_pallor_got_services,
      max(CASE WHEN refer_palm_pallor_flag THEN complete_referral::INT END) AS palm_pallor_cancelled_followup,
      max(CASE WHEN refer_palm_pallor_flag THEN went_to_facility::INT END) AS palm_pallor_went_to_facility,
      max(CASE WHEN refer_vaccines_flag THEN got_services::INT END) AS vaccines_got_services,
      max(CASE WHEN refer_vaccines_flag THEN complete_referral::INT END) AS vaccines_cancelled_followup,
      max(CASE WHEN refer_vaccines_flag THEN went_to_facility::INT END) AS vaccines_went_to_facility,
      max(CASE WHEN refer_slow_to_learn_specifics_flag THEN got_services::INT END) AS slow_to_learn_specifics_got_services,
      max(CASE WHEN refer_slow_to_learn_specifics_flag THEN complete_referral::INT END) AS slow_to_learn_specifics_cancelled_followup,
      max(CASE WHEN refer_slow_to_learn_specifics_flag THEN went_to_facility::INT END) AS slow_to_learn_specifics_went_to_facility
    FROM useview_referral_follow_up AS r
    WHERE original_source_form = 'infant_child'
    GROUP BY original_source_form,original_source_form_uuid,catchment_area_uuid
  )

  SELECT
    district,
    shehia,
    original_source_form,
    (combo.cat_1_kind || ',' || combo.cat_2_kind) AS disaggregation,
    (combo.cat_1_option || ',' || combo.cat_2_option) AS disaggregation_value,
    date_trunc('month',infant.reported_date) AS issued_month,
    sum(small_baby_went_to_facility) AS small_baby_went_to_facility,
    sum((small_baby_went_to_facility = 0)::INT) AS small_baby_didnt_go_facility,
    sum(small_baby_got_services) AS small_baby_got_services,
    sum(small_baby_cancelled_followup) AS small_baby_cancelled_followup,
    sum(neonatal_danger_sign_went_to_facility) AS neonatal_danger_sign_went_to_facility,
    sum((neonatal_danger_sign_went_to_facility = 0)::INT) AS neonatal_danger_sign_didnt_go_facility,
    sum(neonatal_danger_sign_got_services) AS neonatal_danger_sign_got_services,
    sum(neonatal_danger_sign_cancelled_followup) AS neonatal_danger_sign_cancelled_followup,
    sum(secondary_neonatal_danger_sign_went_to_facility) AS secondary_neonatal_danger_sign_went_to_facility,
    sum((secondary_neonatal_danger_sign_went_to_facility = 0)::INT) AS secondary_neonatal_danger_sign_didnt_go_facility,
    sum(secondary_neonatal_danger_sign_got_services) AS secondary_neonatal_danger_sign_got_services,
    sum(secondary_neonatal_danger_sign_cancelled_followup) AS secondary_neonatal_danger_sign_cancelled_followup,
    sum(child_danger_sign_got_services) AS child_danger_sign_got_services,
    sum(child_danger_sign_cancelled_followup) AS child_danger_sign_cancelled_followup,
    sum(child_danger_sign_went_to_facility) AS child_danger_sign_went_to_facility,
    sum((child_danger_sign_went_to_facility = 0)::INT) AS child_danger_sign_didnt_go_facility,
    sum(child_other_danger_sign_got_services) AS child_other_danger_sign_got_services,
    sum(child_other_danger_sign_cancelled_followup) AS child_other_danger_sign_cancelled_followup,
    sum(child_other_danger_sign_went_to_facility) AS child_other_danger_sign_went_to_facility,
    sum((child_other_danger_sign_went_to_facility = 0)::INT) AS child_other_danger_sign_didnt_go_facility,
    sum(muac_got_services) AS muac_got_services,
    sum(muac_cancelled_followup) AS muac_cancelled_followup,
    sum(muac_went_to_facility) AS muac_went_to_facility,
    sum((muac_went_to_facility = 0)::INT) AS muac_didnt_go_facility,
    sum(palm_pallor_got_services) AS palm_pallor_got_services,
    sum(palm_pallor_cancelled_followup) AS palm_pallor_cancelled_followup,
    sum(palm_pallor_went_to_facility) AS palm_pallor_went_to_facility,
    sum((palm_pallor_went_to_facility = 0)::INT) AS palm_pallor_didnt_go_facility,
    sum(vaccines_got_services) AS vaccines_got_services,
    sum(vaccines_cancelled_followup) AS vaccines_cancelled_followup,
    sum(vaccines_went_to_facility) AS vaccines_went_to_facility,
    sum((vaccines_went_to_facility = 0)::INT) AS vaccines_didnt_go_facility,
    sum(slow_to_learn_specifics_got_services) AS slow_to_learn_specifics_got_services,
    sum(slow_to_learn_specifics_cancelled_followup) AS slow_to_learn_specifics_cancelled_followup,
    sum(slow_to_learn_specifics_went_to_facility) AS slow_to_learn_specifics_went_to_facility,
    sum((slow_to_learn_specifics_went_to_facility = 0)::INT) AS slow_to_learn_specifics_didnt_go_facility,
    sum((infant.refer_neonatal_danger_sign_flag = 't')::INT) AS issued_referrals_neonatal_danger_sign,
    sum((infant.refer_secondary_neonatal_danger_sign_flag = 't')::INT) AS issued_referrals_secondary_neonatal_danger_sign,
    sum((infant.refer_child_danger_sign_flag = 't')::INT) AS issued_referrals_child_danger_sign,
    sum((infant.refer_child_other_danger_sign_flag = 't')::INT) AS issued_referrals_child_other_danger_sign,
    sum((infant.has_health_card = 'f' AND infant.age_years < 2 OR infant.vaccines_up_to_date = 'f')::INT) AS issued_referrals_child_missed_services,
    sum((infant.refer_muac_flag = 't')::INT) AS issued_referrals_muac,
    sum((infant.refer_palm_pallor_flag = 't')::INT) AS issued_referrals_palm_pallor,
    sum((infant.refer_slow_to_learn_specifics_flag = 't')::INT) AS issued_referrals_slow_to_learn_specifics,
    sum((
      date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 3
      AND infant.refer_neonatal_danger_sign_flag = 't'
    )::INT) AS followup_within3days_neonatal_danger_sign_flag,
    sum((
      date_part('day',infant.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 7
      AND infant.refer_neonatal_danger_sign_flag = 't'
    )::INT) AS followup_within7days_neonatal_danger_sign_flag,
    sum((
      infant.refer_secondary_neonatal_danger_sign_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 3
    )::INT) AS followup_within3days_secondary_neonatal_danger_sign,
    sum((
      infant.refer_secondary_neonatal_danger_sign_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 7
    )::INT) AS followup_within7days_secondary_neonatal_danger_sign,
    sum((
      infant.refer_child_danger_sign_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 3
    )::INT) AS followup_within3days_child_danger_sign,
    sum((
      infant.refer_child_danger_sign_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 7
    )::INT) AS followup_within7days_child_danger_sign,
    sum((
      infant.refer_child_other_danger_sign_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 3
    )::INT) AS followup_within3days_child_other_danger_sign,
    sum((
      infant.refer_child_other_danger_sign_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 7
    )::INT) AS followup_within7days_child_other_danger_sign,
    sum((
        (infant.has_health_card = 'f' AND infant.age_years <= 2 OR infant.vaccines_up_to_date = 'f')
        AND date_part('day',infant.reported_date - referral_cte.first_followup_date) < 3
    )::INT) AS followup_within3days_child_missed_services,
    sum((
        (infant.has_health_card = 'f' AND infant.age_years < 2 OR infant.vaccines_up_to_date = 'f')
        AND date_part('day',infant.reported_date - referral_cte.first_followup_date) > 3
        AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 7
    )::INT) AS followup_within7days_child_missed_services,
    sum((
      infant.refer_muac_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 3
    )::INT) AS followup_within3days_muac,
    sum((
      infant.refer_muac_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 7
    )::INT) AS followup_within7days_muac,
    sum((
      infant.refer_palm_pallor_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 3
    )::INT) AS followup_within3days_palm_pallor,
    sum((
      infant.refer_palm_pallor_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 7
    )::INT) AS followup_within7days_palm_pallor,
    sum((
      infant.refer_slow_to_learn_specifics_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 3
    )::INT) AS followup_within3days_slow_to_learn_specifics,
    sum((
      infant.refer_slow_to_learn_specifics_flag = 't'
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) > 3
      AND date_part('day',infant.reported_date - referral_cte.first_followup_date) <= 7
    )::INT) AS followup_within7days_slow_to_learn_specifics

  FROM useview_infant_child AS infant
  INNER JOIN useview_jna_locations AS loc
    ON loc.catchment_area_uuid = infant.catchment_area_uuid
  LEFT JOIN referral_cte
    ON infant._id = referral_cte.original_source_form_uuid
  LEFT JOIN category_options_combos AS combo
    ON infant.age_days::INT / 30 BETWEEN combo.cat_1_low AND combo.cat_1_up
      AND infant.child_sex = combo.cat_2_option
  WHERE
    --this filter is necessary as we have a few children above 5 yrs due to a bug on the app    
    cat_1_kind IS NOT NULL
  GROUP BY
    district,shehia,issued_month,original_source_form,disaggregation,disaggregation_value
);
CREATE UNIQUE INDEX IF NOT EXISTS district_month_shehia_agg_child_referrals ON agg_child_referrals USING btree(district,shehia,issued_month,original_source_form,disaggregation_value);
ALTER MATERIALIZED VIEW agg_child_referrals OWNER TO full_access;
GRANT SELECT ON agg_child_referrals TO dtree;
