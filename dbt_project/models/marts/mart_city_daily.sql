/*
    Mart: Daily Weather by City
    Joins weather facts with city and date dimensions
    to produce a fully denormalized daily weather table.
*/

with weather as (
    select * from {{ ref('stg_weather') }}
),

cities as (
    select * from {{ ref('stg_cities') }}
),

dates as (
    select * from {{ ref('stg_dates') }}
),

daily as (
    select
        -- City info
        c.city_name,
        c.state,
        c.climate_zone,
        c.latitude,
        c.longitude,
        c.elevation_m,

        -- Date info
        d.date,
        d.year,
        d.month,
        d.month_name,
        d.quarter,
        d.season,
        d.day_of_week,
        d.is_weekend,

        -- Weather metrics
        w.temp_avg,
        w.temp_min,
        w.temp_max,
        w.temp_range,
        w.humidity_avg,
        w.precip_total,
        w.wind_speed_avg,
        w.wind_speed_max,
        w.pressure_avg,
        w.cloud_cover_avg,
        w.heat_index,
        w.is_extreme_heat,
        w.is_freezing,
        w.precip_category

    from weather w
    inner join cities c on w.city_id = c.city_id
    inner join dates d on w.date_id = d.date_id
)

select * from daily
