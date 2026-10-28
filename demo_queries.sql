USE autocare_db;
-- JOIN service records to vehicle, workshop and owner
SELECT u.name AS owner, v.registration_no, s.service_type, s.service_date,
       s.cost, COALESCE(w.name,'Independent') AS workshop
FROM service_records s JOIN vehicles v ON s.vehicle_id=v.id
JOIN users u ON u.id=v.user_id LEFT JOIN workshops w ON w.id=s.workshop_id
ORDER BY s.service_date DESC;

-- GROUP BY and HAVING: vehicles with at least two services
SELECT v.registration_no, COUNT(*) AS visits, SUM(s.cost) AS expenses
FROM vehicles v JOIN service_records s ON s.vehicle_id=v.id
GROUP BY v.id,v.registration_no HAVING COUNT(*) >= 2;

-- Nested query: above-average service expenses
SELECT id,service_type,cost FROM service_records
WHERE cost > (SELECT AVG(cost) FROM service_records);

-- View and stored procedure
SELECT * FROM vw_vehicle_expenses;
-- CALL sp_vehicle_service_summary(1); -- replace 1 with a real user ID

-- Trigger audit trail
SELECT * FROM service_audit ORDER BY changed_at DESC, id DESC;

-- Concurrency illustration (execute in two separate SQL sessions)
-- Session A: START TRANSACTION; SELECT * FROM vehicles WHERE id=1 FOR UPDATE;
-- Session B: START TRANSACTION; SELECT * FROM vehicles WHERE id=1 FOR UPDATE; -- waits
-- Session A: COMMIT; -- Session B then proceeds and should COMMIT or ROLLBACK.
