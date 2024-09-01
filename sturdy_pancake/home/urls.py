from django.urls import path
from home.views import IndexView, DetailView, EditView, DeleteView

urlpatterns = [
    # 首页的路由
    path('', IndexView.as_view(), name='index'),

    # 详情视图的路由
    path('detail/', DetailView.as_view(), name='detail'),

    # 详情修改的路由
    path('edit/', EditView.as_view(), name='edit'),

    # 详情删除的路由
    path('delete/', DeleteView.as_view(), name='delete'),
    path('delete/<nid>', DeleteView.as_view(), name='delete'),
]