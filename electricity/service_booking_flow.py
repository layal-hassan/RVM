"""Service bookings share the electrician UI, with no customer-supplied hours."""
import re
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import AdminNotification, ServiceBooking

ARRIVAL_WINDOWS = {
    "Morning (08:00 AM - 12:00 PM)", "Afternoon (12:00 PM - 05:00 PM)",
    "Evening (05:00 PM - 10:00 PM)", "Any time (08:00 AM - 09:00 PM)",
}
DETAIL_FIELDS = {
    "location_details": 1000, "timing_notes": 1000, "housing_type": 40,
    "property_designation": 200, "housing_association_number": 40,
    "billing_email": 254, "invoice_reference": 160, "purchase_order_number": 160,
    "access_method": 40, "site_contact": 160, "site_contact_phone": 40,
    "access_notes": 1000, "commercial_notes": 500, "special_requirements": 1000,
}
BOOLEAN_DETAILS = ("rot_owner_confirm", "electronic_invoice_confirm", "access_confirm")
STEP_FIELDS = {
    1: {"customer_type": 20, "service_type": 60, "work_description": 500},
    2: {"street_address": 200, "zip_code": 10, "city": 80, "location_details": 1000},
    3: {"preferred_date": 10, "arrival_window": 60, "timing_notes": 1000},
    4: {"full_name": 160, "phone": 40, "email": 254, "personal_id": 40,
        "housing_type": 40, "property_designation": 200, "housing_association_number": 40,
        "apartment_number": 20, "company_name": 160, "organization_number": 40,
        "billing_email": 254, "invoice_reference": 160, "purchase_order_number": 160},
    5: {key: DETAIL_FIELDS[key] for key in ("access_method", "site_contact", "site_contact_phone", "access_notes", "commercial_notes", "special_requirements")},
}


def validate_step(step, data):
    from . import views as v
    errors = []
    for field, limit in STEP_FIELDS.get(step, {}).items():
        if len(str(data.get(field, ""))) > limit:
            errors.append(f"{field.replace('_', ' ').title()}: maximum {limit} characters.")
    required = {
        1: ("customer_type", "service_type", "work_description"),
        2: ("street_address", "zip_code", "city"),
        3: ("preferred_date", "arrival_window"),
        4: ("full_name", "phone", "email"),
    }
    for field in required.get(step, ()):
        if not data.get(field):
            errors.append(f"{field.replace('_', ' ').title()} is required.")
    if step == 1:
        if data.get("customer_type") not in ServiceBooking.AccountType.values:
            errors.append("Please choose Private or Business.")
        if data.get("service_type") not in dict(ServiceBooking._meta.get_field("service_type").choices):
            errors.append("Please select a service type.")
    elif step == 2:
        if not re.fullmatch(r"\d{3} ?\d{2}", data.get("zip_code", "")):
            errors.append("Enter a valid Swedish postal code.")
    elif step == 3:
        date = v._parse_date(data.get("preferred_date"))
        if not date or date < timezone.localdate():
            errors.append("Please choose a date from today onward.")
        if data.get("arrival_window") not in ARRIVAL_WINDOWS:
            errors.append("Please select an arrival window.")
    elif step == 4:
        business = data.get("customer_type") == "business"
        emails = ["email", "billing_email"] if business else ["email"]
        for field in emails:
            try:
                validate_email(data.get(field, ""))
            except ValidationError:
                errors.append(f"Enter a valid {field.replace('_', ' ')}.")
        if business:
            for field in ("company_name", "organization_number"):
                if not data.get(field):
                    errors.append(f"{field.replace('_', ' ').title()} is required.")
        else:
            if data.get("rot_answer") not in {"yes", "no"}:
                errors.append("Please choose whether to apply ROT.")
            if data.get("use_rot"):
                if not re.fullmatch(r"\d{8}-\d{4}", data.get("personal_id", "")):
                    errors.append("Enter the personal identity number as YYYYMMDD-XXXX.")
                if data.get("housing_type") not in {"house", "apartment"}:
                    errors.append("Please select the type of housing.")
                if not data.get("rot_owner_confirm") or not data.get("electronic_invoice_confirm"):
                    errors.append("Please confirm the ROT eligibility statements.")
    elif step == 5:
        if data.get("customer_type") == "business":
            if data.get("access_method") not in {"someone_on_site", "key_code", "arrange_later"}:
                errors.append("Please select how the electrician will access the site.")
        elif not data.get("access_confirm"):
            errors.append("Please confirm that the electrician will have access.")
    return errors


def _persist_uploads(items):
    uploads = []
    for item in items:
        with default_storage.open(item["path"], "rb") as source:
            path = default_storage.save(f"electricity/service_booking/attachments/{uuid.uuid4().hex}_{Path(item['name']).name}", source)
        uploads.append(dict(item, path=path))
    return uploads


