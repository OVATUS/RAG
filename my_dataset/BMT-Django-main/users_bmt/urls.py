# users_bmt/urls.py
from django.urls import path
from users_bmt import views
from booking_bmt.views import cancel_booking_view

urlpatterns = [ 
    path('register/', views.register, name='register'),
    path("profile/", views.profile_view, name="profile"),
    path("bookings/", views.booking_history_view, name="booking_history"),
    path("bookings/<int:booking_id>/cancel/", cancel_booking_view, name="cancel_booking"),
    path("deactivate/", views.deactivate_confirm_view, name="deactivate_confirm"),
    path("deactivate/submit/", views.deactivate_me_view, name="deactivate_me"),
    path("profile/edit/", views.edit_profile, name="edit_profile"),

]
