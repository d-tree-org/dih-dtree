SELECT
    cols.column_name,
    cols.data_type,
    tc.constraint_type AS key,
    CASE
        WHEN tc.constraint_type = 'FOREIGN KEY'
            THEN (
                SELECT kcu2.table_name || '.' || kcu2.column_name
                FROM
                    information_schema.referential_constraints AS rc
                INNER JOIN information_schema.key_column_usage AS kcu2
                    ON rc.unique_constraint_name = kcu2.constraint_name
                WHERE
                    rc.constraint_name = kcu.constraint_name
                LIMIT 1
            )
    END AS foreign_key_reference
FROM
    information_schema.columns AS cols
LEFT JOIN
    information_schema.key_column_usage AS kcu
    ON
        cols.table_name = kcu.table_name
        AND cols.column_name = kcu.column_name
        AND cols.table_schema = kcu.table_schema
LEFT JOIN
    information_schema.table_constraints AS tc
    ON
        kcu.table_schema = tc.table_schema
        AND kcu.table_name = tc.table_name
        AND kcu.constraint_name = tc.constraint_name
WHERE
    cols.table_name = :table
    AND cols.table_schema = :schema
ORDER BY
    cols.ordinal_position;
