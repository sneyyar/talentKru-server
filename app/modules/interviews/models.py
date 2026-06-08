"""
Interview ORM model stubs.

InterviewSlot, InterviewFeedback, and InterviewerPreference have been moved to their respective modules:
- InterviewSlot: app.modules.slots.models
- InterviewFeedback: app.modules.feedback.models
- InterviewerPreference: app.modules.slots.models

They inherit Base, AuditMixin, and VersionMixin to satisfy Requirements 7.1
and 7.5 (optimistic locking on all mutable entities).
"""
