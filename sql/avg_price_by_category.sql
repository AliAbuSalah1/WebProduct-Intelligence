-- Average, min and max price per source and category (categories never mix currencies).
SELECT source, currency, category,
       COUNT(*)              AS products,
       ROUND(AVG(price), 2)  AS avg_price,
       MIN(price)            AS min_price,
       MAX(price)            AS max_price
FROM products
WHERE category <> ''
GROUP BY source, currency, category
ORDER BY source, avg_price DESC;
