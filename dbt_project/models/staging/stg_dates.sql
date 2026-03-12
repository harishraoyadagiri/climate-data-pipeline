/*
    Staging: Date Dimension
    Clean date reference data for joins and time-series analysis.
*/

with source as (
    select * from {{ source('raw', 'dim_date') }}
),

cleaned as (
    select
        date_id,
        cast(date as varchar) as date,
        year,
        month,
        day,
        quarter,
        day_of_week,
        cast(is_weekend as boolean) as is_weekend,
        season,
        month_name
    from source
)

select * from cleaned
