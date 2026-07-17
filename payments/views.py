"""Rent payment views."""

from decimal import Decimal

from django.contrib import messages
from django.db.models import DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView, View,
)

from accounts.mixins import OwnerRequiredMixin
from .filters import RentPaymentFilter
from .forms import MarkPaidForm, RentPaymentForm
from .models import RentPayment

_MONEY = DecimalField(max_digits=12, decimal_places=2)


class PaymentListView(OwnerRequiredMixin, ListView):
    """Payment history with search, filtering and collection stat tiles."""

    model = RentPayment
    template_name = "payments/payment_list.html"
    context_object_name = "payments"
    paginate_by = 12
    extra_context = {"active_nav": "payments"}

    def get_base_queryset(self):
        return (RentPayment.objects.for_user(self.request.user)
                .select_related("lease__tenant__user", "lease__unit__property"))

    def get_queryset(self):
        qs = self.get_base_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(lease__tenant__user__first_name__icontains=q)
                | Q(lease__tenant__user__last_name__icontains=q)
                | Q(lease__unit__unit_number__icontains=q)
                | Q(lease__unit__property__title__icontains=q)
            )
        self.filterset = RentPaymentFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = self.filterset
        ctx["search_query"] = self.request.GET.get("q", "")

        base = self.get_base_queryset()
        today = timezone.localdate()
        collected = base.paid().aggregate(
            t=Coalesce(Sum(F("amount") + F("late_fee"), output_field=_MONEY), Decimal("0"), output_field=_MONEY))["t"]
        pending = base.pending().filter(due_date__gte=today).aggregate(
            t=Coalesce(Sum("amount", output_field=_MONEY), Decimal("0"), output_field=_MONEY))["t"]
        overdue_qs = base.overdue()
        overdue_amt = overdue_qs.aggregate(
            t=Coalesce(Sum(F("amount") + F("late_fee"), output_field=_MONEY), Decimal("0"), output_field=_MONEY))["t"]
        ctx["stats"] = {
            "collected": collected,
            "pending": pending,
            "overdue_amount": overdue_amt,
            "overdue_count": overdue_qs.count(),
        }
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class PaymentDetailView(OwnerRequiredMixin, DetailView):
    model = RentPayment
    template_name = "payments/payment_detail.html"
    context_object_name = "payment"
    extra_context = {"active_nav": "payments"}

    def get_queryset(self):
        return RentPayment.objects.for_user(self.request.user).select_related(
            "lease__tenant__user", "lease__unit__property")


class PaymentFormMixin:
    model = RentPayment
    form_class = RentPaymentForm
    template_name = "payments/payment_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["owner"] = self.request.user
        return kwargs


class PaymentCreateView(OwnerRequiredMixin, PaymentFormMixin, CreateView):
    extra_context = {"active_nav": "payments", "form_title": "Record Payment"}

    def form_valid(self, form):
        messages.success(self.request, "Payment recorded.")
        return super().form_valid(form)


class PaymentUpdateView(OwnerRequiredMixin, PaymentFormMixin, UpdateView):
    extra_context = {"active_nav": "payments", "form_title": "Edit Payment"}

    def get_queryset(self):
        return RentPayment.objects.for_user(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Payment updated.")
        return super().form_valid(form)


class PaymentDeleteView(OwnerRequiredMixin, DeleteView):
    model = RentPayment
    template_name = "payments/payment_confirm_delete.html"
    success_url = reverse_lazy("payments:list")
    context_object_name = "payment"
    extra_context = {"active_nav": "payments"}

    def get_queryset(self):
        return RentPayment.objects.for_user(self.request.user).select_related(
            "lease__tenant__user", "lease__unit__property")

    def form_valid(self, form):
        messages.success(self.request, "Payment deleted.")
        return super().form_valid(form)


class MarkPaidView(OwnerRequiredMixin, View):
    """Quick action: record a pending payment as paid."""

    template_name = "payments/mark_paid.html"

    def get_payment(self):
        return get_object_or_404(
            RentPayment.objects.for_user(self.request.user)
            .select_related("lease__tenant__user", "lease__unit__property"),
            pk=self.kwargs["pk"],
        )

    def get(self, request, *args, **kwargs):
        from django.shortcuts import render
        payment = self.get_payment()
        form = MarkPaidForm(initial={"payment_date": timezone.localdate(), "late_fee": payment.late_fee})
        return render(request, self.template_name,
                      {"payment": payment, "form": form, "active_nav": "payments"})

    def post(self, request, *args, **kwargs):
        from django.shortcuts import render
        payment = self.get_payment()
        form = MarkPaidForm(request.POST)
        if form.is_valid():
            payment.late_fee = form.cleaned_data.get("late_fee") or Decimal("0")
            payment.status = RentPayment.Status.PAID
            payment.payment_date = form.cleaned_data["payment_date"]
            payment.payment_method = form.cleaned_data["payment_method"]
            payment.save(update_fields=[
                "late_fee", "status", "payment_date", "payment_method", "updated_at",
            ])
            messages.success(request, f"Payment recorded — receipt {payment.receipt_number}.")
            return redirect("payments:detail", pk=payment.pk)
        return render(request, self.template_name,
                      {"payment": payment, "form": form, "active_nav": "payments"})
