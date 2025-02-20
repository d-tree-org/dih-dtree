WITH temp AS (
    SELECT * FROM ( VALUES
     {values}
    ) AS t({columns})
)
UPDATE {tablename} AS u_table
SET 
    {set_columns}
FROM temp
WHERE {id_condition};

WITH temp AS (
    SELECT * FROM ( VALUES
     {values}
    ) AS t({columns})
)
INSERT INTO {tablename} ({columns})
SELECT {update_columns} 
FROM temp
LEFT JOIN {tablename} AS u_table ON {id_condition}
WHERE {where_clause}
{on_conflict};
