/*
    Staging: City Dimension
    Clean city reference data from the SQLite warehouse.
*/

with source as (
    select * from {{ source('raw', 'dim_city') }}
),

cleaned as (
    select
        city_id,
        city_key,
        city_name,
        state,
        round(cast(latitude as double), 4)  as latitude,
        round(cast(longitude as double), 4) as longitude,
        round(cast(elevation as double), 0) as elevation_m,
        climate_zone
    from source
)

select * from cleaned
