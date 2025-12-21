-- Report unresolved FK backfill rows for cross-module references.

-- Journal entry items missing account_id
SELECT 'journal_entry_items' AS table_name, id, account AS legacy_value
FROM journal_entry_items
WHERE account_id IS NULL
ORDER BY id;

-- Suppliers missing supplier_group_id
SELECT 'suppliers' AS table_name, id, supplier_group AS legacy_value
FROM suppliers
WHERE supplier_group IS NOT NULL
  AND supplier_group_id IS NULL
ORDER BY id;

-- Sales orders missing sales_partner_id
SELECT 'sales_orders.sales_partner' AS table_name, id, sales_partner AS legacy_value
FROM sales_orders
WHERE sales_partner IS NOT NULL
  AND sales_partner_id IS NULL
ORDER BY id;

-- Sales orders missing territory_id
SELECT 'sales_orders.territory' AS table_name, id, territory AS legacy_value
FROM sales_orders
WHERE territory IS NOT NULL
  AND territory_id IS NULL
ORDER BY id;

-- Quotations missing sales_partner_id
SELECT 'quotations.sales_partner' AS table_name, id, sales_partner AS legacy_value
FROM quotations
WHERE sales_partner IS NOT NULL
  AND sales_partner_id IS NULL
ORDER BY id;

-- Quotations missing territory_id
SELECT 'quotations.territory' AS table_name, id, territory AS legacy_value
FROM quotations
WHERE territory IS NOT NULL
  AND territory_id IS NULL
ORDER BY id;

-- Opportunities missing campaign_id
SELECT 'opportunities.campaign' AS table_name, id, campaign AS legacy_value
FROM opportunities
WHERE campaign IS NOT NULL
  AND campaign_id IS NULL
ORDER BY id;

-- Purchase orders missing cost_center_id
SELECT 'purchase_orders.cost_center' AS table_name, id, cost_center AS legacy_value
FROM purchase_orders
WHERE cost_center IS NOT NULL
  AND cost_center_id IS NULL
ORDER BY id;

-- Purchase orders missing project_id
SELECT 'purchase_orders.project' AS table_name, id, project AS legacy_value
FROM purchase_orders
WHERE project IS NOT NULL
  AND project_id IS NULL
ORDER BY id;
