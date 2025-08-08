from django.urls import path

from . import views

app_name = 'trading'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('bots/', views.bot_list, name='bot_list'),
    path('bots/<int:bot_id>/', views.bot_detail, name='bot_detail'),
    path('trades/', views.trade_list, name='trade_list'),
    path('runs/', views.run_list, name='run_list'),
]
