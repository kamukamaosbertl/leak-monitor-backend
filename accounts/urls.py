from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

# Import authentication views
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    MeView,
    GoogleLoginView,
    ProfileSetupView,
    DeleteAccountView,# 🔥 NEW
)

urlpatterns = [
    # ───────────────────────────────────────────
    # 📝 REGISTER
    # ───────────────────────────────────────────
    path('register/', RegisterView.as_view(), name='auth-register'),

    # ───────────────────────────────────────────
    # 🔑 LOGIN
    # ───────────────────────────────────────────
    path('login/', LoginView.as_view(), name='auth-login'),

    # ───────────────────────────────────────────
    # 🚪 LOGOUT
    # ───────────────────────────────────────────
    path('logout/', LogoutView.as_view(), name='auth-logout'),

    # ───────────────────────────────────────────
    # 👤 CURRENT USER
    # ───────────────────────────────────────────
    path('me/', MeView.as_view(), name='auth-me'),

    # ───────────────────────────────────────────
    # 🔄 TOKEN REFRESH
    # ───────────────────────────────────────────
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # ───────────────────────────────────────────
    # 🔐 GOOGLE LOGIN
    # ───────────────────────────────────────────
    path('google/', GoogleLoginView.as_view(), name='google-login'),

    # ───────────────────────────────────────────
    # 🛠 PROFILE SETUP
    # ───────────────────────────────────────────
    path('profile/setup/', ProfileSetupView.as_view(), name='profile-setup'),
    
    # ───────────────────────────────────────────
    #delete  routes
    #
   path('delete-account/', DeleteAccountView.as_view()),
]