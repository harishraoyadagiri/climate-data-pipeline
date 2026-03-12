/*
    Mart: Monthly Weather Aggregations
    Aggregates daily weather into monthly summaries per city.
*/

with daily as (
    select * from {{ ref('mart_city_daily') }}
),

monthly as (
    select
        city_name,
        state,
        climate_zone,
        year,
        month,
        month_name,
        season,

        -- Temperature
        round(avg(temp_avg), 2)   as avg_temp,
        round(min(temp_min), 2)   as min_temp,
        round(max(temp_max), 2)   as max_temp,
        round(avg(temp_range), 2) as avg_temp_range,

        -- Moisture
        round(avg(humidity_avg), 1)  as avg_humidity,
        round(sum(precip_total), 2)  as total_precip,

        -- Wind
        round(avg(wind_speed_avg), 2) as avg_wind_speed,
        round(max(wind_speed_max), 2) as max_wind_gust,

        -- Atmosphere
        round(avg(pressure_avg), 1)    as avg_pressure,
        round(avg(cloud_cover_avg), 1) as avg_cloud_cover,

        -- Counts
        count(*)                                        as days_recorded,
        sum(case when is_extreme_heat then 1 else 0 end) as extreme_heat_days,
        sum(case when is_freezing then 1 else 0 end)     as freezing_days,
        sum(case when precip_total > 0 then 1 else 0 end) as rainy_days

    from daily
    group by city_name, state, climate_zone, year, month, month_name, season
)

select * from monthly
order by city_name, year, month
