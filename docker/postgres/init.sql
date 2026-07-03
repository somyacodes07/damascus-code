-- Damascus PostgreSQL initialization
-- This script runs when the PostgreSQL container starts for the first time.

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Note: Apache AGE (graph extension) will be configured separately in a later phase.
