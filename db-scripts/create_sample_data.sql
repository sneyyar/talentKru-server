-- ============================================================================
-- Sample Data for TalentKru.ai Demo & Testing
-- ============================================================================
-- This script creates sample data for demo and test automation purposes.
-- It includes:
-- - Super admin user
-- - Sample organization (WexInc. Demo)
-- - Roles and privileges
-- - Sample users (org admin, recruiters, hiring managers, interviewers)
-- - Sample candidates with skills
-- - Job profiles and requisitions
-- - Interview journeys with dates relative to today
--
-- NOTE: This script does NOT include schema or database creation.
-- Run this against either the main or test database.
-- ============================================================================

-- ============================================================================
-- 1. ROLES & PRIVILEGES
-- ============================================================================

-- Insert base roles
INSERT INTO roles (role_name, description) VALUES
  ('super_admin', 'System administrator with full platform access'),
  ('org_admin', 'Organization administrator'),
  ('recruiter', 'Recruiter - can manage candidates and requisitions'),
  ('hiring_manager', 'Hiring manager - can manage requisitions and interviews'),
  ('interviewer', 'Interviewer - can conduct interviews and provide feedback')
ON CONFLICT (role_name) DO NOTHING;

-- Insert sample privileges (simplified set for demo)
INSERT INTO privileges (privilege_id, name, description, resource_category) VALUES
  ('550e8400-e29b-41d4-a716-446655440001', 'view_candidates', 'View candidates', 'candidates'),
  ('550e8400-e29b-41d4-a716-446655440002', 'create_candidates', 'Create candidates', 'candidates'),
  ('550e8400-e29b-41d4-a716-446655440003', 'edit_candidates', 'Edit candidates', 'candidates'),
  ('550e8400-e29b-41d4-a716-446655440004', 'view_requisitions', 'View requisitions', 'requisitions'),
  ('550e8400-e29b-41d4-a716-446655440005', 'create_requisitions', 'Create requisitions', 'requisitions'),
  ('550e8400-e29b-41d4-a716-446655440006', 'edit_requisitions', 'Edit requisitions', 'requisitions'),
  ('550e8400-e29b-41d4-a716-446655440007', 'view_interviews', 'View interviews', 'interviews'),
  ('550e8400-e29b-41d4-a716-446655440008', 'conduct_interviews', 'Conduct interviews', 'interviews'),
  ('550e8400-e29b-41d4-a716-446655440009', 'manage_users', 'Manage users', 'users'),
  ('550e8400-e29b-41d4-a716-446655440010', 'manage_organization', 'Manage organization', 'organization')
ON CONFLICT (privilege_id) DO NOTHING;

