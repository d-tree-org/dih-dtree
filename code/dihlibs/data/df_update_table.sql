WITH temp AS (
    SELECT * FROM ( VALUES
     {values}
    ) AS t({columns})
)
UPDATE {tablename} AS u_table
SET 
    {set_columns}
FROM temp
WHERE u_table.{id_column}=temp.{id_column} ;
WITH temp AS (
    SELECT * FROM ( VALUES
     {values}
    ) AS t({columns})
)
INSERT INTO {tablename} ({columns})
SELECT {update_columns} 
FROM temp
LEFT JOIN {tablename} AS u_table ON u_table.{id_column} = temp.{id_column}
WHERE u_table.{id_column} IS NULL
{on_conflict};