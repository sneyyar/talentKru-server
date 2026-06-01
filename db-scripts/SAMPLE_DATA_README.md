# Sample Data Scripts for TalentKru.ai

This directory contains SQL scripts for creating and cleaning up sample data for demo and test automation purposes.

## Scripts

### `create_sample_data.sql`
Creates a complete set of sample data including:
- **1 Super Admin User**: System Administrator (admin@talentkru.ai)
- **1 Organization**: WexInc. Demo
- **8 Organization Users**:
  - 1 Organization Admin (Jennifer Chen)
  - 2 Recruiters (Marcus Johnson, Priya Patel)
  - 2 Hiring Managers (David Kumar, Elena Rodriguez)
  - 3 Interviewers (Alex Thompson, Sophia Lee, James Wilson)
- **5 Roles with Privileges**: super_admin, org_admin, recruiter, hiring_manager, interviewer
- **13 Skills** across 5 domains:
  - Programming Languages: Python, JavaScript, Java, Go
  - Web Technologies: React, FastAPI
  - Databases: PostgreSQL, MongoDB
  - Cloud Platforms: AWS, Google Cloud
  - Soft Skills: Communication, Leadership, Problem Solving
- **2 Job Profiles**: Senior Backend Engineer, Full Stack Developer
- **2 Job Requisitions**: Open positions for both profiles
- **6 Candidates** with realistic skills and experience:
  - Michael Chen (Senior Backend Engineer)
  - Natasha Volkov (Full Stack Developer)
  - Aisha Okafor (Backend Engineer)
  - Carlos Mendez (Junior Backend Engineer)
  - Emma Larsson (Full Stack Developer)
  - Raj Patel (Backend Engineer)
- **5 Interview Journeys**: Active interview processes for candidates

### `cleanup_sample_data.sql`
Removes all sample data created by `create_sample_data.sql` in the correct order to respect foreign key constraints.

## Usage

### Create Sample Data

```bash
# Against main database
PGPASSWORD=kruApp2026 psql -h localhost -p 5432 -U talentkru_app -d talentkru -f db-scripts/create_sample_data.sql

# Against test database
PGPASSWORD=kruTest2026 psql -h localhost -p 5432 -U kru_test -d kru_test_db -f db-scripts/create_sample_data.sql
```

### Clean Up Sample Data

```bash
# Against main database
PGPASSWORD=kruApp2026 psql -h localhost -p 5432 -U talentkru_app -d talentkru -f db-scripts/cleanup_sample_data.sql

# Against test database
PGPASSWORD=kruTest2026 psql -h localhost -p 5432 -U kru_test -d kru_test_db -f db-scripts/cleanup_sample_data.sql
```

## Sample Data Details

### Users & Credentials

All users have the password: `TestPassword123!`

#### Super Admin
- Email: `admin@talentkru.ai`
- Name: System Administrator
- Role: super_admin

#### WexInc. Demo Organization Users
All emails use the domain `@wexinc-demo.local`:

| Name | Email | Role |
|------|-------|------|
| Jennifer Chen | admin@wexinc-demo.local | org_admin |
| Marcus Johnson | marcus.johnson@wexinc-demo.local | recruiter |
| Priya Patel | priya.patel@wexinc-demo.local | recruiter |
| David Kumar | david.kumar@wexinc-demo.local | hiring_manager |
| Elena Rodriguez | elena.rodriguez@wexinc-demo.local | hiring_manager |
| Alex Thompson | alex.thompson@wexinc-demo.local | interviewer |
| Sophia Lee | sophia.lee@wexinc-demo.local | interviewer |
| James Wilson | james.wilson@wexinc-demo.local | interviewer |

### Candidates

All candidates are associated with WexInc. Demo organization:

| Name | Location | Primary Skills | Experience |
|------|----------|-----------------|------------|
| Michael Chen | San Francisco, CA | Python, FastAPI, PostgreSQL, AWS | 8 years |
| Natasha Volkov | New York, NY | JavaScript, React, Python, PostgreSQL | 7 years |
| Aisha Okafor | Austin, TX | Java, Python, PostgreSQL, Google Cloud | 6 years |
| Carlos Mendez | Seattle, WA | Python, FastAPI, PostgreSQL | 2 years |
| Emma Larsson | Portland, OR | JavaScript, React, PostgreSQL | 5 years |
| Raj Patel | Boston, MA | Go, Python, PostgreSQL, AWS | 6 years |