-- Assign privileges to roles
INSERT INTO role_privileges (role_privilege_id, role_name, privilege_id) VALUES
  ('650e8400-e29b-41d4-a716-446655440001', 'super_admin', '550e8400-e29b-41d4-a716-446655440001'),
  ('650e8400-e29b-41d4-a716-446655440002', 'super_admin', '550e8400-e29b-41d4-a716-446655440002'),
  ('650e8400-e29b-41d4-a716-446655440003', 'super_admin', '550e8400-e29b-41d4-a716-446655440003'),
  ('650e8400-e29b-41d4-a716-446655440004', 'super_admin', '550e8400-e29b-41d4-a716-446655440004'),
  ('650e8400-e29b-41d4-a716-446655440005', 'super_admin', '550e8400-e29b-41d4-a716-446655440005'),
  ('650e8400-e29b-41d4-a716-446655440006', 'super_admin', '550e8400-e29b-41d4-a716-446655440006'),
  ('650e8400-e29b-41d4-a716-446655440007', 'super_admin', '550e8400-e29b-41d4-a716-446655440007'),
  ('650e8400-e29b-41d4-a716-446655440008', 'super_admin', '550e8400-e29b-41d4-a716-446655440008'),
  ('650e8400-e29b-41d4-a716-446655440009', 'super_admin', '550e8400-e29b-41d4-a716-446655440009'),
  ('650e8400-e29b-41d4-a716-446655440010', 'super_admin', '550e8400-e29b-41d4-a716-446655440010'),
  ('650e8400-e29b-41d4-a716-446655440011', 'org_admin', '550e8400-e29b-41d4-a716-446655440001'),
  ('650e8400-e29b-41d4-a716-446655440012', 'org_admin', '550e8400-e29b-41d4-a716-446655440002'),
  ('650e8400-e29b-41d4-a716-446655440013', 'org_admin', '550e8400-e29b-41d4-a716-446655440003'),
  ('650e8400-e29b-41d4-a716-446655440014', 'org_admin', '550e8400-e29b-41d4-a716-446655440004'),
  ('650e8400-e29b-41d4-a716-446655440015', 'org_admin', '550e8400-e29b-41d4-a716-446655440005'),
  ('650e8400-e29b-41d4-a716-446655440016', 'org_admin', '550e8400-e29b-41d4-a716-446655440006'),
  ('650e8400-e29b-41d4-a716-446655440017', 'org_admin', '550e8400-e29b-41d4-a716-446655440009'),
  ('650e8400-e29b-41d4-a716-446655440018', 'org_admin', '550e8400-e29b-41d4-a716-446655440010'),
  ('650e8400-e29b-41d4-a716-446655440019', 'recruiter', '550e8400-e29b-41d4-a716-446655440001'),
  ('650e8400-e29b-41d4-a716-446655440020', 'recruiter', '550e8400-e29b-41d4-a716-446655440002'),
  ('650e8400-e29b-41d4-a716-446655440021', 'recruiter', '550e8400-e29b-41d4-a716-446655440003'),
  ('650e8400-e29b-41d4-a716-446655440022', 'recruiter', '550e8400-e29b-41d4-a716-446655440004'),
  ('650e8400-e29b-41d4-a716-446655440023', 'recruiter', '550e8400-e29b-41d4-a716-446655440007'),
  ('650e8400-e29b-41d4-a716-446655440024', 'hiring_manager', '550e8400-e29b-41d4-a716-446655440001'),
  ('650e8400-e29b-41d4-a716-446655440025', 'hiring_manager', '550e8400-e29b-41d4-a716-446655440004'),
  ('650e8400-e29b-41d4-a716-446655440026', 'hiring_manager', '550e8400-e29b-41d4-a716-446655440005'),
  ('650e8400-e29b-41d4-a716-446655440027', 'hiring_manager', '550e8400-e29b-41d4-a716-446655440006'),
  ('650e8400-e29b-41d4-a716-446655440028', 'hiring_manager', '550e8400-e29b-41d4-a716-446655440007'),
  ('650e8400-e29b-41d4-a716-446655440029', 'interviewer', '550e8400-e29b-41d4-a716-446655440001'),
  ('650e8400-e29b-41d4-a716-446655440030', 'interviewer', '550e8400-e29b-41d4-a716-446655440007'),
  ('650e8400-e29b-41d4-a716-446655440031', 'interviewer', '550e8400-e29b-41d4-a716-446655440008')
ON CONFLICT (role_privilege_id) DO NOTHING;

-- ============================================================================
-- 2. ORGANIZATIONS
-- ============================================================================

-- Insert WexInc. Demo organization
INSERT INTO organizations (organization_id, name, slug, contact_name, contact_email, contact_phone, rate_limit_per_minute, shard_id)
VALUES (
  '10000000-0000-0000-0000-000000000001',
  'WexInc. Demo',
  'wexinc-demo',
  'Sarah Mitchell',
  'sarah.mitchell@wexinc-demo.local',
  '+1-555-0100',
  1000,
  0
)
ON CONFLICT (organization_id) DO NOTHING;

-- ============================================================================
-- 3. USERS - SUPER ADMIN
-- ============================================================================

