from enum import Enum

class IncidentCategory(str, Enum):
    WAREHOUSE = "warehouse"
    REVERSE_LOGISTICS = "reverse_logistics"
    LAST_MILE = "last_mile"
    CUSTOMER_EXPERIENCE = "customer_experience"

class IncidentStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISCARDED = "discarded"

class IncidentOrigin(str, Enum):
    CUSTOMER = "customer"
    BRANCH = "branch"
    INTERNAL = "internal"
