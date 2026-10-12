from django.urls import path
from dealers.views import (
    DealerListCreateView,
    DealerDetailView,
    DealerLoginView,
    DealerProvisionView,
    DealerResetPasswordView,
    DealerMeView,
    DealerLogoutView,
)

urlpatterns = [
    path("dealers/", DealerListCreateView.as_view(), name="dealer-list-create"),
    path("dealers/<int:pk>/", DealerDetailView.as_view(), name="dealer-detail"),
    path("auth/login/", DealerLoginView.as_view(), name="dealer-login"),
    path("auth/provision/", DealerProvisionView.as_view(), name="dealer-provision"),
    path("auth/reset-password/", DealerResetPasswordView.as_view(), name="dealer-reset-password"),
    path("auth/me/", DealerMeView.as_view(), name="dealer-me"),
    path("auth/logout/", DealerLogoutView.as_view(), name="dealer-logout"),
]
