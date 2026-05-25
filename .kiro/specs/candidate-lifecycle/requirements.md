# Requirements Document

## Introduction

This is the Candidate Lifecycle module of TalentKru.ai Server, covering candidate profile management, resume upload and ingestion, skills taxonomy, job profiles and postings, job requisitions, and data privacy/compliance (GDPR). This module defines the core entities and workflows that track a candidate from initial profile creation through resume parsing, skill extraction, job matching, and eventual data retention or erasure.

Key architectural decisions relevant to this module:
- PostgreSQL with pgvector extension for semantic search over candidate embeddings generated from parsed resumes.
- S3-compatible bucket (cloud) and local filesystem directory (development) as configurable storage backends for resume files.
- Soft delete for data retention; candidate records are logically deleted by populating DeletedAt/DeletedBy AuditFields while retaining the record for audit purposes.
- FastAPI background tasks for async processing of resume ingestion and skill extraction.
- Field-level encryption of candidate PII (Name, Email, Phone) at rest using the ENCRYPTION_KEY environment variable.

## Glossary

- **Server**: The TalentKru.ai FastAPI backend application.
- **Organization**: A client tenant in the system; all data is scoped to an organization.
- **Candidate**: A job applicant tracked within an organization's recruiting pipeline.
- **JobRequisition**: An open position within an organization that candidates are matched against.
- **JobProfile**: A job category representing a set of required or desired skills.
- **JobPosting**: The public-facing details of a job including description, location, and salary range.
- **ResumeIngestionAgent**: An AI agent that parses resumes, extracts skills, and generates embeddings.
- **AuditFields**: Standard fields on all entities: CreatedAt, UpdatedAt, DeletedAt, CreatedBy, UpdatedBy, DeletedBy.
- **ENCRYPTION_KEY**: The secret key used exclusively for field-level encryption of PII data at rest.

## Requirements

### Requirement 1: Candidate Management

**User Story:** As a recruiter, I want to create and manage candidate profiles, so that I can track applicants through the hiring process.

#### Acceptance Criteria

1. THE Server SHALL store Candidate entities with fields: CandidateID (UUID), OrganizationID (FK), Name (max 200 characters), Email (max 254 characters), Phone (max 50 characters), Location (max 200 characters), GlobalStatus (Active, Interviewing, Expired, Ineligible, Deleted), IneligibilityReason (nullable, max 1000 characters), and AuditFields.
2. WHEN a recruiter creates a candidate, THE Server SHALL validate that the Email is unique within the organization, that Name and Email are provided, and set GlobalStatus to Active by default.
3. WHEN a candidate with GlobalStatus of Active has no active InterviewJourneys (defined as any InterviewJourney with OverallStatus of Active or OnHold) and no changes to Name, Email, Phone, Location, or associated resume records for 90 days, THE Server SHALL set GlobalStatus to Expired via a scheduled background task that runs once every 24 hours.
4. IF a user sets a candidate to Ineligible status without providing an IneligibilityReason value of at least 1 non-whitespace character, THEN THE Server SHALL reject the request with a 400 Bad Request response indicating that IneligibilityReason is required.
5. WHEN a candidate is set to Deleted status, THE Server SHALL perform a logical deletion by populating the DeletedAt and DeletedBy AuditFields and excluding the candidate from search and matching results while retaining the record for audit purposes.
6. THE Server SHALL support searching candidates by name (partial, case-insensitive match), email (partial, case-insensitive match), and status (exact match), scoped to the authenticated user's organization, with paginated results returning a maximum of 50 records per page by default.
7. THE Server SHALL restrict GlobalStatus transitions to the following valid paths: Active to Interviewing, Active to Ineligible, Active to Deleted, Interviewing to Active, Interviewing to Ineligible, Interviewing to Deleted, Expired to Active, and Expired to Deleted.
8. IF a user attempts an invalid GlobalStatus transition, THEN THE Server SHALL reject the request with a 400 Bad Request response indicating the transition is not permitted.

### Requirement 2: Resume Management and Ingestion

**User Story:** As a recruiter, I want to upload and parse resumes, so that candidate skills and experience are automatically extracted and searchable.

#### Acceptance Criteria