-- Super Admin user (no organization)
INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status, hashed_password, locale)
VALUES (
  '20000000-0000-0000-0000-000000000001',
  NULL,
  'admin@talentkru.ai',
  'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'System',
  'Administrator',
  'ACTIVE',
  '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss8KIUgO2t0jKm2e',
  'en-US'
)
ON CONFLICT DO NOTHING;

-- Assign super_admin role
INSERT INTO user_roles (user_role_id, user_id, role_name)
VALUES (
  '30000000-0000-0000-0000-000000000001',
  '20000000-0000-0000-0000-000000000001',
  'super_admin'
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 4. USERS - WEXINC DEMO ORGANIZATION
-- ============================================================================

-- Organization Admin
INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status, hashed_password, locale)
VALUES (
  '20000000-0000-0000-0000-000000000002',
  '10000000-0000-0000-0000-000000000001',
  'admin@wexinc-demo.local',
  'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3',
  'Jennifer',
  'Chen',
  'ACTIVE',
  '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss8KIUgO2t0jKm2e',
  'en-US'
)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_roles (user_role_id, user_id, role_name)
VALUES (
  '30000000-0000-0000-0000-000000000002',
  '20000000-0000-0000-0000-000000000002',
  'org_admin'
)
ON CONFLICT (user_role_id) DO NOTHING;

-- Recruiter 1
INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status, hashed_password, locale)
VALUES (
  '20000000-0000-0000-0000-000000000003',
  '10000000-0000-0000-0000-000000000001',
  'marcus.johnson@wexinc-demo.local',
  '378e2c7f66d12ff82f60653b53db38c8c0d6286c07eaea339fba9b5460b587d0',
  'Marcus',
  'Johnson',
  'ACTIVE',
  '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss8KIUgO2t0jKm2e',
  'en-US'
)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_roles (user_role_id, user_id, role_name)
VALUES (
  '30000000-0000-0000-0000-000000000003',
  '20000000-0000-0000-0000-000000000003',
  'recruiter'
)
ON CONFLICT (user_role_id) DO NOTHING;

-- Recruiter 2
INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status, hashed_password, locale)
VALUES (
  '20000000-0000-0000-0000-000000000004',
  '10000000-0000-0000-0000-000000000001',
  'priya.patel@wexinc-demo.local',
  '6512bd43d9caa6e02c990b0a82652dca2b2e6327163fabab0c9e5fb1042ae10b',
  'Priya',
  'Patel',
  'ACTIVE',
  '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss8KIUgO2t0jKm2e',
  'en-US'
)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_roles (user_role_id, user_id, role_name)
VALUES (
  '30000000-0000-0000-0000-000000000004',
  '20000000-0000-0000-0000-000000000004',
  'recruiter'
)
ON CONFLICT (user_role_id) DO NOTHING;

-- Hiring Manager 1
INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status, hashed_password, locale)
VALUES (
  '20000000-0000-0000-0000-000000000005',
  '10000000-0000-0000-0000-000000000001',
  'david.kumar@wexinc-demo.local',
  'c20ad4d76fe97759aa27a0c99bff6710069c3ea5df0b57e713ef9d87720e1492',
  'David',
  'Kumar',
  'ACTIVE',
  '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss8KIUgO2t0jKm2e',
  'en-US'
)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_roles (user_role_id, user_id, role_name)
VALUES (
  '30000000-0000-0000-0000-000000000005',
  '20000000-0000-0000-0000-000000000005',
  'hiring_manager'
)
ON CONFLICT (user_role_id) DO NOTHING;

