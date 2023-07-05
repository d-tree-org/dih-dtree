DROP MATERIALIZED VIEW IF EXISTS agg_neonatal_referrals;
CREATE MATERIALIZED VIEW agg_neonatal_referrals AS
(
    SELECT
        issued_month,
        district,
        shehia,
        'sex' AS disaggregation,
        CASE WHEN strpos(disaggregation_values,'female') > 0 then 'female' ELSE 'male' END AS disaggregation_value,
        sum(small_baby_went_to_facility) AS small_baby_went_to_facility,
        sum(small_baby_got_services) AS small_baby_got_services,
        sum(small_baby_cancelled_followup) AS small_baby_cancelled_followup,
        sum(small_baby_didnt_go_facility) AS small_baby_didnt_go_facility,
        sum(small_baby_got_services) AS small_baby_got_services,
        sum(small_baby_cancelled_followup) AS small_baby_cancelled_followup,
        sum(neonatal_danger_sign_went_to_facility) AS neonatal_danger_sign_went_to_facility,
        sum(neonatal_danger_sign_got_services) AS neonatal_danger_sign_got_services,
        sum(neonatal_danger_sign_cancelled_followup) AS neonatal_danger_sign_cancelled_followup,
        sum(secondary_neonatal_danger_sign_went_to_facility) AS secondary_neonatal_danger_sign_went_to_facility,
        sum(secondary_neonatal_danger_sign_got_services) AS secondary_neonatal_danger_sign_got_services,
        sum(secondary_neonatal_danger_sign_cancelled_followup) AS secondary_neonatal_danger_sign_cancelled_followup,
        sum(neonatal_danger_sign_went_to_facility) AS neonatal_danger_sign_went_to_facility,
        sum(neonatal_danger_sign_didnt_go_facility) AS neonatal_danger_sign_didnt_go_facility,
        sum(neonatal_danger_sign_got_services) AS neonatal_danger_sign_got_services,
        sum(neonatal_danger_sign_cancelled_followup) AS neonatal_danger_sign_cancelled_followup,
        sum(secondary_neonatal_danger_sign_went_to_facility) AS secondary_neonatal_danger_sign_went_to_facility,
        sum(secondary_neonatal_danger_sign_didnt_go_facility) AS secondary_neonatal_danger_sign_didnt_go_facility,
        sum(secondary_neonatal_danger_sign_got_services) AS secondary_neonatal_danger_sign_got_services,
        sum(secondary_neonatal_danger_sign_cancelled_followup) AS secondary_neonatal_danger_sign_cancelled_followup,
        sum(issued_referrals_neonatal_danger_sign) AS issued_referrals_neonatal_danger_sign,
        sum(issued_referrals_secondary_neonatal_danger_sign) AS issued_referrals_secondary_neonatal_danger_sign,
        sum(followup_within3days_neonatal_danger_sign_flag) AS followup_within3days_neonatal_danger_sign_flag,
        sum(followup_within7days_neonatal_danger_sign_flag) AS followup_within7days_neonatal_danger_sign_flag,
        sum(followup_within3days_secondary_neonatal_danger_sign) AS followup_within3days_secondary_neonatal_danger_sign,
        sum(followup_within7days_secondary_neonatal_danger_sign) AS followup_within7days_secondary_neonatal_danger_sign
    FROM agg_child_referrals
    GROUP BY issued_month,district,shehia,4,5
);
CREATE UNIQUE INDEX IF NOT EXISTS district_month_shehia_agg_neonatal_referrals ON agg_neonatal_referrals USING btree(district,shehia,issued_month,disaggregation_values);
ALTER MATERIALIZED VIEW agg_neonatal_referrals OWNER TO full_access;
GRANT SELECT ON agg_neonatal_referrals TO dtree;