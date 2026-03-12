/*
    Mart: City Climate Summary
    Overall climate profile per city across the entire date range.
    Used by the dashboard Map page and Overview cards.
*/

with daily as (
    select * from {{ ref('mart_city_daily') }}
),

summary as (
    select
        city_name,
        state,
        climate_zone,
        latitude,
        longitude,
        elevation_m,

        -- Date range
        min(date) as first_date,
        max(date) as last_date,
        count(*)  as total_days,

        -- Temperature
        round(avg(temp_avg), 2) as avg_temp,
        round(min(temp_min), 2) as record_low,
        round(max(temp_max), 2) as record_high,
        round(avg(temp_range), 2) as avg_daily_range,

        -- Moisture
        round(avg(humidity_avg), 1)  as avg_humidity,
        round(sum(precip_total), 1)  as total_precip,
        round(avg(precip_total), 2)  as avg_daily_precip,

        -- Wind
        round(avg(wind_speed_avg), 2) as avg_wind_speed,
        round(max(wind_speed_max), 2) as max_wind_gust,

        -- Atmosphere
        round(avg(pressure_avg), 1)    as avg_pressure,
        round(avg(cloud_cover_avg), 1) as avg_cloud_cover,

        -- Extreme weather counts
        sum(case when is_extreme_heat then 1 else 0 end) as extreme_heat_days,
        sum(case when is_freezing then 1 else 0 end)     as freezing_days,
        sum(case when precip_total > 0 then 1 else 0 end) as rainy_days,
        sum(case when precip_total > 10 then 1 else 0 end) as heavy_rain_days,

        -- Percentages
        round(100.0 * sum(case when is_freezing then 1 else 0 end) / count(*), 1) as pct_freezing,
        round(100.0 * sum(case when precip_total > 0 then 1 else 0 end) / count(*), 1) as pct_rainy

    from daily
    group by city_name, state, climate_zone, latitude, longitude, elevation_m
)

select * from summary
order by avg_temp desc
