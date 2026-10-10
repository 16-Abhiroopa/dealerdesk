from decimal import Decimal
from rest_framework import serializers
from core.exceptions import DuplicateAppError, ValidationAppError
from core.utils import format_money
from dealers.models import Dealer


class DealerSerializer(serializers.ModelSerializer):
    credit_limit = serializers.SerializerMethodField()

    class Meta:
        model = Dealer
        fields = [
            "id",
            "dealer_code",
            "name",
            "city",
            "phone",
            "email",
            "gstin",
            "credit_limit",
        ]

    def get_credit_limit(self, obj) -> str:
        return format_money(obj.credit_limit)


class DealerCreateSerializer(serializers.ModelSerializer):
    dealer_code = serializers.CharField(required=True, validators=[])
    name = serializers.CharField(required=True)
    credit_limit = serializers.CharField(required=False, default="0.00")

    class Meta:
        model = Dealer
        fields = [
            "dealer_code",
            "name",
            "city",
            "phone",
            "email",
            "gstin",
            "credit_limit",
        ]

    def validate_dealer_code(self, value):
        code = value.strip()
        if not code:
            raise ValidationAppError("dealer_code cannot be empty.")
        if Dealer.objects.filter(dealer_code=code).exists():
            raise DuplicateAppError(f"Dealer with code '{code}' already exists.")
        return code

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise ValidationAppError("name cannot be empty.")
        return name

    def validate_credit_limit(self, value):
        try:
            return Decimal(str(value))
        except Exception:
            raise ValidationAppError("credit_limit must be a valid number.")
