from django.urls import path

from core import views

urlpatterns = [
    path("", views.projects_list, name="projects"),
    path("<int:project_id>/delete/", views.project_delete, name="project-delete"),
]
