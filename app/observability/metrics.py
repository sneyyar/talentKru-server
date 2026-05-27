from prometheus_client import Counter, Histogram, Gauge

resumes_parsed_total = Counter(
    "talentkru_resumes_parsed_total",
    "Total number of resumes successfully parsed",
)
match_computation_duration_ms = Histogram(
    "talentkru_match_computation_duration_ms",
    "Match computation duration in milliseconds",
    buckets=[50, 100, 250, 500, 1000, 2500, 5000],
)
matches_per_requisition_total = Counter(
    "talentkru_matches_per_requisition_total",
    "Total match computations per requisition",
    labelnames=["requisition_id"],
)
questionnaire_completions_total = Counter(
    "talentkru_questionnaire_completions_total",
    "Total questionnaire submission events",
)
ai_agent_errors_total = Counter(
    "talentkru_ai_agent_errors_total",
    "Total AI agent errors by agent name",
    labelnames=["agent_name"],
)
interview_volume = Gauge(
    "talentkru_interview_volume",
    "Current interview volume by stage, type, and organization",
    labelnames=["stage", "interview_type", "organization_id"],
)
no_show_rate = Gauge(
    "talentkru_no_show_rate",
    "No-show rate per organization",
    labelnames=["organization_id"],
)
