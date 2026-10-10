from rest_framework.views import APIView
from rest_framework.response import Response


class ChatAssistantView(APIView):
    def post(self, request):
        return Response({
            "reply": "Assistant initialized.",
            "cited_skus": [],
            "tool_calls": [],
            "actions": [],
        })