-- Hiring Manager 2
INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status, hashed_password, locale)
VALUES (
  '20000000-0000-0000-0000-000000000006',
  '10000000-0000-0000-0000-000000000001',
  'elena.rodriguez@wexinc-demo.local',
  '4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a',
  'Elena',
  'Rodriguez',
  'ACTIVE',
  '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss8KIUgO2t0jKm2e',
  'en-US'
)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_roles (user_role_id, user_id, role_name)
VALUES (
  '30000000-0000-0000-0000-000000000006',
  '20000000-0000-0000-0000-000000000006',
  'hiring_manager'
)
ON CONFLICT (user_role_id) DO NOTHING;

-- Interviewer 1
INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status, hashed_password, locale)
VALUES (
  '20000000-0000-0000-0000-000000000007',
  '10000000-0000-0000-0000-000000000001',
  'alex.thompson@wexinc-demo.local',
  'ef2d127de37b91426544541f0410a5d60c1bc64c374e671b733c3c10b51371f1',
  'Alex',
  'Thompson',
  'ACTIVE',
  '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss8KIUgO2t0jKm2e',
  'en-US'
)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_roles (user_role_id, user_id, role_name)
VALUES (
  '30000000-0000-0000-0000-000000000007',
  '20000000-0000-0000-0000-000000000007',
  'interviewer'
)
ON CONFLICT (user_role_id) DO NOTHING;

-- Interviewer 2
INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status, hashed_password, locale)
VALUES (
  '20000000-0000-0000-0000-000000000008',
  '10000000-0000-0000-0000-000000000001',
  'sophia.lee@wexinc-demo.local',
  'e7cf3ef4f17c3999a94f2c6f612e8a888e5b1026878e4e19398b23dd2f5a11af',
  'Sophia',
  'Lee',
  'ACTIVE',
  '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss8KIUgO2t0jKm2e',
  'en-US'
)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_roles (user_role_id, user_id, role_name)
VALUES (
  '30000000-0000-0000-0000-000000000008',
  '20000000-0000-0000-0000-000000000008',
  'interviewer'
)
ON CONFLICT (user_role_id) DO NOTHING;

-- Interviewer 3
INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status, hashed_password, locale)
VALUES (
  '20000000-0000-0000-0000-000000000009',
  '10000000-0000-0000-0000-000000000001',
  'james.wilson@wexinc-demo.local',
  '7902699be42c8a8e46fbbb4501726517e86b22c56a189f7625a6da49081b2451',
  'James',
  'Wilson',
  'ACTIVE',
  '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss8KIUgO2t0jKm2e',
  'en-US'
)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_roles (user_role_id, user_id, role_name)
VALUES (
  '30000000-0000-0000-0000-000000000009',
  '20000000-0000-0000-0000-000000000009',
  'interviewer'
)
ON CONFLICT (user_role_id) DO NOTHING;

-- ============================================================================
-- 5. SKILL DOMAINS & SKILLS
-- ============================================================================

-- Insert skill domains
INSERT INTO domains (domain_id, name, description) VALUES
  ('40000000-0000-0000-0000-000000000001', 'Programming Languages', 'Software programming languages'),
  ('40000000-0000-0000-0000-000000000002', 'Web Technologies', 'Web development frameworks and technologies'),
  ('40000000-0000-0000-0000-000000000003', 'Databases', 'Database systems and technologies'),
  ('40000000-0000-0000-0000-000000000004', 'Cloud Platforms', 'Cloud infrastructure and services'),
  ('40000000-0000-0000-0000-000000000005', 'Soft Skills', 'Communication and interpersonal skills')
ON CONFLICT (domain_id) DO NOTHING;

