from decimal import Decimal
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from core.exceptions import NotFoundAppError, ValidationAppError
from core.pagination import StandardResultsSetPagination
from core.utils import format_money
from dealers.models import Dealer
from dealers.serializers import DealerSerializer, DealerCreateSerializer
from orders.models import Order


def get_dealer_financial_info(dealer: Dealer):
    """Calculate outstanding orders and remaining available credit for a dealer."""
    active_orders = Order.objects.filter(
        dealer=dealer,
        status__in=["CONFIRMED", "DISPATCHED"],
    )
    outstanding = sum((o.grand_total for o in active_orders), Decimal("0.00"))
    if dealer.credit_limit <= Decimal("0.00"):
        available_credit = Decimal("999999999.00")
    else:
        available_credit = max(Decimal("0.00"), dealer.credit_limit - outstanding)
    return {
        "credit_limit": format_money(dealer.credit_limit),
        "outstanding_orders": format_money(outstanding),
        "available_credit": format_money(available_credit),
    }


class DealerListCreateView(APIView):
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Dealer.objects.all()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = DealerSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = DealerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dealer = serializer.save()
        return Response(DealerSerializer(dealer).data, status=status.HTTP_201_CREATED)


class DealerDetailView(APIView):
    def get(self, request, pk: int):
        try:
            dealer = Dealer.objects.get(pk=pk)
        except Dealer.DoesNotExist:
            raise NotFoundAppError(f"Dealer with id {pk} not found.")
        data = DealerSerializer(dealer).data
        data.update(get_dealer_financial_info(dealer))
        return Response(data)


class DealerLoginView(APIView):
    """Secure login endpoint for dealers using username/dealer_code and password."""

    def post(self, request):
        data = request.data or {}
        ident = (data.get("username") or data.get("dealer_code") or "").strip()
        password = (data.get("password") or "").strip()

        if not ident or not password:
            raise ValidationAppError("Dealer code/username and password are required.")

        # Match dealer by dealer_code, user username, or user email
        dealer = (
            Dealer.objects.filter(dealer_code__iexact=ident).first()
            or Dealer.objects.filter(user__username__iexact=ident).first()
            or Dealer.objects.filter(user__email__iexact=ident).first()
        )

        if not dealer or not dealer.user:
            # Check if user exists directly
            user = authenticate(username=ident.lower(), password=password)
            if user and hasattr(user, "dealer"):
                dealer = user.dealer
            else:
                raise ValidationAppError("Invalid dealer credentials or account not yet provisioned.")
        else:
            if not dealer.user.check_password(password):
                raise ValidationAppError("Invalid password for dealer account.")
            user = dealer.user

        token, _ = Token.objects.get_or_create(user=user)
        financials = get_dealer_financial_info(dealer)

        response_data = {
            "token": token.key,
            "dealer": DealerSerializer(dealer).data,
            **financials,
        }
        return Response(response_data, status=status.HTTP_200_OK)


class DealerProvisionView(APIView):
    """Secure provisioning flow for dealers to activate their account or set initial password.
    
    Verifies dealer identity against recorded dealer_code and registered email/gstin.
    """

    def post(self, request):
        data = request.data or {}
        dealer_code = (data.get("dealer_code") or "").strip()
        email = (data.get("email") or "").strip().lower()
        gstin = (data.get("gstin") or "").strip().upper()
        password = (data.get("password") or "").strip()

        if not dealer_code:
            raise ValidationAppError("dealer_code is required for provisioning.")
        if not password or len(password) < 6:
            raise ValidationAppError("A secure password of at least 6 characters is required.")
        if not email and not gstin:
            raise ValidationAppError("Either registered email or GSTIN is required to verify dealer identity.")

        dealer = Dealer.objects.filter(dealer_code__iexact=dealer_code).first()
        if not dealer:
            raise NotFoundAppError(f"Dealer with code '{dealer_code}' not found in registry.")

        # Verification check
        matched = False
        if email and dealer.email.lower() == email:
            matched = True
        if gstin and dealer.gstin.upper() == gstin:
            matched = True

        if not matched:
            raise ValidationAppError("Dealer verification failed: provided email or GSTIN does not match records.")

        if dealer.user:
            user = dealer.user
            user.set_password(password)
            user.save()
        else:
            username = dealer.dealer_code.lower()
            user, _ = User.objects.get_or_create(username=username, defaults={"email": dealer.email})
            user.set_password(password)
            user.save()
            dealer.user = user
            dealer.save(update_fields=["user"])

        token, _ = Token.objects.get_or_create(user=user)
        financials = get_dealer_financial_info(dealer)

        return Response(
            {
                "message": f"Dealer account for {dealer.name} ({dealer.dealer_code}) successfully provisioned.",
                "token": token.key,
                "dealer": DealerSerializer(dealer).data,
                **financials,
            },
            status=status.HTTP_200_OK,
        )


class DealerResetPasswordView(APIView):
    """Password reset flow verifying dealer identity."""

    def post(self, request):
        data = request.data or {}
        dealer_code = (data.get("dealer_code") or "").strip()
        email = (data.get("email") or "").strip().lower()
        new_password = (data.get("new_password") or "").strip()

        if not dealer_code or not email or not new_password:
            raise ValidationAppError("dealer_code, email, and new_password are required.")
        if len(new_password) < 6:
            raise ValidationAppError("New password must be at least 6 characters.")

        dealer = Dealer.objects.filter(dealer_code__iexact=dealer_code).first()
        if not dealer:
            raise NotFoundAppError(f"Dealer '{dealer_code}' not found.")

        if dealer.email.lower() != email:
            raise ValidationAppError("Email does not match dealer record.")

        if not dealer.user:
            user, _ = User.objects.get_or_create(username=dealer.dealer_code.lower(), defaults={"email": dealer.email})
            dealer.user = user
            dealer.save(update_fields=["user"])
        else:
            user = dealer.user

        user.set_password(new_password)
        user.save()

        # Rotate token
        Token.objects.filter(user=user).delete()
        new_token = Token.objects.create(user=user)

        return Response(
            {
                "message": "Password reset successfully.",
                "token": new_token.key,
                "dealer": DealerSerializer(dealer).data,
            },
            status=status.HTTP_200_OK,
        )


class DealerMeView(APIView):
    """Retrieve profile and credit information for the currently authenticated dealer."""

    def get(self, request):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return Response({"authenticated": False, "dealer": None}, status=status.HTTP_200_OK)

        dealer = getattr(user, "dealer", None)
        if not dealer:
            return Response({"authenticated": True, "dealer": None, "is_staff": getattr(user, "is_staff", False)}, status=status.HTTP_200_OK)

        data = DealerSerializer(dealer).data
        financials = get_dealer_financial_info(dealer)
        return Response(
            {
                "authenticated": True,
                "dealer": data,
                **financials,
            },
            status=status.HTTP_200_OK,
        )


class DealerLogoutView(APIView):
    """Log out dealer and invalidate token."""

    def post(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            Token.objects.filter(user=user).delete()
        return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)

