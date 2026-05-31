# TalentKru.ai Product Overview

## What is TalentKru.ai?

TalentKru.ai is a talent acquisition and recruitment platform that helps organizations manage the complete candidate lifecycle—from job posting through hiring decisions. The platform combines AI-powered matching, resume ingestion, and interview management to streamline recruitment workflows.

## Core Features

- **Candidate Management**: Track candidates through the recruitment pipeline with lifecycle states and expiry policies
- **Resume Processing**: Ingest and parse resumes with AI-powered extraction and skill matching
- **Job Matching**: AI-driven candidate-to-job matching based on skills and qualifications
- **Interview Management**: Schedule and manage interviews with feedback collection
- **RBAC & Multi-Tenancy**: Role-based access control with organization-level isolation
- **Privacy & Compliance**: Data retention policies, DSAR (Data Subject Access Request) support, and audit logging
- **Reporting**: Interview leaderboards and recruitment analytics

## Key Concepts

- **Organizations**: Multi-tenant isolation—each organization has its own data, users, and configurations
- **Candidates**: Individuals in the recruitment pipeline with lifecycle states (active, expired, archived)
- **Requisitions**: Job openings that candidates are matched against
- **Journeys**: Candidate progression through interview stages
- **Resumes**: Uploaded documents parsed for skills and experience
- **Skills**: Extracted from resumes and used for matching

## Architecture Style

- **Backend**: FastAPI-based REST API with async/await patterns
- **Database**: PostgreSQL with pgvector for semantic search
- **Async Processing**: Background schedulers for expiry checks and retention purges
- **Event-Driven**: Domain events for audit trails and system integration
- **AI Integration**: Gemini API for resume parsing, matching, and feedback generation

## Development Status

The platform is actively developed with multiple feature waves completed. Recent work includes identity/access management, candidate lifecycle automation, and privacy compliance features.
