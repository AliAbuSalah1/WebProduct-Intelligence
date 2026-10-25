-- Products whose price differs between the two most recent runs.
WITH ranked AS (
    SELECT source, product_url, title, currency, price, scraped_at_utc,
           ROW_NUMBER() OVER (PARTITION BY source, product_url
                              ORDER BY scraped_at_utc DESC) AS rn
    FROM price_history
)
SELECT cur.source,
       cur.title,
       cur.currency,
       prev.price                                           AS old_price,
       cur.price                                            AS new_price,
       ROUND(cur.price - prev.price, 2)                     AS change,
       ROUND(100.0 * (cur.price - prev.price) / prev.price, 1) AS change_pct,
       cur.scraped_at_utc                                   AS changed_at
FROM ranked cur
JOIN ranked prev
  ON prev.source = cur.source AND prev.product_url = cur.product_url
 AND cur.rn = 1 AND prev.rn = 2
WHERE cur.price <> prev.price AND prev.price > 0
ORDER BY ABS(change_pct) DESC;
