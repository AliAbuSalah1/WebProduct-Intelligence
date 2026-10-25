-- Cheapest product with a rating of 4 or more in each category.
WITH ranked AS (
    SELECT source, category, title, price, currency, rating,
           ROW_NUMBER() OVER (PARTITION BY source, category ORDER BY price ASC) AS rn
    FROM products
    WHERE rating >= 4 AND category <> ''
)
SELECT source, category, title, price, currency, rating
FROM ranked WHERE rn = 1
ORDER BY source, category;
