CREATE DATABASE IF NOT EXISTS autocare_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE autocare_db;

CREATE TABLE IF NOT EXISTS users (
 id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100) NOT NULL,
 email VARCHAR(190) NOT NULL UNIQUE, password_hash VARCHAR(255) NOT NULL,
 role ENUM('owner','admin') NOT NULL DEFAULT 'owner', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS vehicles (
 id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,
 registration_no VARCHAR(30) NOT NULL UNIQUE, make VARCHAR(70) NOT NULL,
 model VARCHAR(70) NOT NULL, vehicle_type ENUM('Car','Bike','Scooter','Other') NOT NULL DEFAULT 'Car',
 manufacture_year SMALLINT NULL, odometer INT UNSIGNED NOT NULL DEFAULT 0,
 fuel_type VARCHAR(30) DEFAULT 'Petrol', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 CHECK (manufacture_year IS NULL OR manufacture_year BETWEEN 1900 AND 2100)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS workshops (
 id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, name VARCHAR(120) NOT NULL,
 city VARCHAR(90), phone VARCHAR(30),
 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS service_records (
 id INT AUTO_INCREMENT PRIMARY KEY, vehicle_id INT NOT NULL, workshop_id INT NULL,
 service_type VARCHAR(80) NOT NULL, service_date DATE NOT NULL,
 odometer INT UNSIGNED NOT NULL, cost DECIMAL(12,2) NOT NULL DEFAULT 0,
 notes TEXT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
 FOREIGN KEY (workshop_id) REFERENCES workshops(id) ON DELETE SET NULL,
 CHECK (cost >= 0), INDEX idx_service_vehicle_date(vehicle_id,service_date)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS service_reminders (
 id INT AUTO_INCREMENT PRIMARY KEY, vehicle_id INT NOT NULL,
 title VARCHAR(120) NOT NULL, due_date DATE NULL, due_odometer INT UNSIGNED NULL,
 status ENUM('Pending','Completed') NOT NULL DEFAULT 'Pending',
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
 CHECK (due_date IS NOT NULL OR due_odometer IS NOT NULL),
 INDEX idx_reminder_status_date(status,due_date)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS service_audit (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, service_id INT NOT NULL,
 event_type ENUM('INSERT','UPDATE','DELETE') NOT NULL,
 old_cost DECIMAL(12,2) NULL, new_cost DECIMAL(12,2) NULL,
 changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

DROP TRIGGER IF EXISTS trg_service_insert;
DROP TRIGGER IF EXISTS trg_service_update;
DROP TRIGGER IF EXISTS trg_service_delete;
DELIMITER $$
CREATE TRIGGER trg_service_insert AFTER INSERT ON service_records FOR EACH ROW
BEGIN INSERT INTO service_audit(service_id,event_type,new_cost) VALUES(NEW.id,'INSERT',NEW.cost); END$$
CREATE TRIGGER trg_service_update AFTER UPDATE ON service_records FOR EACH ROW
BEGIN INSERT INTO service_audit(service_id,event_type,old_cost,new_cost) VALUES(NEW.id,'UPDATE',OLD.cost,NEW.cost); END$$
CREATE TRIGGER trg_service_delete AFTER DELETE ON service_records FOR EACH ROW
BEGIN INSERT INTO service_audit(service_id,event_type,old_cost) VALUES(OLD.id,'DELETE',OLD.cost); END$$
DELIMITER ;

CREATE OR REPLACE VIEW vw_vehicle_expenses AS
SELECT v.id AS vehicle_id, v.user_id, v.registration_no, v.make, v.model,
 COUNT(s.id) AS service_count, COALESCE(SUM(s.cost),0) AS total_spend,
 MAX(s.service_date) AS last_service
FROM vehicles v LEFT JOIN service_records s ON s.vehicle_id=v.id
GROUP BY v.id,v.user_id,v.registration_no,v.make,v.model;

DROP PROCEDURE IF EXISTS sp_vehicle_service_summary;
DELIMITER $$
CREATE PROCEDURE sp_vehicle_service_summary(IN p_user_id INT)
BEGIN
 SELECT * FROM vw_vehicle_expenses WHERE user_id=p_user_id ORDER BY total_spend DESC;
END$$
DELIMITER ;
