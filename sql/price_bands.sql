-- Distribution of products across price bands, per source.
SELECT source, currency,
       CASE WHEN price < 10 THEN '1. under 10'
            WHEN price < 25 THEN '2. 10-25'
            WHEN price < 50 THEN '3. 25-50'
            ELSE '4. 50+' END AS price_band,
       COUNT(*) AS products
FROM products
GROUP BY source, currency, price_band
ORDER BY source, price_band;