1. THE Server SHALL store Resume entities with fields: ResumeID (UUID), CandidateID (FK, nullable at upload), OrganizationID (FK), StorageLocation, MimeType, FileName, FileSizeBytes, UploadedByUserID, IsPrimary flag, ParseStatus (Pending, Completed, Failed), parsed data fields (extracted name, email, phone, summary, job history, skills), and AuditFields.
2. WHEN a user uploads a resume file, THE Server SHALL accept only PDF, DOC, and DOCX formats with a maximum file size of 10 MB and store the file in the configured storage backend.
3. IF a user uploads a file with an unsupported format or exceeding 10 MB, THEN THE Server SHALL reject the upload with a 422 response indicating the validation failure reason.
4. THE Server SHALL support two storage backends configurable via the STORAGE_BACKEND environment variable: a local filesystem directory (for development) and an S3-compatible bucket (for cloud deployment).
5. WHEN a resume is uploaded, THE Server SHALL enqueue a background task to invoke the ResumeIngestionAgent with the storage URI and metadata.
6. WHEN the ResumeIngestionAgent returns parsed results, THE Server SHALL update or create Candidate, CandidateJobHistory, and CandidateSkill records, associate the resume, and set ParseStatus to Completed.
7. THE Server SHALL store CandidateJobHistory entities with fields: CandidateJobHistoryID (UUID), CandidateID (FK), OrganizationID (FK), CompanyName (max 200 characters), JobTitle (max 200 characters), StartDate (date), EndDate (nullable date), Description (max 2000 characters), IsCurrent (boolean), and AuditFields.
8. IF the ResumeIngestionAgent fails to parse a resume, THEN THE Server SHALL set ParseStatus to Failed, log the error with a correlation ID, and expose the resume record with Failed status so the uploading recruiter can provide candidate data via manual entry endpoints.
9. THE Server SHALL support listing resumes for a candidate with pagination and retrieving resume metadata and parsed fields.
10. THE Server SHALL restrict resume upload endpoints to users with Recruiter or Administrator roles, and restrict resume listing and retrieval endpoints to users with Recruiter, Administrator, or HiringManager roles, all scoped within the same organization.

### Requirement 3: Skills and Domain Taxonomy

**User Story:** As a recruiter, I want a standardized skill taxonomy, so that candidate skills and requisition requirements can be consistently compared.

#### Acceptance Criteria

1. THE Server SHALL store Domain entities with fields: DomainID (UUID), Name (unique, max 100 characters), Description (nullable), and AuditFields; and Skill entities with fields: SkillID (UUID), DomainID (FK), Name (unique within domain, max 100 characters), and AuditFields.
2. THE Server SHALL store CandidateSkill entities with fields: CandidateSkillID (UUID), CandidateID (FK), SkillID (FK), ProficiencyRank (integer 1 to 5), YearsOfExperience (integer 0 to 50), Source (enum: manual, parsed, inferred), and AuditFields.
3. THE Server SHALL store RequisitionRequiredSkill entities with fields: RequisitionRequiredSkillID (UUID), JobRequisitionID (FK), SkillID (FK), RequiredProficiencyRank (integer 1 to 5), Weight (integer 1 to 10 indicating relative priority among required skills for the requisition), and AuditFields.
4. WHEN the ResumeIngestionAgent extracts skills, THE Server SHALL match each extracted skill name against existing Skill entity names using case-insensitive comparison and link the matching Skill to the CandidateSkill record.
5. IF the ResumeIngestionAgent extracts a skill that does not match any existing Skill entity name, THEN THE Server SHALL create the CandidateSkill record with Source set to parsed and flag the skill for manual taxonomy review without blocking the ingestion process.

### Requirement 4: Job Profile and Job Posting Management

**User Story:** As a recruiter, I want to define job profiles and create job postings, so that open positions are clearly described with required skills and compensation details.

#### Acceptance Criteria

