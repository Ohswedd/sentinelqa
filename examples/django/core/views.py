from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import ProjectForm
from core.models import Project


@login_required
def projects_list(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            return redirect("projects")
    else:
        form = ProjectForm()
    projects = Project.objects.filter(owner=request.user).order_by("id")
    return render(request, "projects/list.html", {"projects": projects, "form": form})


@login_required
def project_delete(request: HttpRequest, project_id: int) -> HttpResponse:
    project = get_object_or_404(Project, pk=project_id, owner=request.user)
    if request.method == "POST":
        project.delete()
        return redirect("projects")
    return render(request, "projects/delete.html", {"project": project})
