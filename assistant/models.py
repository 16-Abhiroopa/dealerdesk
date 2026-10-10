from django.db import models
from dealers.models import Dealer


class ChatSession(models.Model):
    session_id = models.CharField(max_length=128, primary_key=True)
    dealer = models.ForeignKey(Dealer, on_delete=models.PROTECT, related_name="chat_sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session {self.session_id} (Dealer {self.dealer_id})"


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "user"),
        ("assistant", "assistant"),
        ("system", "system"),
        ("tool", "tool"),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField(blank=True, default="")
    tool_calls = models.JSONField(null=True, blank=True)
    tool_call_id = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.session_id} [{self.role}]: {self.content[:40]}"