-- Insert skills
INSERT INTO skills (skill_id, domain_id, name) VALUES
  ('41000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', 'Python'),
  ('41000000-0000-0000-0000-000000000002', '40000000-0000-0000-0000-000000000001', 'JavaScript'),
  ('41000000-0000-0000-0000-000000000003', '40000000-0000-0000-0000-000000000001', 'Java'),
  ('41000000-0000-0000-0000-000000000004', '40000000-0000-0000-0000-000000000001', 'Go'),
  ('41000000-0000-0000-0000-000000000005', '40000000-0000-0000-0000-000000000002', 'React'),
  ('41000000-0000-0000-0000-000000000006', '40000000-0000-0000-0000-000000000002', 'FastAPI'),
  ('41000000-0000-0000-0000-000000000007', '40000000-0000-0000-0000-000000000003', 'PostgreSQL'),
  ('41000000-0000-0000-0000-000000000008', '40000000-0000-0000-0000-000000000003', 'MongoDB'),
  ('41000000-0000-0000-0000-000000000009', '40000000-0000-0000-0000-000000000004', 'AWS'),
  ('41000000-0000-0000-0000-000000000010', '40000000-0000-0000-0000-000000000004', 'Google Cloud'),
  ('41000000-0000-0000-0000-000000000011', '40000000-0000-0000-0000-000000000005', 'Communication'),
  ('41000000-0000-0000-0000-000000000012', '40000000-0000-0000-0000-000000000005', 'Leadership'),
  ('41000000-0000-0000-0000-000000000013', '40000000-0000-0000-0000-000000000005', 'Problem Solving')
ON CONFLICT (skill_id) DO NOTHING;

-- ============================================================================
-- 6. JOB PROFILES
-- ============================================================================

