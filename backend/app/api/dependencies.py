from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.ai.langgraph_intent import HybridIntentGraph
from app.ai.providers.base import LLMProvider
from app.ai.providers.mock_provider import MockLLMProvider
from app.ai.providers.openai_provider import OpenAILLMProvider
from app.core.settings import get_settings
from app.core.errors import UnauthorizedError
from app.core.errors import ForbiddenError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.faq_repository import FAQRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.refund_repository import RefundRepository
from app.repositories.user_repository import UserRepository
from app.services.account_order_service import AccountOrderService
from app.services.auth_service import AuthService
from app.services.intent_faq_service import IntentFAQService
from app.services.order_placement_service import OrderPlacementService
from app.services.notification_service import NotificationService
from app.services.refund_service import RefundService

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_auth_service(user_repository: UserRepository = Depends(get_user_repository)) -> AuthService:
    return AuthService(user_repository)


def get_order_repository(db: Session = Depends(get_db)) -> OrderRepository:
    return OrderRepository(db)


def get_account_order_service(
    order_repository: OrderRepository = Depends(get_order_repository),
    user_repository: UserRepository = Depends(get_user_repository),
) -> AccountOrderService:
    return AccountOrderService(order_repository, user_repository)


def get_order_placement_service(
    order_repository: OrderRepository = Depends(get_order_repository),
) -> OrderPlacementService:
    return OrderPlacementService(order_repository)


def get_notification_service(
    account_order_service: AccountOrderService = Depends(get_account_order_service),
) -> NotificationService:
    return NotificationService(account_order_service)


def get_refund_repository(db: Session = Depends(get_db)) -> RefundRepository:
    return RefundRepository(db)


def get_refund_service(
    order_repository: OrderRepository = Depends(get_order_repository),
    refund_repository: RefundRepository = Depends(get_refund_repository),
) -> RefundService:
    return RefundService(order_repository=order_repository, refund_repository=refund_repository)


def get_faq_repository() -> FAQRepository:
    settings = get_settings()
    return FAQRepository(faq_chunks_path=settings.faq_chunks_path)


def get_conversation_repository(db: Session = Depends(get_db)) -> ConversationRepository:
    return ConversationRepository(db)


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return OpenAILLMProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=settings.llm_temperature,
        )
    return MockLLMProvider()


def get_hybrid_intent_graph(llm_provider: LLMProvider = Depends(get_llm_provider)) -> HybridIntentGraph:
    settings = get_settings()
    return HybridIntentGraph(
        llm_provider=llm_provider,
        rule_confidence_threshold=settings.intent_rule_confidence_threshold,
    )


def get_intent_faq_service(
    faq_repository: FAQRepository = Depends(get_faq_repository),
    conversation_repository: ConversationRepository = Depends(get_conversation_repository),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    intent_graph: HybridIntentGraph = Depends(get_hybrid_intent_graph),
) -> IntentFAQService:
    settings = get_settings()
    return IntentFAQService(
        faq_repository=faq_repository,
        conversation_repository=conversation_repository,
        llm_provider=llm_provider,
        intent_graph=intent_graph,
        escalation_confidence_threshold=settings.intent_escalation_confidence_threshold,
        llm_faq_synthesis_enabled=settings.llm_faq_synthesis_enabled,
        retrieval_top_k=settings.faq_retrieval_top_k,
        max_context_chunks=settings.faq_max_context_chunks,
        max_context_chars=settings.faq_max_context_chars,
        min_chunk_score=settings.faq_min_chunk_score,
        relative_score_floor=settings.faq_relative_score_floor,
        synthesis_history_messages=settings.faq_synthesis_history_messages,
        synthesis_history_chars=settings.faq_synthesis_history_chars,
    )


def _extract_token_from_request(
    request: Request, credentials: HTTPAuthorizationCredentials | None
) -> str:
    if credentials is not None:
        return credentials.credentials

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    raise UnauthorizedError("Missing authentication token")


def _extract_cookie_token_from_request(request: Request) -> str:
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    raise UnauthorizedError("Missing authentication token")


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    token = _extract_token_from_request(request, credentials)
    payload = decode_access_token(token)

    subject = payload.get("sub")
    if subject is None:
        raise UnauthorizedError("Invalid token subject")

    user = user_repository.get_by_id(int(subject))
    if user is None:
        raise UnauthorizedError("User not found")
    return user


def get_current_user_from_cookie(
    request: Request,
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    token = _extract_cookie_token_from_request(request)
    payload = decode_access_token(token)

    subject = payload.get("sub")
    if subject is None:
        raise UnauthorizedError("Invalid token subject")

    user = user_repository.get_by_id(int(subject))
    if user is None:
        raise UnauthorizedError("User not found")
    return user


def get_current_guest_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_guest:
        raise UnauthorizedError("Guest account required")
    return current_user


def require_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.is_guest or not current_user.is_admin:
        raise ForbiddenError("Admin access required")
    return current_user