def _finish(request, data):
    from . import views as v
    business = data["customer_type"] == "business"
    details = {key: data.get(key, "") for key in DETAIL_FIELDS}
    details.update({key: bool(data.get(key)) for key in BOOLEAN_DETAILS})
    with transaction.atomic():
        booking = ServiceBooking.objects.create(
            booking_version=2, service_type=data["service_type"], booking_details=details,
            account_type=data["customer_type"], full_name=data["full_name"],
            email=data["email"], phone=data["phone"], street_address=data["street_address"],
            zip_code=data["zip_code"].replace(" ", ""), city=data["city"],
            work_description=data["work_description"], preferred_date=v._parse_date(data["preferred_date"]),
            preferred_time_slot=data["arrival_window"], billing_type=data["customer_type"],
            company_name=data.get("company_name", "") if business else "",
            organization_number=data.get("organization_number", "") if business else "",
            personal_id=data.get("personal_id", "") if not business else "",
            apartment_number=data.get("apartment_number", "") if not business else "",
            rot_deduction=bool(data.get("use_rot")) if not business else False,
            uploads=_persist_uploads(data.get("business_attachments", []) if business else []),
        )
        AdminNotification.objects.create(service_booking=booking, message=f"New service booking from {booking.full_name}.")
    reference = f"SB-{booking.pk:06d}"
    lines = [f"Selected services: {booking.get_service_type_display()}",
             f"Service address: {booking.street_address}, {booking.zip_code} {booking.city}",
             "Pricing: to be confirmed after review."]
    v._send_custom_booking_confirmation_email(
        to_email=booking.email, customer_name=booking.full_name, booking_reference=reference,
        booking_type_label="Service Booking", team_name=v._booking_team_name(None),
        preferred_date=booking.preferred_date, preferred_time=booking.preferred_time_slot,
        summary_lines=lines, next_steps=["Our team will review your request and confirm the schedule and price."],
    )
    v._send_booking_company_notification_email(
        booking_reference=reference, booking_type_label="Service Booking", customer_name=booking.full_name,
        customer_email=booking.email, customer_phone=booking.phone,
        address=f"{booking.street_address}, {booking.zip_code} {booking.city}",
        summary_lines=lines + [f"Work description: {booking.work_description}"],
    )
    request.session["service_booking_id"] = reference
    request.session["service_booking_pk"] = booking.pk
    request.session.pop(v.SERVICE_BOOKING_SESSION_KEY, None)
    return redirect("electricity:service_booking_thank_you")


def service_booking_step(request, step):
    from . import views as v
    if step == 12:
        return redirect("electricity:service_booking_thank_you")
    if step == 11:
        return redirect("electricity:service_booking_step", step=6)
    if step not in range(1, 7):
        return redirect("electricity:service_booking_step", step=1)
    data = dict(v._get_service_booking_data(request))
    data.setdefault("customer_type", data.get("account_type", ""))
    data.setdefault("zip_code", request.session.get(v.ZIP_CHECK_SESSION_KEY, {}).get("service", ""))
    for earlier in range(1, step):
        if validate_step(earlier, data):
            return redirect("electricity:service_booking_step", step=earlier)
    errors = []
    if request.method == "POST":
        if step < 6:
            for key in STEP_FIELDS[step]:
                data[key] = request.POST.get(key, "").strip()
            if step == 1:
                data["account_type"] = data.get("customer_type", "")
            if step == 4:
                data["rot_answer"] = request.POST.get("use_rot", "")
                data["use_rot"] = data.get("customer_type") == "private" and data["rot_answer"] == "yes"
                for key in BOOLEAN_DETAILS[:2]:
                    data[key] = request.POST.get(key) == "yes"
            if step == 5:
                data["access_confirm"] = request.POST.get("access_confirm") == "yes"
                if data.get("customer_type") == "business":
                    remove = set(request.POST.getlist("remove_business_attachments"))
                    kept = [item for index, item in enumerate(data.get("business_attachments", [])) if str(index) not in remove]
                    uploads, upload_errors = v._save_electrician_attachments(request)
                    data["business_attachments"] = kept + uploads
                    errors.extend(upload_errors)
                    if len(data["business_attachments"]) > 10:
                        errors.append("You can upload a maximum of 10 files.")
            errors.extend(validate_step(step, data))
        else:
            data["accept_terms"] = request.POST.get("accept_terms") == "yes"
            if not data["accept_terms"]:
                errors.append("Please accept the Terms and Conditions.")
            if not errors:
                rejection = v.reject_public_submission(request)
                if rejection is not None:
                    return rejection
                return _finish(request, data)
        v._set_service_booking_data(request, data)
        if not errors:
            return redirect("electricity:service_booking_step", step=step + 1)
    return render(request, f"electricity/service_booking/step_{step}.html", {
        "step": step, "progress_percent": int(step / 6 * 100), "data": data, "errors": errors,
        "pricing": {"rot_requested": bool(data.get("use_rot")), "rot_percent": 30},
    })


def service_booking_thank_you(request):
    booking = get_object_or_404(ServiceBooking, pk=request.session.get("service_booking_pk"))
    return render(request, "electricity/service_booking/thank_you.html", {"booking": booking, "step": 6, "progress_percent": 100})
