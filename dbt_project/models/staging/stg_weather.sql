/*
    Staging: Weather Facts
    Clean and type-cast the raw fact_weather table from the SQLite warehouse.
    Source data is loaded by the Python ETL pipeline.
*/

with source as (
    select * from {{ source('raw', 'fact_weather') }}
),

cleaned as (
    select
        city_id,
        date_id,

        -- Temperature metrics
        round(cast(temp_avg as double), 2)       as temp_avg,
        round(cast(temp_min as double), 2)       as temp_min,
        round(cast(temp_max as double), 2)       as temp_max,
        round(cast(temp_max as double) - cast(temp_min as double), 2) as temp_range,

        -- Moisture
        round(cast(humidity_avg as double), 1)    as humidity_avg,
        round(cast(precip_total as double), 2)    as precip_total,

        -- Wind
        round(cast(wind_speed_avg as double), 2)  as wind_speed_avg,
        round(cast(wind_speed_max as double), 2)  as wind_speed_max,

        -- Atmosphere
        round(cast(pressure_avg as double), 1)    as pressure_avg,
        round(cast(cloud_cover_avg as double), 1) as cloud_cover_avg,

        -- Derived
        round(cast(heat_index as double), 2)      as heat_index,
        cast(is_extreme_heat as boolean)          as is_extreme_heat,
        cast(is_freezing as boolean)              as is_freezing,
        precip_category

    from source
    where city_id is not null
      and date_id is not null
)

select * from cleaned