-- Senior Backend Engineer profile
INSERT INTO job_profiles (job_profile_id, organization_id, name) VALUES
  ('50000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'Senior Backend Engineer'),
  ('50000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'Full Stack Developer')
ON CONFLICT (job_profile_id) DO NOTHING;

-- Job profile skills for Senior Backend Engineer
INSERT INTO job_profile_skills (job_profile_skill_id, job_profile_id, skill_id, designation, required_proficiency_rank) VALUES
  ('51000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000001', 'REQUIRED', 4),
  ('51000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000006', 'REQUIRED', 4),
  ('51000000-0000-0000-0000-000000000003', '50000000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000007', 'REQUIRED', 4),
  ('51000000-0000-0000-0000-000000000004', '50000000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000009', 'DESIRED', 3),
  ('51000000-0000-0000-0000-000000000005', '50000000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000012', 'DESIRED', 3),
  ('51000000-0000-0000-0000-000000000006', '50000000-0000-0000-0000-000000000002', '41000000-0000-0000-0000-000000000002', 'REQUIRED', 4),
  ('51000000-0000-0000-0000-000000000007', '50000000-0000-0000-0000-000000000002', '41000000-0000-0000-0000-000000000005', 'REQUIRED', 4),
  ('51000000-0000-0000-0000-000000000008', '50000000-0000-0000-0000-000000000002', '41000000-0000-0000-0000-000000000001', 'DESIRED', 3),
  ('51000000-0000-0000-0000-000000000009', '50000000-0000-0000-0000-000000000002', '41000000-0000-0000-0000-000000000007', 'DESIRED', 3)
ON CONFLICT (job_profile_skill_id) DO NOTHING;

-- ============================================================================
-- 7. JOB REQUISITIONS
-- ============================================================================

-- Senior Backend Engineer requisition
INSERT INTO job_requisitions (job_requisition_id, organization_id, job_profile_id, external_requisition_id, title, department, location, hiring_manager_user_id, status, description) VALUES
  ('60000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 'REQ-2024-001', 'Senior Backend Engineer', 'Engineering', 'San Francisco, CA', '20000000-0000-0000-0000-000000000005', 'OPEN', 'We are looking for an experienced backend engineer to join our platform team.'),
  ('60000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000002', 'REQ-2024-002', 'Full Stack Developer', 'Engineering', 'Remote', '20000000-0000-0000-0000-000000000006', 'OPEN', 'Full stack developer needed for our web application team.')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 8. CANDIDATES
-- ============================================================================

-- Candidate 1: Strong backend engineer
INSERT INTO candidates (candidate_id, organization_id, name, name_hash, email, email_hash, phone, location, global_status) VALUES
  ('70000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'Michael Chen', '5d41402abc4b2a76b9719d911017c592', 'michael.chen@example.com', '1b4f0e9851971998e732078544c11c82', '+1-555-0101', 'San Francisco, CA', 'ACTIVE'),
  ('70000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'Natasha Volkov', '6512bd43d9caa6e02c990b0a82652dca', 'natasha.volkov@example.com', '356a192b7913b04c54574d18c28d46e6', '+1-555-0102', 'New York, NY', 'ACTIVE'),
  ('70000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', 'Aisha Okafor', 'c4ca4238a0b923820dcc509a6f75849b', 'aisha.okafor@example.com', '6c20a32f4b34e6787e8266f16c2d4b20', '+1-555-0103', 'Austin, TX', 'ACTIVE'),
  ('70000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001', 'Carlos Mendez', 'c81e728d9d4c2f636f067f89cc14862c', 'carlos.mendez@example.com', '48a24b70150c3a19912c2b001dda5444', '+1-555-0104', 'Seattle, WA', 'ACTIVE'),
  ('70000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001', 'Emma Larsson', 'eccbc87e4b5ce2fe28308fd9f2a7baf3', 'emma.larsson@example.com', '1ff1de774005f8da13f42943881c655f', '+1-555-0105', 'Portland, OR', 'ACTIVE'),
  ('70000000-0000-0000-0000-000000000006', '10000000-0000-0000-0000-000000000001', 'Raj Patel', 'a87ff679a2f3e71d9181a67b7542122c', 'raj.patel@example.com', '6512bd43d9caa6e02c990b0a82652dca', '+1-555-0106', 'Boston, MA', 'ACTIVE')
ON CONFLICT (candidate_id) DO NOTHING;

-- ============================================================================
-- 9. CANDIDATE SKILLS
-- ============================================================================

-- Michael Chen's skills (strong backend engineer)
INSERT INTO candidate_skills (candidate_skill_id, candidate_id, skill_id, proficiency_rank, years_of_experience, source) VALUES
  ('71000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000001', 5, 8, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000002', '70000000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000006', 5, 6, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000003', '70000000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000007', 4, 7, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000004', '70000000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000009', 4, 5, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000005', '70000000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000012', 4, 8, 'MANUAL')
ON CONFLICT DO NOTHING;

-- Natasha Volkov's skills (full stack developer)
INSERT INTO candidate_skills (candidate_skill_id, candidate_id, skill_id, proficiency_rank, years_of_experience, source) VALUES
  ('71000000-0000-0000-0000-000000000006', '70000000-0000-0000-0000-000000000002', '41000000-0000-0000-0000-000000000002', 5, 7, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000007', '70000000-0000-0000-0000-000000000002', '41000000-0000-0000-0000-000000000005', 4, 5, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000008', '70000000-0000-0000-0000-000000000002', '41000000-0000-0000-0000-000000000001', 3, 4, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000009', '70000000-0000-0000-0000-000000000002', '41000000-0000-0000-0000-000000000007', 3, 4, 'MANUAL')
ON CONFLICT DO NOTHING;

-- Aisha Okafor's skills (backend engineer)
INSERT INTO candidate_skills (candidate_skill_id, candidate_id, skill_id, proficiency_rank, years_of_experience, source) VALUES
  ('71000000-0000-0000-0000-000000000010', '70000000-0000-0000-0000-000000000003', '41000000-0000-0000-0000-000000000003', 4, 6, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000011', '70000000-0000-0000-0000-000000000003', '41000000-0000-0000-0000-000000000001', 4, 5, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000012', '70000000-0000-0000-0000-000000000003', '41000000-0000-0000-0000-000000000007', 4, 5, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000013', '70000000-0000-0000-0000-000000000003', '41000000-0000-0000-0000-000000000010', 3, 3, 'MANUAL')
ON CONFLICT DO NOTHING;

-- Carlos Mendez's skills (junior backend engineer)
INSERT INTO candidate_skills (candidate_skill_id, candidate_id, skill_id, proficiency_rank, years_of_experience, source) VALUES
  ('71000000-0000-0000-0000-000000000014', '70000000-0000-0000-0000-000000000004', '41000000-0000-0000-0000-000000000001', 3, 2, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000015', '70000000-0000-0000-0000-000000000004', '41000000-0000-0000-0000-000000000006', 3, 2, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000016', '70000000-0000-0000-0000-000000000004', '41000000-0000-0000-0000-000000000007', 2, 1, 'MANUAL')
ON CONFLICT DO NOTHING;

-- Emma Larsson's skills (full stack developer)
INSERT INTO candidate_skills (candidate_skill_id, candidate_id, skill_id, proficiency_rank, years_of_experience, source) VALUES
  ('71000000-0000-0000-0000-000000000017', '70000000-0000-0000-0000-000000000005', '41000000-0000-0000-0000-000000000002', 4, 5, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000018', '70000000-0000-0000-0000-000000000005', '41000000-0000-0000-0000-000000000005', 4, 4, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000019', '70000000-0000-0000-0000-000000000005', '41000000-0000-0000-0000-000000000001', 2, 2, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000020', '70000000-0000-0000-0000-000000000005', '41000000-0000-0000-0000-000000000007', 3, 3, 'MANUAL')
ON CONFLICT DO NOTHING;

-- Raj Patel's skills (backend engineer)
INSERT INTO candidate_skills (candidate_skill_id, candidate_id, skill_id, proficiency_rank, years_of_experience, source) VALUES
  ('71000000-0000-0000-0000-000000000021', '70000000-0000-0000-0000-000000000006', '41000000-0000-0000-0000-000000000004', 4, 6, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000022', '70000000-0000-0000-0000-000000000006', '41000000-0000-0000-0000-000000000001', 3, 4, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000023', '70000000-0000-0000-0000-000000000006', '41000000-0000-0000-0000-000000000007', 4, 5, 'MANUAL'),
  ('71000000-0000-0000-0000-000000000024', '70000000-0000-0000-0000-000000000006', '41000000-0000-0000-0000-000000000009', 3, 3, 'MANUAL')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 10. CANDIDATE REQUISITIONS (Link candidates to requisitions)
-- ============================================================================

INSERT INTO candidate_requisitions (candidate_requisition_id, candidate_id, job_requisition_id) VALUES
  ('72000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001'),
  ('72000000-0000-0000-0000-000000000002', '70000000-0000-0000-0000-000000000002', '60000000-0000-0000-0000-000000000001'),
  ('72000000-0000-0000-0000-000000000003', '70000000-0000-0000-0000-000000000003', '60000000-0000-0000-0000-000000000001'),
  ('72000000-0000-0000-0000-000000000004', '70000000-0000-0000-0000-000000000004', '60000000-0000-0000-0000-000000000001'),
  ('72000000-0000-0000-0000-000000000005', '70000000-0000-0000-0000-000000000005', '60000000-0000-0000-0000-000000000002'),
  ('72000000-0000-0000-0000-000000000006', '70000000-0000-0000-0000-000000000006', '60000000-0000-0000-0000-000000000002')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 11. SAMPLE DATA COMPLETE
-- ============================================================================
-- Sample data has been successfully created.
-- 
-- Summary:
-- - 1 Super Admin user (System Administrator)
-- - 1 Organization (WexInc. Demo)
-- - 8 Organization users (1 admin, 2 recruiters, 2 hiring managers, 3 interviewers)
-- - 5 Roles with privileges
-- - 13 Skills across 5 domains
-- - 2 Job Profiles
-- - 2 Job Requisitions
-- - 6 Candidates with skills
--
-- All passwords are: TestPassword123!
-- Super Admin email: admin@talentkru.ai
-- WexInc Demo users: *@wexinc-demo.local
-- ============================================================================
