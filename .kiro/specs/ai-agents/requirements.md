# Requirements Document

## Introduction

This is the AI Agents module of TalentKru.ai Server, covering the AI-powered agents for resume ingestion, candidate-requisition matching, questionnaire orchestration, and behavioral feedback generation. These agents automate key recruiting workflows—parsing resumes into structured candidate data, ranking candidates against open requisitions using semantic similarity, assigning questionnaires when candidates join requisitions, and generating structured behavioral interview feedback from transcripts.

Key architectural decisions relevant to this module:
- FastAPI background tasks for async processing (resume ingestion, matching, AI feedback).
- pgvector for semantic search and embeddings (candidate and requisition vector representations).
- Manual fallback paths for all AI features (recruiters and interviewers can always perform actions manually if an agent fails).
- Internal agent callback endpoints authenticated via X-Agent-API-Key header.

## Glossary

- **Server**: The TalentKru.ai FastAPI backend application.
- **Organization**: A client tenant in the system; all data is scoped to an organization.
- **Candidate**: A job applicant tracked within an organization's recruiting pipeline.
- **ResumeIngestionAgent**: An AI agent that parses resumes, extracts skills, and generates embeddings.
- **MatchingAgent**: An AI agent that computes semantic similarity between candidates and requisitions.
- **QuestionnaireOrchestratorAgent**: An AI agent that manages questionnaire assignment for candidates.
- **BehavioralFeedbackAgent**: An AI agent that generates structured behavioral interview feedback from transcripts.
- **AuditFields**: Standard fields on all entities: CreatedAt, UpdatedAt, DeletedAt, CreatedBy, UpdatedBy, DeletedBy.

## Requirements

### Requirement 1: AI Resume Ingestion Agent

**User Story:** As a recruiter, I want resumes to be automatically parsed and skills extracted, so that candidate profiles are populated without manual data entry.

#### Acceptance Criteria

1. THE Server SHALL expose an internal endpoint (POST /internal/agents/resume-ingestion-callback) for the ResumeIngestionAgent to post parsed results, authenticated via the X-Agent-API-Key header.
2. WHEN the ResumeIngestionAgent is invoked, THE Server SHALL provide the resume storage URI and associated metadata including CandidateID, OrganizationID, ResumeID, MimeType, and FileName, and SHALL include the X-Correlation-ID header for distributed tracing.
3. WHEN the ResumeIngestionAgent returns results, THE Server SHALL accept payloads with any extractable candidate information (including name, email, phone, job history, skills, education, or certifications) and map the payload to Candidate, CandidateJobHistory, CandidateSkill, and Resume entities.
4. IF the ResumeIngestionAgent callback payload fails validation, THEN THE Server SHALL reject the request with a 422 response and log the validation failure with the correlation ID.
5. WHEN the ResumeIngestionAgent returns candidate contact information (name, email, phone), THE Server SHALL encrypt these fields using AES-256-GCM before persisting to the database, and SHALL populate CreatedBy with the agent's system identity and UpdatedBy with the current timestamp on all created entities.
6. WHEN the ResumeIngestionAgent results are successfully mapped to entities, THE Server SHALL generate vector embeddings for the parsed resume text and store them using pgvector for semantic search.
7. IF the ResumeIngestionAgent encounters an error, THEN THE Server SHALL log the failure with correlation ID and notify the uploading recruiter, and the Server SHALL allow the recruiter to manually create or update candidate data via standard candidate endpoints.
8. THE Server SHALL enforce rate limiting on the /internal/agents/resume-ingestion-callback endpoint with a default limit of 100 requests per minute per agent identity.

### Requirement 2: AI Matching Agent

**User Story:** As a recruiter, I want candidates to be automatically ranked against requisitions, so that the best-fit candidates surface quickly.

#### Acceptance Criteria

