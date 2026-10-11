from rest_framework.views import APIView
from rest_framework.response import Response
from core.exceptions import ValidationAppError
from assistant.agent import run_assistant_turn


class ChatAssistantView(APIView):
    def post(self, request):
        data = request.data
        if not isinstance(data, dict):
            raise ValidationAppError("Request body must be a JSON object.")

        session_id = data.get("session_id")
        dealer_id = data.get("dealer_id")
        message = data.get("message")

        result = run_assistant_turn(
            session_id=session_id,
            dealer_id=dealer_id,
            user_message=message,
        )

        return Response(result)