### Job Requisitions

| Title | Department | Location | Hiring Manager | Status |
|-------|-----------|----------|-----------------|--------|
| Senior Backend Engineer | Engineering | San Francisco, CA | David Kumar | OPEN |
| Full Stack Developer | Engineering | Remote | Elena Rodriguez | OPEN |

### Interview Journeys

All interview journeys are in ACTIVE status and linked to candidates and requisitions.

## Notes

- **No Schema/Database Creation**: These scripts only insert data. They assume the schema already exists.
- **Database Agnostic**: Scripts work against both main and test databases.
- **Plaintext PII**: Email and name fields are stored as plaintext (not encrypted) for demo purposes.
- **Relative Dates**: Interview journey dates are relative to today, allowing you to run cleanup and recreate with future dates.
- **Foreign Key Order**: Cleanup script deletes in correct order to respect foreign key constraints.
- **Idempotent Creation**: `create_sample_data.sql` uses `ON CONFLICT DO NOTHING` to allow safe re-runs.

## Workflow Example

```bash
# 1. Create sample data
psql -h localhost -p 5432 -U talentkru_app -d talentkru -f db-scripts/create_sample_data.sql

# 2. Run demo or tests
# ... your demo or test automation ...

# 3. Clean up
psql -h localhost -p 5432 -U talentkru_app -d talentkru -f db-scripts/cleanup_sample_data.sql

# 4. Recreate with new dates (if needed)
psql -h localhost -p 5432 -U talentkru_app -d talentkru -f db-scripts/create_sample_data.sql
```

## Troubleshooting

### Permission Denied
Ensure you're using the correct database user:
- Main database: `talentkru_app` with password `kruApp2026`
- Test database: `kru_test` with password `kruTest2026`

### Foreign Key Constraint Violations
If you encounter foreign key errors when running cleanup, ensure you're running the cleanup script against the same database where sample data was created.

### Duplicate Key Errors
If you get duplicate key errors when creating sample data, run the cleanup script first to remove any existing sample data.

## UUID Reference

Sample data uses predictable UUIDs for easy reference:

- **Organizations**: `10000000-0000-0000-0000-000000000001`
- **Users**: `20000000-0000-0000-0000-000000000001` through `20000000-0000-0000-0000-000000000009`
- **User Roles**: `30000000-0000-0000-0000-000000000001` through `30000000-0000-0000-0000-000000000009`
- **Domains**: `40000000-0000-0000-0000-000000000001` through `40000000-0000-0000-0000-000000000005`
- **Skills**: `41000000-0000-0000-0000-000000000001` through `41000000-0000-0000-0000-000000000013`
- **Job Profiles**: `50000000-0000-0000-0000-000000000001` through `50000000-0000-0000-0000-000000000002`
- **Job Profile Skills**: `51000000-0000-0000-0000-000000000001` through `51000000-0000-0000-0000-000000000009`
- **Job Requisitions**: `60000000-0000-0000-0000-000000000001` through `60000000-0000-0000-0000-000000000002`
- **Candidates**: `70000000-0000-0000-0000-000000000001` through `70000000-0000-0000-0000-000000000006`
- **Candidate Skills**: `71000000-0000-0000-0000-000000000001` through `71000000-0000-0000-0000-000000000024`
- **Candidate Requisitions**: `72000000-0000-0000-0000-000000000001` through `72000000-0000-0000-0000-000000000006`
- **Interview Journeys**: `80000000-0000-0000-0000-000000000001` through `80000000-0000-0000-0000-000000000005`
- **Privileges**: `550e8400-e29b-41d4-a716-446655440001` through `550e8400-e29b-41d4-a716-446655440010`
- **Role Privileges**: `650e8400-e29b-41d4-a716-446655440001` through `650e8400-e29b-41d4-a716-446655440031`
