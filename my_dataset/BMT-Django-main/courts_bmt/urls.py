from django.urls import path
from courts_bmt import views

urlpatterns = [
    path('list/', views.court_list, name='court_list'),
    path('<pk>/', views.court_detail, name='court_detail'),
    path('<int:pk>/book/', views.create_booking, name='create_booking'),
]
