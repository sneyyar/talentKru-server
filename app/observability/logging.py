import logging
import structlog
from app.observability.middleware import correlation_id_var


def add_correlation_id(logger, method, event_dict):
    event_dict["correlation_id"] = correlation_id_var.get("")
    return event_dict


# Configure structlog with stdlib integration
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_correlation_id,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Configure standard logging to output to console
logging.basicConfig(
    format="%(message)s",
    level=logging.INFO,
)


def get_logger(name: str):
    return structlog.get_logger(name)
