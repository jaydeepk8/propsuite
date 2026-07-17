"""Expense CRUD views."""

from decimal import Decimal

from django.contrib import messages
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.mixins import OwnerRequiredMixin
from .filters import ExpenseFilter
from .forms import ExpenseForm
from .models import Expense

_MONEY = DecimalField(max_digits=12, decimal_places=2)


class ExpenseListView(OwnerRequiredMixin, ListView):
    model = Expense
    template_name = "expenses/expense_list.html"
    context_object_name = "expenses"
    paginate_by = 15
    extra_context = {"active_nav": "expenses"}

    def get_base_queryset(self):
        return Expense.objects.for_user(self.request.user).select_related("property")

    def get_queryset(self):
        self.filterset = ExpenseFilter(
            self.request.GET, queryset=self.get_base_queryset(), owner=self.request.user)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = self.filterset
        # Totals over the *filtered* set.
        qs = self.filterset.qs
        ctx["total"] = qs.aggregate(
            t=Coalesce(Sum("amount", output_field=_MONEY), Decimal("0"), output_field=_MONEY))["t"]
        by_cat = (qs.values("category")
                  .annotate(total=Coalesce(Sum("amount", output_field=_MONEY),
                                           Decimal("0"), output_field=_MONEY))
                  .order_by("-total"))
        labels = dict(Expense.Category.choices)
        ctx["by_category"] = [(labels[r["category"]], r["total"]) for r in by_cat]
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class ExpenseFormMixin:
    model = Expense
    form_class = ExpenseForm
    template_name = "expenses/expense_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["owner"] = self.request.user
        return kwargs


class ExpenseCreateView(OwnerRequiredMixin, ExpenseFormMixin, CreateView):
    extra_context = {"active_nav": "expenses", "form_title": "Log Expense"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Expense logged.")
        return super().form_valid(form)


class ExpenseUpdateView(OwnerRequiredMixin, ExpenseFormMixin, UpdateView):
    extra_context = {"active_nav": "expenses", "form_title": "Edit Expense"}

    def get_queryset(self):
        return Expense.objects.for_user(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Expense updated.")
        return super().form_valid(form)


class ExpenseDeleteView(OwnerRequiredMixin, DeleteView):
    model = Expense
    template_name = "expenses/expense_confirm_delete.html"
    success_url = reverse_lazy("expenses:list")
    context_object_name = "expense"
    extra_context = {"active_nav": "expenses"}

    def get_queryset(self):
        return Expense.objects.for_user(self.request.user).select_related("property")

    def form_valid(self, form):
        messages.success(self.request, "Expense deleted.")
        return super().form_valid(form)
