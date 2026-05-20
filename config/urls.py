from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views 
from agendamentos import views as ag_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', ag_views.home, name='home'),
    path('registro/', ag_views.registro, name='registro'),
    path('servicos/', ag_views.lista_servicos, name='lista_servicos'),
    path('agendamentos/', include('agendamentos.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='agendamentos/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
