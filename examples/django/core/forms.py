from django import forms

from core.models import Project


class ProjectForm(forms.ModelForm[Project]):
    class Meta:
        model = Project
        fields = ("name", "description")
