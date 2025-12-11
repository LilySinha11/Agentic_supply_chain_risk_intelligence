// Constraints
CREATE CONSTRAINT IF NOT EXISTS FOR (s:Supplier) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (m:Manufacturer) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (h:Hub) REQUIRE h.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (c:Country) REQUIRE c.code IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (r:RiskEvent) REQUIRE r.id IS UNIQUE;

// Load Countries
LOAD CSV WITH HEADERS FROM 'file:///countries.csv' AS row
MERGE (c:Country {code: row.country})
SET c.name = row.name, c.geo_risk_index = toFloat(row.geo_risk_index);

// Load Suppliers
LOAD CSV WITH HEADERS FROM 'file:///suppliers.csv' AS row
MERGE (s:Supplier {id: row.supplier_id})
SET s.name = row.name,
    s.esg_score = toInteger(row.esg_score),
    s.financial_health = toFloat(row.financial_health),
    s.lead_time_days = toInteger(row.lead_time_days);

// Load Manufacturers
LOAD CSV WITH HEADERS FROM 'file:///manufacturers.csv' AS row
MERGE (m:Manufacturer {id: row.manu_id})
SET m.name = row.name, m.country = row.country;

// Load Products
LOAD CSV WITH HEADERS FROM 'file:///products.csv' AS row
MERGE (p:Product {id: row.product_id})
SET p.name = row.name, p.category = row.category;

// Load Hubs
LOAD CSV WITH HEADERS FROM 'file:///hubs.csv' AS row
MERGE (h:Hub {id: row.hub_id})
SET h.name = row.name, h.country = row.country;

// Relationships: LOCATED_IN
LOAD CSV WITH HEADERS FROM 'file:///relationships_located.csv' AS row
MATCH (c:Country {code: row.to_id})
WITH row, c
CALL {
  WITH row, c
  MATCH (s:Supplier {id: row.from_id})
  MERGE (s)-[:LOCATED_IN]->(c)
  RETURN 0 AS _
}
CALL {
  WITH row, c
  MATCH (m:Manufacturer {id: row.from_id})
  MERGE (m)-[:LOCATED_IN]->(c)
  RETURN 0 AS _
}
CALL {
  WITH row, c
  MATCH (h:Hub {id: row.from_id})
  MERGE (h)-[:LOCATED_IN]->(c)
  RETURN 0 AS _
};

// Relationships: SUPPLIES_TO
LOAD CSV WITH HEADERS FROM 'file:///relationships_supply.csv' AS row
MATCH (from {id: row.from_id})
MATCH (to {id: row.to_id})
MERGE (from)-[r:SUPPLIES_TO]->(to)
SET r.notes = row.notes;

// Risk Events
LOAD CSV WITH HEADERS FROM 'file:///risk_events.csv' AS row
MERGE (r:RiskEvent {id: row.event_id})
SET r.type = row.type, r.severity = toFloat(row.severity), r.description = row.description
WITH r, row
MATCH (c:Country {code: row.country})
MERGE (r)-[:AFFECTS]->(c);