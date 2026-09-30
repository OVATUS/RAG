# booking_bmt/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("<int:pk>/reschedule/", views.reschedule_booking, name="booking_reschedule"),  # UPDATE
    
    path("<int:pk>/delete/", views.delete_booking, name="delete_booking"),              # DELETE 
]
   