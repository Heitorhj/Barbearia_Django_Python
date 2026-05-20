from django.urls import path
from . import views

urlpatterns = [
    path('', views.meus_agendamentos, name='meus_agendamentos'),
    path('agendar/', views.agendar_step1, name='agendar_step1'),
    path('agendar/data/', views.agendar_step2, name='agendar_step2'),
    path('agendar/horario/', views.agendar_step3, name='agendar_step3'),
    path('<int:pk>/', views.detalhe_agendamento, name='detalhe_agendamento'),
    path('<int:pk>/cancelar/', views.cancelar_agendamento, name='cancelar_agendamento'),
    path('<int:pk>/avaliar/', views.avaliar_agendamento, name='avaliar_agendamento'),
    path('barbeiro/dashboard/', views.dashboard_barbeiro, name='dashboard_barbeiro'),
]