1. THE Server SHALL invoke the MatchingAgent as a background task scoped to the requisition's organization both automatically when a candidate is associated with a requisition and when a user manually triggers matching for a requisition via the matching endpoint, and SHALL include the X-Correlation-ID header for distributed tracing.
2. THE MatchingAgent SHALL compute embeddings for the requisition using description, skills, and domain.
3. THE MatchingAgent SHALL run vector search over candidate embeddings within the same organization, excluding candidates with GlobalStatus of Ineligible, Expired, or Deleted, and excluding candidates WHERE deleted_at IS NOT NULL, and return a maximum of 100 candidate matches.
4. THE MatchingAgent SHALL combine semantic similarity with structured skill matching to compute a MatchScore on a numeric scale of 0.00 to 100.00.
5. THE MatchingAgent SHALL generate a MatchExplanation in natural language text of no more than 1000 characters for each match.
6. THE Server SHALL persist CandidateRequisitionMatch records with MatchScore, MatchExplanation, and a timestamp indicating when the match was computed.
7. THE Server SHALL expose a paginated endpoint to retrieve matches for a requisition sorted by MatchScore in descending order.
8. IF the MatchingAgent fails, THEN THE Server SHALL log the error with a correlation ID and allow recruiters to manually associate candidates with requisitions even if error logging fails.
9. THE Server SHALL enforce rate limiting on the /internal/agents/matching-callback endpoint with a default limit of 100 requests per minute per agent identity.

### Requirement 3: AI Questionnaire Orchestrator Agent

**User Story:** As a recruiter, I want questionnaires to be automatically assigned when candidates join requisitions, so that no assessment steps are missed.

#### Acceptance Criteria

1. WHEN a candidate is associated with a requisition, THE Server SHALL invoke the QuestionnaireOrchestratorAgent as a background task to retrieve the questionnaires linked to that requisition via JobRequisitionQuestionnaire records, and SHALL include the X-Correlation-ID header for distributed tracing.
2. WHEN the QuestionnaireOrchestratorAgent processes a candidate-requisition association, THE QuestionnaireOrchestratorAgent SHALL query existing CandidateQuestionnaireResponse records matching the same CandidateID and QuestionnaireID and create a new CandidateQuestionnaireResponse record with Status set to Draft only for questionnaires that have no existing response record for that candidate.
3. IF the requisition has no linked questionnaires, THEN THE QuestionnaireOrchestratorAgent SHALL complete without creating any records and log an informational message.
4. IF the QuestionnaireOrchestratorAgent fails, THEN THE Server SHALL log the error with a correlation ID and expose a manual questionnaire assignment endpoint accessible to users with the Recruiter role.
5. WHEN the QuestionnaireOrchestratorAgent completes successfully, THE Server SHALL publish a domain event 'questionnaire_assigned' with the CandidateID, JobRequisitionID, and count of newly created CandidateQuestionnaireResponse records, and SHALL record the assignment event in the audit log.
6. THE Server SHALL enforce rate limiting on the /internal/agents/questionnaire-orchestrator-callback endpoint with a default limit of 100 requests per minute per agent identity.

### Requirement 4: AI Behavioral Feedback Agent

**User Story:** As an interviewer, I want AI-generated behavioral feedback drafts from interview transcripts, so that I can provide structured assessments more efficiently.

#### Acceptance Criteria

1. WHEN an interviewer submits a transcript for an InterviewSlot, THE Server SHALL validate that the transcript does not exceed 50,000 characters before any other processing, and IF the limit is exceeded, THE Server SHALL reject the request with a validation error response.
2. WHEN a valid transcript is submitted, THE Server SHALL invoke the BehavioralFeedbackAgent as a background task with the transcript text and contextual metadata including the interview type, job requisition title, and required competencies from the linked JobProfile, and SHALL include the X-Correlation-ID header for distributed tracing.
3. THE BehavioralFeedbackAgent SHALL generate structured behavioral feedback including competency ratings on the integer scale of 1 to 5 and a narrative summary of no more than 2000 characters. THE Server SHALL allow the interviewer to expand the narrative up to 5000 characters total before final submission.
4. WHEN the BehavioralFeedbackAgent returns results, THE Server SHALL persist the generated feedback as a BehavioralFeedbackDraft linked to the InterviewSlot, replacing any previously generated draft for that slot.
5. WHEN a user who is not the assigned interviewer for the slot attempts to trigger draft generation, THE Server SHALL reject the request with a 403 Forbidden response. IF the InterviewSlot is not in Scheduled status or the assigned interviewer is not found, THE Server SHALL reject the request with a 400 Bad Request response.
6. IF the BehavioralFeedbackAgent fails, THEN THE Server SHALL log the error with the correlation ID and InterviewSlotID, and retain the ability for the interviewer to submit feedback manually without AI assistance.
7. THE Server SHALL enforce rate limiting on the /internal/agents/behavioral-feedback-callback endpoint with a default limit of 100 requests per minute per agent identity.