1. THE Server SHALL store JobProfile entities with fields: JobProfileID (UUID), OrganizationID (FK), Name, and AuditFields, with associated required and desired skills linked via the Skill taxonomy using a proficiency designation (required or desired) for each skill.
2. THE Server SHALL store JobPosting entities with fields: JobPostingID (UUID), OrganizationID (FK), job description, work locations (list of location strings), salary range minimum, salary range maximum, salary currency, sourcing channel, linked JobProfileID (FK), and AuditFields.
3. WHEN a recruiter creates a job posting without a linked JobProfile, THE Server SHALL reject the request with a 400 Bad Request response indicating that a JobProfile is required.
4. WHEN a recruiter creates a job posting with a valid linked JobProfile, THE Server SHALL store the job posting and associate it with the specified JobProfile.
5. THE Server SHALL support listing and filtering job postings by location, salary range (returning postings whose salary range overlaps with the requested min/max filter values), and sourcing channel, scoped to the authenticated user's organization.
6. IF a user without the Recruiter role attempts to create, update, or delete a JobProfile or JobPosting, THEN THE Server SHALL return a 403 Forbidden response.

### Requirement 5: Job Requisition Management

**User Story:** As a recruiter, I want to create and manage job requisitions, so that I can track open positions and their hiring pipeline.

#### Acceptance Criteria

1. THE Server SHALL store JobRequisition entities with fields: JobRequisitionID (UUID), OrganizationID (FK), ExternalRequisitionID (nullable, for future ATS integration), Title (max 200 characters), Department (max 100 characters), Location (max 200 characters), HiringManagerUserID (FK), Status (Open, OnHold, Closed, Cancelled), Description (max 5000 characters), linked JobProfile, and AuditFields.
2. WHEN a recruiter creates a requisition, THE Server SHALL set Status to Open by default and permit only the following status transitions: Open to OnHold, Open to Closed, Open to Cancelled, OnHold to Open, and OnHold to Cancelled.
3. WHEN a recruiter associates a candidate with a requisition, THE Server SHALL validate that the requisition Status is Open, that the candidate GlobalStatus is Active or Interviewing, and that the candidate is not already associated with the same requisition, before creating the association.
4. THE Server SHALL support configuring required skills on a requisition with proficiency levels (integer 1 to 5) and priority weights (integer 1 to 10, where higher values indicate greater relative priority).
5. THE Server SHALL support listing and filtering requisitions by hiring manager, status, department, and domain with pagination.
6. IF a recruiter attempts a status transition not in the permitted set, THEN THE Server SHALL reject the request with a 400 response indicating the invalid transition.

### Requirement 6: Data Privacy and Compliance

**User Story:** As a data protection officer, I want the system to support data subject rights and configurable retention policies, so that the organization complies with privacy regulations such as GDPR.

#### Acceptance Criteria

1. THE Server SHALL expose a POST /api/v1/portal/dsar endpoint accessible to authenticated candidates, which creates a Data Subject Access Request record containing the CandidateID, OrganizationID, RequestType (Access or Erasure), Status (Pending, Processing, Completed, Denied), RequestedAt (timestamp), CompletedAt (nullable timestamp), and AuditFields.
2. WHEN a candidate submits a DSAR with RequestType Access, THE Server SHALL compile all personal data associated with that CandidateID within the organization (candidate profile, job history, skills, questionnaire responses, availability slots, and interview journey metadata excluding encrypted records) and return it as a downloadable JSON document within 72 hours, updating the DSAR Status to Completed.
3. WHEN a candidate submits a DSAR with RequestType Erasure, THE Server SHALL hard-delete all personal data associated with that CandidateID (candidate profile, contact information, resume files, questionnaire answers, and availability slots) while preserving anonymized audit trail entries (replacing candidate identifiers with a placeholder value), and update the DSAR Status to Completed.
4. THE Server SHALL store OrganizationRetentionPolicy entities with fields: OrganizationRetentionPolicyID (UUID), OrganizationID (FK, unique), CandidateDataRetentionDays (integer, default 730), ResumeRetentionDays (integer, default 365), AuditLogRetentionDays (integer, default 2555), and AuditFields.
5. THE Server SHALL run a scheduled background task once every 24 hours that identifies and purges candidate data and resume files that have exceeded the organization's configured retention period, logging each purge action in the audit log.
6. THE Server SHALL restrict DSAR management endpoints (listing, status updates, denial with reason) to users with Administrator or HRManager roles.
7. IF an Administrator denies a DSAR, THE Server SHALL require a DenialReason (minimum 10 characters) and record the denial in the audit log.
