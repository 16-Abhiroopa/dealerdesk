from rest_framework.views import APIView
from rest_framework.response import Response
from core.exceptions import ValidationAppError
from dealers.models import Dealer
from assistant.models import ChatSession
from assistant.agent import run_assistant_turn


def get_authenticated_dealer(request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return getattr(user, "dealer", None)
    return None


class ChatAssistantView(APIView):
    def post(self, request):
        data = request.data
        if not isinstance(data, dict):
            raise ValidationAppError("Request body must be a JSON object.")

        auth_dealer = get_authenticated_dealer(request)
        if auth_dealer:
            requested_dealer_id = data.get("dealer_id")
            if requested_dealer_id is not None:
                try:
                    requested_dealer_id = int(requested_dealer_id)
                except (ValueError, TypeError):
                    pass
            if requested_dealer_id and requested_dealer_id != auth_dealer.id:
                raise ValidationAppError("You cannot chat as another dealer.")
            dealer_id = auth_dealer.id
        else:
            dealer_id = data.get("dealer_id")
            if dealer_id is not None:
                try:
                    dealer_id = int(dealer_id)
                except (ValueError, TypeError):
                    pass

        session_id = data.get("session_id")
        if not session_id or session_id == "auto":
            session_id = f"dealer-{dealer_id}-chat" if dealer_id else "default-session"

        message = data.get("message")

        result = run_assistant_turn(
            session_id=session_id,
            dealer_id=dealer_id,
            user_message=message,
        )

        return Response(result)


class ChatSessionHistoryView(APIView):
    """Retrieve message history for a dealer's session."""

    def get(self, request):
        auth_dealer = get_authenticated_dealer(request)
        if auth_dealer:
            dealer = auth_dealer
        else:
            dealer_id = request.query_params.get("dealer_id")
            if not dealer_id:
                raise ValidationAppError("dealer_id query param is required.")
            try:
                dealer = Dealer.objects.get(id=int(dealer_id))
            except (ValueError, Dealer.DoesNotExist):
                raise ValidationAppError("Valid dealer not found.")

        session_id = request.query_params.get("session_id") or f"dealer-{dealer.id}-chat"
        session = ChatSession.objects.filter(session_id=session_id, dealer=dealer).first()

        messages = []
        if session:
            for msg in session.messages.order_by("created_at")[:50]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content,
                    "tool_calls": msg.tool_calls,
                    "created_at": msg.created_at.isoformat(),
                })

        return Response({
            "session_id": session_id,
            "dealer_id": dealer.id,
            "messages": messages,
        })
