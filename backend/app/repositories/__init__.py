from app.repositories.customer_repository import CustomerRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.return_repository import ReturnRepository
from app.repositories.fraud_repository import FraudScoreRepository, FraudCaseRepository, AnalystFeedbackRepository
from app.repositories.dashboard_repository import DashboardRepository

__all__ = [
    "CustomerRepository",
    "OrderRepository",
    "ReturnRepository",
    "FraudScoreRepository",
    "FraudCaseRepository",
    "AnalystFeedbackRepository",
    "DashboardRepository",
]
