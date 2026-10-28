-- Run as a MySQL administrator, after schema.sql. Change this example password.
CREATE USER IF NOT EXISTS 'autocare_app'@'localhost' IDENTIFIED BY 'change_this_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON autocare_db.* TO 'autocare_app'@'localhost';
-- The app does not need CREATE, DROP, ALTER, TRIGGER, or GRANT privileges.
SHOW GRANTS FOR 'autocare_app'@'localhost';
-- If using a different host for the application, adjust the account host accordingly.
