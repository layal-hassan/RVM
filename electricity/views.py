import os
import re
import uuid
import datetime
import logging
from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.shortcuts import redirect, render
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
from django.core.mail import EmailMessage, send_mail
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.translation import gettext as _
from django.db.models import Q
from .forms import (
    BookingStatusUpdateForm,
    ServiceBookingStatusUpdateForm,
    ConsultationBookingForm,
    ConsultationRequestForm,
    CustomerProfileForm,
    ElectricalServiceForm,
    ProviderAssignForm,
    ServiceBookingAssignForm,
    OnCallBookingAssignForm,
    ElectricianBookingForm,
    ElectricianBookingAssignForm,
    FAQEntryForm,
    ProviderProfileForm,
    ProviderShiftForm,
    ServiceBookingForm,
    ServicePricingForm,
    OnCallBookingForm,
    SupportTicketForm,
    ZipCheckForm,
    OutsideAreaRequestForm,
    AcceptedZipCodeForm,
    ServiceRequestOutsideAreaAdminForm,
    UserCreateForm,
    UserEditForm,
    SignupForm,
    Step1Form,
    Step2Form,
    Step3Form,
    Step4Form,
    Step5Form,
    Step6Form,
    Step7Form,
)
from .admin_site import electricity_admin_site
from .models import (
    AdminNotification,
    BookingStatusUpdate,
    ServiceBookingStatusUpdate,
    ConsultationBooking,
    ConsultationBookingAttachment,
    ConsultationRequest,
    ElectricalService,
    ContactInquiry,
    CustomerProfile,
    ProviderProfile,
    ProviderShift,
    ServiceBooking,
    ElectricianBooking,
    FAQEntry,
    ServicePricing,
    OnCallBooking,
    SupportTicket,
    AcceptedZipCode,
    ServiceRequestOutsideArea,
)
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


def _booking_team_name(assigned_provider=None):
    if assigned_provider and getattr(assigned_provider, "display_name", "").strip():
        return assigned_provider.display_name.strip()
    return "RWM EL"


def _send_booking_confirmation_email(
    *,
    to_email,
    customer_name,
    booking_reference,
    booking_type_label,
    team_name,
    preferred_date=None,
    preferred_time=None,
):
    if not to_email:
        return

    subject = f"Booking Confirmation - {booking_reference}"
    lines = [
        f"مرحباً {customer_name or 'عميلنا الكريم'}،",
        "",
        f"تم استلام طلب الحجز بنجاح.",
        f"رقم الحجز: {booking_reference}",
        f"نوع الحجز: {booking_type_label}",
        f"الفريق المسؤول: {team_name}",
    ]
    if preferred_date:
        lines.append(f"التاريخ المطلوب: {preferred_date}")
    if preferred_time:
        lines.append(f"الوقت المطلوب: {preferred_time}")
    lines.extend(
        [
            "",
            "سيقوم فريقنا بمراجعة الحجز والتواصل معك عند الحاجة.",
            "",
            "RWM EL",
        ]
    )
    try:
        from_email = (
            getattr(settings, "BOOKING_FROM_EMAIL", None)
            or getattr(settings, "DEFAULT_FROM_EMAIL", None)
            or "services@rwmel.se"
        )
        send_mail(subject, "\n".join(lines), from_email, [to_email])
    except Exception:
        logger.exception("Booking confirmation email failed to send to %s.", to_email)


def _service_titles_for_ids(service_ids):
    if not service_ids:
        return []
    services = ElectricalService.objects.filter(id__in=service_ids)
    title_by_id = {str(item.id): item.title for item in services}
    return [title_by_id[str(service_id)] for service_id in service_ids if str(service_id) in title_by_id]


def _format_currency_amount(amount, currency):
    if amount in (None, ""):
        return None
    try:
        return f"{currency} {float(amount):.2f}"
    except (TypeError, ValueError):
        return f"{currency} {amount}"


def _on_call_coverage_time_labels():
    return {
        "evenings": "Evenings",
        "nights": "Nights",
        "weekends": "Weekends & holidays",
    }


def _on_call_coverage_scope_labels():
    return {
        "power_outages": "Power outages",
        "fuse_boards": "Fuse boards",
        "common_areas": "Common areas",
        "critical_systems": "Critical systems",
        "general_faults": "General faults",
    }


def _send_custom_booking_confirmation_email(
    *,
    to_email,
    customer_name,
    booking_reference,
    booking_type_label,
    team_name,
    preferred_date=None,
    preferred_time=None,
    summary_lines=None,
    next_steps=None,
):
    if not to_email:
        return

    subject = f"Booking Confirmation - {booking_reference}"
    lines = [
        f"Hello {customer_name or 'Valued Customer'},",
        "",
        "We have received your booking request successfully.",
        "",
        "Booking details:",
        f"- Reference: {booking_reference}",
        f"- Booking type: {booking_type_label}",
        f"- Service team: {team_name}",
    ]
    if preferred_date:
        lines.append(f"- Requested date: {preferred_date}")
    if preferred_time:
        lines.append(f"- Requested time: {preferred_time}")
    if summary_lines:
        lines.extend(["", "Summary:"])
        lines.extend(f"- {line}" for line in summary_lines if line)
    lines.extend(["", "Next steps:"])
    if next_steps:
        lines.extend(f"- {line}" for line in next_steps if line)
    else:
        lines.extend(
            [
                "- Our team will review your booking and contact you if any clarification is needed.",
                "- Please keep this reference for future communication.",
            ]
        )
    lines.extend(["", "Regards,", "RWM EL"])
    try:
        from_email = (
            getattr(settings, "BOOKING_FROM_EMAIL", None)
            or getattr(settings, "DEFAULT_FROM_EMAIL", None)
            or "services@rwmel.se"
        )
        send_mail(subject, "\n".join(lines), from_email, [to_email])
    except Exception:
        logger.exception("Booking confirmation email failed to send to %s.", to_email)


def home(request):
    return render(request, "electricity/landing.html")


def services(request):
    services_qs = ElectricalService.objects.filter(is_active=True).order_by("order", "title")
    pricing = ServicePricing.objects.filter(is_active=True).order_by("-created_at").first()
    pricing_context = {}
    if pricing:
        base_total = pricing.labor_rate + pricing.transport_fee
        rot_deduction = pricing.labor_rate * (pricing.rot_percent / 100)
        pricing_context = {
            "pricing": pricing,
            "base_total": base_total,
            "rot_deduction": rot_deduction,
            "rot_total": base_total - rot_deduction,
            "hourly_standard": pricing.labor_rate,
            "hourly_rot": pricing.labor_rate - rot_deduction,
        }
    return render(
        request,
        "electricity/services.html",
        {"services": services_qs, **pricing_context},
    )


def terms(request):
    return render(request, "electricity/terms.html")


def cookies(request):
    return render(request, "electricity/cookies.html")


def privacy(request):
    return render(request, "electricity/privacy.html")


def about(request):
    return render(request, "electricity/about.html")


def on_call(request):
    return render(request, "electricity/on_call.html")


def support(request):
    errors = []
    data = {}
    if request.method == "POST":
        data["full_name"] = request.POST.get("full_name", "").strip()
        data["email"] = request.POST.get("email", "").strip()
        data["phone"] = request.POST.get("phone", "").strip()
        data["request_type"] = request.POST.get("request_type", "").strip()
        data["customer_type"] = request.POST.get("customer_type", "").strip()
        data["project_address"] = request.POST.get("project_address", "").strip()
        data["message"] = request.POST.get("message", "").strip()
        if not data["full_name"]:
            errors.append("Full name is required.")
        if not data["email"]:
            errors.append("Email address is required.")
        else:
            try:
                validate_email(data["email"])
            except ValidationError:
                errors.append("Please provide a valid email address.")
        if not data["message"]:
            errors.append("Please describe your request.")

        if not errors:
            ticket = SupportTicket.objects.create(
                full_name=data["full_name"],
                email=data["email"],
                phone=data.get("phone", ""),
                request_type=data.get("request_type", ""),
                customer_type=data.get("customer_type", ""),
                project_address=data.get("project_address", ""),
                message=data.get("message", ""),
            )
            AdminNotification.objects.create(
                message=f"New support ticket from {ticket.full_name}.",
            )
            subject = f"Support Request: {data.get('request_type') or 'General'}"
            body = (
                f"Name: {data.get('full_name')}\n"
                f"Email: {data.get('email')}\n"
                f"Phone: {data.get('phone')}\n"
                f"Customer Type: {data.get('customer_type')}\n"
                f"Project Address: {data.get('project_address')}\n"
                f"Request Type: {data.get('request_type')}\n"
                f"\nMessage:\n{data.get('message')}\n"
            )
            try:
                from_email = (
                    getattr(settings, "EMAIL_HOST_USER", None)
                    or getattr(settings, "DEFAULT_FROM_EMAIL", None)
                    or "support@rwmel.se"
                )
                email_message = EmailMessage(
                    subject,
                    body,
                    from_email,
                    ["support@rwmel.se"],
                )
                if data.get("email"):
                    email_message.reply_to = [data.get("email")]
                email_message.send()
            except Exception:
                logger.exception("Support ticket email failed to send.")
            return render(
                request,
                "electricity/support.html",
                {"submitted": True, "ticket_id": f"ST-{ticket.id:06d}"},
            )
    return render(request, "electricity/support.html", {"errors": errors, "data": data})


def contact(request):
    status = None
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        request_type = request.POST.get("request_type", "").strip()
        inquiry_type = request.POST.get("inquiry_type", "").strip() or "new_booking"
        message = request.POST.get("message", "").strip()
        consent = request.POST.get("consent")

        try:
            validate_email(email)
        except ValidationError:
            status = "error"
        else:
            if not (full_name and message and consent and inquiry_type):
                status = "error"
            else:
                ContactInquiry.objects.create(
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    address=address,
                    request_type=request_type,
                    inquiry_type=inquiry_type,
                    message=message,
                    consent=True,
                )
                subject = f"Contact Request: {request_type or 'General Inquiry'}"
                body = (
                    f"Name: {full_name}\n"
                    f"Email: {email}\n"
                    f"Phone: {phone}\n"
                    f"Address: {address}\n"
                    f"Request Type: {request_type}\n"
                    f"Inquiry Type: {inquiry_type}\n"
                    f"\nMessage:\n{message}\n"
                )
                try:
                    to_email = getattr(settings, "CONTACT_TO_EMAIL", None) or "info@rwmel.se"
                    from_email = (
                        getattr(settings, "EMAIL_HOST_USER", None)
                        or getattr(settings, "DEFAULT_FROM_EMAIL", None)
                        or "support@rwmel.se"
                    )
                    email_message = EmailMessage(
                        subject,
                        body,
                        from_email,
                        [to_email],
                    )
                    if email:
                        email_message.reply_to = [email]
                    email_message.send()
                    status = "sent"
                except Exception:
                    logger.exception("Contact inquiry email failed to send.")
                    status = "error"

    return render(request, "electricity/contact.html", {"contact_status": status})


def faq(request):
    faqs = FAQEntry.objects.filter(is_active=True).order_by("order", "-created_at")
    return render(request, "electricity/faq.html", {"faqs": faqs})


BOOKING_SESSION_KEY = "electricity_booking"
SERVICE_BOOKING_SESSION_KEY = "electricity_service_booking"
ON_CALL_BOOKING_SESSION_KEY = "electricity_on_call_booking"
ELECTRICIAN_BOOKING_SESSION_KEY = "electricity_electrician_booking"

ELECTRICIAN_SERVICE_TYPE_LABELS = {
    "residential": _("Residential Electrical Repair"),
    "installation": _("New Installations"),
    "commercial": _("Commercial Maintenance"),
}
ZIP_CHECK_SESSION_KEY = "electricity_zip_checks"

SLOT_MINUTES = 30
LOOKAHEAD_DAYS = 14


def _eligible_services():
    return ElectricalService.objects.filter(is_active=True, price__gt=0, duration_minutes__gt=0)


def _service_duration_minutes(service_ids):
    services = _eligible_services().filter(id__in=service_ids)
    if services.count() != len(service_ids):
        raise ValidationError("Selected services include items without valid price or duration.")
    return sum(int(s.duration_minutes) for s in services)


def _get_active_pricing():
    return ServicePricing.objects.filter(is_active=True).order_by("-created_at").first()


def _is_first_consultation(email, phone):
    if email:
        return not ConsultationBooking.objects.filter(email__iexact=email).exists()
    if phone:
        return not ConsultationBooking.objects.filter(phone=phone).exists()
    return True


def _service_booking_duration_minutes(data, hours_override=None):
    pricing_type = (data.get("pricing_type") or ServiceBooking.PricingType.FIXED).lower()
    if pricing_type == ServiceBooking.PricingType.HOURLY:
        hours_value = hours_override or data.get("hourly_hours") or 0
        try:
            hours_value = int(hours_value)
        except (TypeError, ValueError):
            hours_value = 0
        return max(hours_value, 0) * 60
    return _service_duration_minutes(data.get("services", []))


def _parse_time(value):
    if not value:
        return None
    for fmt in ("%H:%M", "%I:%M %p"):
        try:
            return datetime.datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def _combine_date_time(date_value, time_value):
    if not date_value or not time_value:
        return None
    dt = datetime.datetime.combine(date_value, time_value)
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


def _active_service_bookings_for_provider(provider):
    return ServiceBooking.objects.filter(assigned_provider=provider).exclude(
        status__in=[ServiceBooking.Status.COMPLETED, ServiceBooking.Status.CANCELED]
    ).exclude(start_at__isnull=True).exclude(end_at__isnull=True)


def _busy_ranges_for_provider(provider, day_start, day_end, exclude_booking_id=None):
    bookings = _active_service_bookings_for_provider(provider).filter(
        start_at__lt=day_end,
        end_at__gt=day_start,
    )
    if exclude_booking_id:
        bookings = bookings.exclude(id=exclude_booking_id)
    return list(bookings.values_list("start_at", "end_at"))


def _provider_is_available(provider, start_at, end_at, exclude_booking_id=None):
    if not start_at or not end_at:
        return False
    overlaps = _active_service_bookings_for_provider(provider).filter(
        start_at__lt=end_at,
        end_at__gt=start_at,
    )
    if exclude_booking_id:
        overlaps = overlaps.exclude(id=exclude_booking_id)
    return not overlaps.exists()


def _provider_slots_for_date(provider, for_date, duration_minutes, start_from=None):
    if not for_date or not duration_minutes:
        return []
    weekday = for_date.weekday()
    shifts = ProviderShift.objects.filter(provider=provider, weekday=weekday)
    if not shifts.exists():
        return []
    day_start = _combine_date_time(for_date, datetime.time(0, 0))
    day_end = _combine_date_time(for_date, datetime.time(23, 59))
    busy_ranges = _busy_ranges_for_provider(provider, day_start, day_end)
    slots = []
    now = timezone.now()
    duration = datetime.timedelta(minutes=duration_minutes)
    slot_step = datetime.timedelta(minutes=SLOT_MINUTES)
    for shift in shifts:
        shift_start = _combine_date_time(for_date, shift.start_time)
        shift_end = _combine_date_time(for_date, shift.end_time)
        if start_from and shift_start < start_from < shift_end:
            shift_start = start_from
        slot_start = shift_start
        while slot_start + duration <= shift_end:
            if slot_start >= now or slot_start.date() > now.date():
                slot_end = slot_start + duration
                conflict = False
                for busy_start, busy_end in busy_ranges:
                    if slot_start < busy_end and slot_end > busy_start:
                        conflict = True
                        break
                if not conflict:
                    slots.append(slot_start)
            slot_start += slot_step
    return slots


def _available_slots_for_zip(zip_code, for_date, duration_minutes):
    zip_code = _normalize_zip(zip_code or "")
    if not zip_code:
        return []
    providers = ProviderProfile.objects.filter(is_active=True, zip_code=zip_code)
    slot_map = {}
    for provider in providers:
        for slot in _provider_slots_for_date(provider, for_date, duration_minutes):
            key = slot.time().strftime("%H:%M")
            slot_map.setdefault(key, slot)
    slots = sorted(slot_map.values())
    return slots


def _format_slots(zip_code, for_date, duration_minutes):
    slots = _available_slots_for_zip(zip_code, for_date, duration_minutes)
    formatted = []
    duration = datetime.timedelta(minutes=duration_minutes)
    for slot in slots:
        end_slot = slot + duration
        formatted.append(
            {
                "start": slot.time().strftime("%H:%M"),
                "end": end_slot.time().strftime("%H:%M"),
                "label": f"{slot:%H:%M} - {end_slot:%H:%M}",
            }
        )
    return formatted


def _earliest_availability_for_zip(zip_code, duration_minutes, start_date=None):
    providers = ProviderProfile.objects.filter(is_active=True, zip_code=zip_code)
    if not providers.exists():
        return None, None
    start_date = start_date or timezone.localdate()
    earliest = None
    earliest_provider = None
    for day_offset in range(LOOKAHEAD_DAYS):
        day = start_date + datetime.timedelta(days=day_offset)
        for provider in providers:
            slots = _provider_slots_for_date(provider, day, duration_minutes)
            if not slots:
                continue
            slot = min(slots)
            if earliest is None or slot < earliest:
                earliest = slot
                earliest_provider = provider
        if earliest:
            break
    return earliest_provider, earliest


def _find_provider_for_slot(zip_code, start_at, end_at):
    providers = ProviderProfile.objects.filter(is_active=True, zip_code=zip_code)
    candidates = []
    for provider in providers:
        if _provider_is_available(provider, start_at, end_at):
            candidates.append(provider)
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.display_name)[0]


def available_providers(for_date, for_time_slot, exclude_booking_id=None):
    if not for_date or not for_time_slot:
        return ProviderProfile.objects.filter(is_active=True)
    consult_conflicts = ConsultationBooking.objects.filter(
        preferred_date=for_date,
        preferred_time_slot=for_time_slot,
        status__in=[
            ConsultationBooking.BookingStatus.ASSIGNED,
            ConsultationBooking.BookingStatus.ON_THE_WAY,
            ConsultationBooking.BookingStatus.STARTED,
            ConsultationBooking.BookingStatus.PAUSED,
            ConsultationBooking.BookingStatus.RESUMED,
            ConsultationBooking.BookingStatus.NOT_AVAILABLE,
        ],
    )
    if exclude_booking_id:
        consult_conflicts = consult_conflicts.exclude(id=exclude_booking_id)
    service_conflicts = ServiceBooking.objects.filter(
        preferred_date=for_date,
        preferred_time_slot=for_time_slot,
        assigned_provider__isnull=False,
    ).exclude(status__in=[ServiceBooking.Status.COMPLETED, ServiceBooking.Status.CANCELED])
    if exclude_booking_id:
        service_conflicts = service_conflicts.exclude(id=exclude_booking_id)

    busy_provider_ids = list(consult_conflicts.values_list("assigned_provider_id", flat=True))
    busy_provider_ids += list(service_conflicts.values_list("assigned_provider_id", flat=True))
    return ProviderProfile.objects.filter(is_active=True).exclude(id__in=busy_provider_ids)


def _get_booking_data(request):
    return request.session.get(BOOKING_SESSION_KEY, {})


def _set_booking_data(request, data):
    request.session[BOOKING_SESSION_KEY] = data
    request.session.modified = True


def _get_service_booking_data(request):
    return request.session.get(SERVICE_BOOKING_SESSION_KEY, {})


def _set_service_booking_data(request, data):
    request.session[SERVICE_BOOKING_SESSION_KEY] = data
    request.session.modified = True


def _get_on_call_booking_data(request):
    return request.session.get(ON_CALL_BOOKING_SESSION_KEY, {})


def _set_on_call_booking_data(request, data):
    request.session[ON_CALL_BOOKING_SESSION_KEY] = data
    request.session.modified = True


def _get_electrician_booking_data(request):
    return request.session.get(ELECTRICIAN_BOOKING_SESSION_KEY, {})


def _set_electrician_booking_data(request, data):
    request.session[ELECTRICIAN_BOOKING_SESSION_KEY] = data


def _electrician_service_type_label(value):
    if not value:
        return "-"
    return ELECTRICIAN_SERVICE_TYPE_LABELS.get(value, str(value).replace("_", " ").title())
    request.session.modified = True


def _update_session_from_form_data(data, form):
    if not form:
        return data
    for name, field in form.fields.items():
        if getattr(field.widget, "allow_multiple_selected", False):
            data[name] = form.data.getlist(name)
        else:
            data[name] = form.data.get(name, "").strip()
    return data


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _normalize_zip(value):
    return re.sub(r"\s+", "", value)


def _provider_table_rows(providers, reasons_by_id):
    rows = []
    for provider in providers:
        info = reasons_by_id.get(provider.id, {})
        rows.append(
            {
                "name": provider.display_name,
                "zip": provider.zip_code or "-",
                "available": bool(info.get("available")),
                "reason": info.get("reason", ""),
            }
        )
    return rows


def _zip_is_allowed(zip_code):
    code = _normalize_zip(zip_code)
    return AcceptedZipCode.objects.filter(code=code, is_active=True).exists()


def _ensure_zip_verified(request, flow):
    checks = request.session.get(ZIP_CHECK_SESSION_KEY, {})
    return bool(checks.get(flow))


def zip_check(request, flow):
    if flow not in {"consultation", "service", "on_call"}:
        raise Http404("Unknown flow")

    form = ZipCheckForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        zip_code = _normalize_zip(form.cleaned_data["zip_code"])
        if _zip_is_allowed(zip_code):
            checks = request.session.get(ZIP_CHECK_SESSION_KEY, {})
            checks[flow] = zip_code
            request.session[ZIP_CHECK_SESSION_KEY] = checks
            request.session.modified = True
            if flow == "consultation":
                return redirect("electricity:booking_step_1")
            if flow == "service":
                return redirect("electricity:service_booking_step", step=1)
            return redirect("electricity:on_call_booking_step", step=1)
        return redirect("electricity:outside_area", flow=flow, zip_code=zip_code)

    return render(request, "electricity/zip_check.html", {"form": form, "flow": flow})


def outside_area(request, flow, zip_code):
    if flow not in {"consultation", "service", "on_call"}:
        raise Http404("Unknown flow")

    form = OutsideAreaRequestForm(request.POST or None)
    submitted = False
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.zip_code = _normalize_zip(zip_code)
        if flow == "consultation":
            item.request_type = ServiceRequestOutsideArea.RequestType.CONSULTATION
        elif flow == "service":
            item.request_type = ServiceRequestOutsideArea.RequestType.SERVICE
        else:
            item.request_type = ServiceRequestOutsideArea.RequestType.ON_CALL
        item.save()
        AdminNotification.objects.create(
            message=f"Outside-area request from {item.full_name} ({item.zip_code}).",
        )
        submitted = True
    return render(
        request,
        "electricity/outside_area.html",
        {"form": form, "flow": flow, "zip_code": zip_code, "submitted": submitted},
    )


def _save_service_uploads(request):
    uploads = request.FILES.getlist("uploads")
    if not uploads:
        return []
    upload_dir = os.path.join(settings.MEDIA_ROOT, "service_booking", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    fs = FileSystemStorage(location=upload_dir)
    saved_paths = []
    for upload in uploads:
        filename = f"{uuid.uuid4().hex}_{upload.name}"
        stored_name = fs.save(filename, upload)
        saved_paths.append(os.path.join("service_booking", "uploads", stored_name))
    return saved_paths


def _require_fields_or_redirect(request, required_fields, redirect_name):
    data = _get_booking_data(request)
    for field in required_fields:
        value = data.get(field)
        if value in (None, "", [], {}):
            return redirect(redirect_name)
    return None


def _save_temp_upload(request, field_name):
    upload = request.FILES.get(field_name)
    if not upload:
        return None
    temp_dir = os.path.join(settings.MEDIA_ROOT, "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    fs = FileSystemStorage(location=temp_dir)
    filename = f"{uuid.uuid4().hex}_{upload.name}"
    stored_name = fs.save(filename, upload)
    return os.path.join("temp_uploads", stored_name)


def _normalize_temp_uploads(temp_uploads):
    normalized = {}
    for field in ("photo", "video", "document"):
        value = (temp_uploads or {}).get(field, [])
        if not value:
            normalized[field] = []
        elif isinstance(value, list):
            normalized[field] = value
        else:
            normalized[field] = [value]
    return normalized


def _save_temp_uploads(request, field_name):
    uploads = request.FILES.getlist(field_name)
    if not uploads:
        return []
    temp_dir = os.path.join(settings.MEDIA_ROOT, "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    fs = FileSystemStorage(location=temp_dir)
    saved_paths = []
    for upload in uploads:
        filename = f"{uuid.uuid4().hex}_{upload.name}"
        stored_name = fs.save(filename, upload)
        saved_paths.append(
            {
                "path": os.path.join("temp_uploads", stored_name),
                "name": upload.name,
                "size": upload.size,
            }
        )
    return saved_paths


def _remove_temp_uploads(temp_uploads, removal_values):
    normalized = _normalize_temp_uploads(temp_uploads)
    removals = {"photo": set(), "video": set(), "document": set()}
    for value in removal_values:
        try:
            kind, index_text = (value or "").split(":", 1)
            index = int(index_text)
        except (ValueError, TypeError):
            continue
        if kind in removals and index >= 0:
            removals[kind].add(index)

    cleaned = {}
    for kind, items in normalized.items():
        kept_items = []
        for index, item in enumerate(items):
            if index in removals[kind]:
                temp_path = item.get("path") if isinstance(item, dict) else item
                if temp_path:
                    full_path = os.path.join(settings.MEDIA_ROOT, temp_path)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                continue
            kept_items.append(item)
        cleaned[kind] = kept_items
    return cleaned


def _attach_temp_file(instance, temp_path, field_name):
    if not temp_path:
        return
    full_path = os.path.join(settings.MEDIA_ROOT, temp_path)
    if not os.path.exists(full_path):
        return
    with open(full_path, "rb") as handle:
        getattr(instance, field_name).save(os.path.basename(full_path), File(handle), save=False)


def _create_attachments_from_temp_uploads(booking, temp_uploads):
    for kind, items in _normalize_temp_uploads(temp_uploads).items():
        for item in items:
            temp_path = item.get("path") if isinstance(item, dict) else item
            if not temp_path:
                continue
            full_path = os.path.join(settings.MEDIA_ROOT, temp_path)
            if not os.path.exists(full_path):
                continue
            original_name = item.get("name", "") if isinstance(item, dict) else ""
            with open(full_path, "rb") as handle:
                attachment = ConsultationBookingAttachment(
                    booking=booking,
                    kind=kind,
                    original_name=original_name or os.path.basename(full_path),
                )
                attachment.file.save(os.path.basename(full_path), File(handle), save=True)


def _temp_uploads_for_display(temp_uploads):
    labels = {
        "photo": _("Photo"),
        "video": _("Video"),
        "document": _("Document"),
    }
    items = []
    for kind, values in _normalize_temp_uploads(temp_uploads).items():
        for index, value in enumerate(values):
            if isinstance(value, dict):
                name = value.get("name") or os.path.basename(value.get("path", ""))
                size = value.get("size") or 0
            else:
                name = os.path.basename(value)
                size = 0
            items.append(
                {
                    "kind": kind,
                    "label": labels[kind],
                    "name": name,
                    "size_kb": max(1, round(size / 1024)) if size else None,
                    "remove_value": f"{kind}:{index}",
                }
            )
    return items


def _choice_label(choices, value):
    return dict(choices).get(value, value)


def booking_step_1(request):
    if not _ensure_zip_verified(request, "consultation"):
        return redirect("electricity:zip_check", flow="consultation")
    data = _get_booking_data(request)
    form = Step1Form(request.POST or None, initial=data)
    if request.method == "POST":
        if form.is_valid():
            data.update(form.cleaned_data)
            _set_booking_data(request, data)
            return redirect("electricity:booking_step_2")
        data = _update_session_from_form_data(data, form)
        _set_booking_data(request, data)
    return render(
        request,
        "electricity/booking/step_1.html",
        {
            "form": form,
            "step": 1,
            "progress_percent": 14,
            "title": _("How would you like to start?"),
        },
    )


def booking_step_2(request):
    if not _ensure_zip_verified(request, "consultation"):
        return redirect("electricity:zip_check", flow="consultation")
    guard = _require_fields_or_redirect(request, ["consultation_type"], "electricity:booking_step_1")
    if guard:
        return guard
    data = _get_booking_data(request)
    form = Step2Form(request.POST or None, initial=data)
    if request.method == "POST":
        if form.is_valid():
            data.update(form.cleaned_data)
            _set_booking_data(request, data)
            return redirect("electricity:booking_step_3")
        data = _update_session_from_form_data(data, form)
        _set_booking_data(request, data)
    return render(
        request,
        "electricity/booking/step_2.html",
        {
            "form": form,
            "step": 2,
            "progress_percent": 28,
            "title": _("Tell us about the property"),
        },
    )


def booking_step_3(request):
    if not _ensure_zip_verified(request, "consultation"):
        return redirect("electricity:zip_check", flow="consultation")
    guard = _require_fields_or_redirect(
        request, ["consultation_type", "property_type", "property_size"], "electricity:booking_step_2"
    )
    if guard:
        return guard
    data = _get_booking_data(request)
    form = Step3Form(request.POST or None, initial=data)
    if request.method == "POST":
        if form.is_valid():
            cleaned = form.cleaned_data
            cleaned["urgent"] = cleaned.get("urgent") == "yes"
            data.update(cleaned)
            _set_booking_data(request, data)
            return redirect("electricity:booking_step_4")
        data = _update_session_from_form_data(data, form)
        _set_booking_data(request, data)
    return render(
        request,
        "electricity/booking/step_3.html",
        {
            "form": form,
            "step": 3,
            "progress_percent": 42,
            "title": _("What do you want help with?"),
        },
    )


def booking_step_4(request):
    if not _ensure_zip_verified(request, "consultation"):
        return redirect("electricity:zip_check", flow="consultation")
    guard = _require_fields_or_redirect(
        request,
        ["consultation_type", "property_type", "property_size", "urgent"],
        "electricity:booking_step_3",
    )
    if guard:
        return guard
    data = _get_booking_data(request)
    form = Step4Form(request.POST or None, initial=data)
    if request.method == "POST":
        if form.is_valid():
            data.update(form.cleaned_data)
            _set_booking_data(request, data)
            return redirect("electricity:booking_step_5")
        data = _update_session_from_form_data(data, form)
        _set_booking_data(request, data)
    return render(
        request,
        "electricity/booking/step_4.html",
        {
            "form": form,
            "step": 4,
            "progress_percent": 57,
            "title": _("Describe your project or issue"),
        },
    )


def booking_step_5(request):
    if not _ensure_zip_verified(request, "consultation"):
        return redirect("electricity:zip_check", flow="consultation")
    guard = _require_fields_or_redirect(
        request,
        ["consultation_type", "property_type", "property_size", "urgent"],
        "electricity:booking_step_4",
    )
    if guard:
        return guard
    data = _get_booking_data(request)
    form = Step5Form(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if form.is_valid():
            temp_uploads = _normalize_temp_uploads(data.get("temp_uploads", {}))
            temp_uploads = _remove_temp_uploads(temp_uploads, request.POST.getlist("remove_temp_uploads"))
            for field in ("photo", "video", "document"):
                saved_items = _save_temp_uploads(request, field)
                if saved_items:
                    temp_uploads[field].extend(saved_items)
            data["temp_uploads"] = temp_uploads
            _set_booking_data(request, data)
            return redirect("electricity:booking_step_6")
        data = _update_session_from_form_data(data, form)
        _set_booking_data(request, data)
    return render(
        request,
        "electricity/booking/step_5.html",
        {
            "form": form,
            "step": 5,
            "progress_percent": 71,
            "title": _("Add photos or documents (optional)"),
            "existing_uploads": _temp_uploads_for_display(data.get("temp_uploads", {})),
        },
    )


def booking_step_6(request):
    if not _ensure_zip_verified(request, "consultation"):
        return redirect("electricity:zip_check", flow="consultation")
    guard = _require_fields_or_redirect(
        request,
        ["consultation_type", "property_type", "property_size", "urgent"],
        "electricity:booking_step_5",
    )
    if guard:
        return guard
    data = _get_booking_data(request)
    form = Step6Form(request.POST or None, initial=data)
    if request.method == "POST":
        if form.is_valid():
            contact_type = form.cleaned_data.get("contact_type")
            if contact_type == "private":
                if not form.cleaned_data.get("personal_id"):
                    form.add_error("personal_id", _("Personal ID is required for private bookings."))
                if not form.cleaned_data.get("full_name"):
                    form.add_error("full_name", _("Full name is required."))
                if not form.cleaned_data.get("email"):
                    form.add_error("email", _("Email is required."))
                if not form.cleaned_data.get("phone"):
                    form.add_error("phone", _("Phone number is required."))
                if not form.cleaned_data.get("availability_days"):
                    form.add_error("availability_days", _("Please select at least one available day."))
                if not form.cleaned_data.get("time_window"):
                    form.add_error("time_window", _("Please select a preferred time window."))
            if contact_type == "business":
                if not form.cleaned_data.get("company_name"):
                    form.add_error("company_name", _("Company name is required."))
                if not form.cleaned_data.get("organization_number"):
                    form.add_error("organization_number", _("Organization number is required."))
                if not form.cleaned_data.get("full_name"):
                    form.cleaned_data["full_name"] = form.cleaned_data.get("company_name", "")
            if form.errors:
                data = _update_session_from_form_data(data, form)
                _set_booking_data(request, data)
                is_free = _is_first_consultation(form.cleaned_data.get("email"), form.cleaned_data.get("phone"))
                return render(
                    request,
                    "electricity/booking/step_6.html",
                    {
                        "form": form,
                        "step": 6,
                        "progress_percent": 85,
                        "title": _("Your contact details"),
                        "consultation_free": is_free,
                    },
                )
            data.update(form.cleaned_data)
            _set_booking_data(request, data)
            return redirect("electricity:booking_step_7")
        data = _update_session_from_form_data(data, form)
        _set_booking_data(request, data)
    is_free = _is_first_consultation(data.get("email"), data.get("phone"))
    return render(
        request,
        "electricity/booking/step_6.html",
        {
            "form": form,
            "step": 6,
            "progress_percent": 85,
            "title": _("Your contact details"),
            "consultation_free": is_free,
        },
    )


def booking_step_7(request):
    if not _ensure_zip_verified(request, "consultation"):
        return redirect("electricity:zip_check", flow="consultation")
    guard = _require_fields_or_redirect(
        request,
        [
            "consultation_type",
            "property_type",
            "property_size",
            "urgent",
            "full_name",
        ],
        "electricity:booking_step_6",
    )
    if guard:
        return guard
    data = _get_booking_data(request)
    initial = dict(data)
    existing_slot = data.get("preferred_time_slot") or ""
    if existing_slot and "preferred_time" not in initial:
        initial["preferred_time"] = existing_slot.strip().split()[0]
    form = Step7Form(request.POST or None, initial=initial)
    if request.method == "POST":
        if form.is_valid():
            cleaned = form.cleaned_data
            time_value = (cleaned.get("preferred_time") or "").strip()
            cleaned["preferred_time_slot"] = time_value if time_value else ""
            data.update(cleaned)
        else:
            data = _update_session_from_form_data(data, form)
            _set_booking_data(request, data)
            is_free = _is_first_consultation(data.get("email"), data.get("phone"))
            pricing = _get_active_pricing()
            consultation_price = 0
            if not is_free and pricing:
                consultation_price = float(pricing.consultation_price)
            return render(
                request,
                "electricity/booking/step_7.html",
                {
                    "form": form,
                    "step": 7,
                    "progress_percent": 100,
                    "title": _("Review your request"),
                    "data": data,
                    "consultation_free": is_free,
                    "consultation_price": consultation_price,
                    "currency": pricing.currency if pricing else "SEK",
                },
            )
    if request.method == "POST" and form.is_valid():
        required = [
            "consultation_type",
            "property_type",
            "property_size",
            "urgent",
            "full_name",
        ]
        if data.get("contact_type") == "private":
            required.append("personal_id")
        if data.get("contact_type") == "business":
            required.extend(["company_name", "organization_number"])
        guard = _require_fields_or_redirect(request, required, "electricity:booking_step_6")
        if guard:
            return guard
        pricing = _get_active_pricing()
        is_free = _is_first_consultation(data.get("email"), data.get("phone"))
        consultation_price = 0
        if not is_free and pricing:
            consultation_price = float(pricing.consultation_price)
        booking = ConsultationBooking(
            consultation_type=data.get("consultation_type", ""),
            property_type=data.get("property_type", ""),
            property_type_other=data.get("property_type_other", ""),
            property_size=data.get("property_size", ""),
            year_built=data.get("year_built", ""),
            services=data.get("services", []),
            urgent=bool(data.get("urgent")),
            project_description=data.get("project_description", ""),
            contact_type=data.get("contact_type", ""),
            personal_id=data.get("personal_id", ""),
            company_name=data.get("company_name", ""),
            organization_number=data.get("organization_number", ""),
            company_address=data.get("company_address", ""),
            full_name=data.get("full_name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            availability_days=data.get("availability_days", []),
            time_window=data.get("time_window", ""),
            preferred_date=data.get("preferred_date") or None,
            preferred_time_slot=data.get("preferred_time_slot", ""),
            consultation_price=consultation_price,
            is_first_free=is_free,
        )

        booking.save()
        temp_uploads = _normalize_temp_uploads(data.get("temp_uploads", {}))
        first_photo = temp_uploads["photo"][0] if temp_uploads["photo"] else None
        first_video = temp_uploads["video"][0] if temp_uploads["video"] else None
        first_document = temp_uploads["document"][0] if temp_uploads["document"] else None
        _attach_temp_file(
            booking,
            first_photo.get("path") if isinstance(first_photo, dict) else first_photo,
            "photo",
        )
        _attach_temp_file(
            booking,
            first_video.get("path") if isinstance(first_video, dict) else first_video,
            "video",
        )
        _attach_temp_file(
            booking,
            first_document.get("path") if isinstance(first_document, dict) else first_document,
            "document",
        )
        booking.save(update_fields=["photo", "video", "document"])
        _create_attachments_from_temp_uploads(booking, temp_uploads)
        AdminNotification.objects.create(
            booking=booking,
            message=f"New consultation booking from {booking.full_name}.",
        )
        _send_custom_booking_confirmation_email(
            to_email=booking.email,
            customer_name=booking.full_name,
            booking_reference=f"CB-{booking.id:06d}",
            booking_type_label="Consultation Booking",
            team_name=_booking_team_name(booking.assigned_provider),
            preferred_date=booking.preferred_date,
            preferred_time=booking.preferred_time_slot,
            summary_lines=[
                f"Consultation type: {booking.consultation_type or '-'}",
                f"Property type: {booking.property_type or '-'}",
                f"Property size: {booking.property_size or '-'}",
                f"Consultation fee: {'Free first consultation' if booking.is_first_free else _format_currency_amount(booking.consultation_price, pricing.currency if pricing else 'SEK')}",
            ],
            next_steps=[
                "We will review your consultation request and confirm the suitable slot.",
                "If we need more project details, our team will contact you using the information you submitted.",
            ],
        )
        request.session.pop(BOOKING_SESSION_KEY, None)
        return redirect("electricity:booking_thank_you")

    is_free = _is_first_consultation(data.get("email"), data.get("phone"))
    pricing = _get_active_pricing()
    consultation_price = 0
    if not is_free and pricing:
        consultation_price = float(pricing.consultation_price)
    return render(
        request,
        "electricity/booking/step_7.html",
        {
            "form": form,
            "step": 7,
            "progress_percent": 100,
            "title": _("Review your request"),
            "data": data,
            "consultation_free": is_free,
            "consultation_price": consultation_price,
            "currency": pricing.currency if pricing else "SEK",
        },
    )


def booking_thank_you(request):
    return render(request, "electricity/booking/thank_you.html")


def legacy_consultation_booking_step(request, step):
    return redirect(f"/consultation-booking/step-{step}/")


def legacy_consultation_booking_thank_you(request):
    return redirect("/consultation-booking/thank-you/")


def _electrician_pricing_breakdown(data):
    pricing = _get_active_pricing()
    hourly_rate = 85
    transport_fee = 0
    currency = "SEK"
    rot_percent = 30.0
    if pricing:
        hourly_rate = float(pricing.hourly_rate_electrician or pricing.labor_rate or hourly_rate)
        transport_fee = float(pricing.transport_fee or 0)
        currency = pricing.currency or currency
        rot_percent = float(pricing.rot_percent or rot_percent)
    try:
        hours = int(data.get("hours") or 1)
    except (TypeError, ValueError):
        hours = 1
    hours = max(1, hours)
    arrival_window = data.get("arrival_window", "")
    multiplier = 2 if arrival_window in {
        "Evening (05:00 PM - 10:00 PM)",
        "Night (10:00 PM - 06:00 AM)",
    } else 1
    effective_hourly_rate = hourly_rate * multiplier
    minimum_callout = effective_hourly_rate
    additional_hours = max(hours - 1, 0)
    additional_total = additional_hours * effective_hourly_rate
    labor_total = minimum_callout + additional_total
    total_before_rot = labor_total + transport_fee
    use_rot = bool(data.get("use_rot")) and data.get("customer_type") == ElectricianBooking.CustomerType.PRIVATE
    rot_discount = labor_total * (rot_percent / 100) if use_rot else 0
    total = total_before_rot - rot_discount
    return {
        "hours": hours,
        "hourly_rate": hourly_rate,
        "effective_hourly_rate": effective_hourly_rate,
        "arrival_multiplier": multiplier,
        "transport_fee": transport_fee,
        "rot_percent": rot_percent,
        "rot_requested": use_rot,
        "rot_discount": rot_discount,
        "minimum_callout": minimum_callout,
        "additional_hours": additional_hours,
        "additional_total": additional_total,
        "labor_total": labor_total,
        "total_before_rot": total_before_rot,
        "total": total,
        "currency": currency,
    }


def _electrician_pricing_from_booking(booking):
    hourly_rate = float(booking.hourly_rate_snapshot or 0)
    transport_fee = float(booking.transport_fee_snapshot or 0)
    rot_percent = float(booking.rot_percent_snapshot or 0)
    hours = max(int(booking.hours or 1), 1)
    multiplier = 2 if booking.arrival_window in {
        "Evening (05:00 PM - 10:00 PM)",
        "Night (10:00 PM - 06:00 AM)",
    } else 1
    effective_hourly_rate = hourly_rate * multiplier
    additional_hours = max(hours - 1, 0)
    additional_total = additional_hours * effective_hourly_rate
    labor_total = effective_hourly_rate + additional_total
    total_before_rot = labor_total + transport_fee
    rot_discount = labor_total * (rot_percent / 100) if booking.rot_requested else 0
    return {
        "hours": hours,
        "hourly_rate": hourly_rate,
        "effective_hourly_rate": effective_hourly_rate,
        "arrival_multiplier": multiplier,
        "transport_fee": transport_fee,
        "rot_percent": rot_percent,
        "rot_requested": bool(booking.rot_requested),
        "rot_discount": rot_discount,
        "minimum_callout": effective_hourly_rate,
        "additional_hours": additional_hours,
        "additional_total": additional_total,
        "labor_total": labor_total,
        "total_before_rot": total_before_rot,
        "total": float(booking.estimated_total or 0),
        "currency": booking.currency or "SEK",
    }


def _electrician_receipt_context(booking=None, data=None):
    data = data or {}
    if booking:
        service_type = _electrician_service_type_label(booking.property_type)
        customer_type = booking.get_customer_type_display() or "-"
        city_line = " ".join(part for part in [booking.zip_code, booking.city] if part)
        location = ", ".join(part for part in [booking.street_address, city_line] if part) or "-"
        pricing = _electrician_pricing_from_booking(booking)
        hours = pricing["hours"]
        appointment_date = booking.preferred_date
        arrival_window = booking.arrival_window or "-"
        work_description = booking.work_description or "-"
    else:
        service_type = _electrician_service_type_label(data.get("service_type"))
        customer_type = dict(ElectricianBooking.CustomerType.choices).get(data.get("customer_type"), "-")
        city_line = " ".join(part for part in [data.get("zip_code", ""), data.get("city", "")] if part)
        location = ", ".join(part for part in [data.get("street_address", ""), city_line] if part) or "-"
        pricing = _electrician_pricing_breakdown(data)
        hours = pricing["hours"]
        appointment_date = data.get("preferred_date") or "-"
        arrival_window = data.get("arrival_window") or "-"
        work_description = data.get("work_description") or "-"

    return {
        "service_type": service_type,
        "customer_type": customer_type,
        "location": location,
        "appointment_date": appointment_date,
        "arrival_window": arrival_window,
        "hours": hours,
        "work_description": work_description,
        "pricing": pricing,
    }


def electrician_booking_step(request, step):
    if step < 1 or step > 8:
        return redirect("electricity:electrician_booking_step", step=1)

    data = _get_electrician_booking_data(request)
    errors = []
    pricing = _electrician_pricing_breakdown(data)

    if request.method == "POST":
        if step == 1:
            hours = request.POST.get("hours")
            work_description = request.POST.get("work_description", "").strip()
            access_confirm = request.POST.get("access_confirm")
            data.update(
                {
                    "hours": hours,
                    "work_description": work_description,
                    "access_confirm": access_confirm == "yes",
                }
            )
            if not hours:
                errors.append("Please select the number of hours.")
            if not work_description:
                errors.append("Please describe the work.")
            if access_confirm != "yes":
                errors.append("Please confirm access to the work area.")
            if not errors:
                _set_electrician_booking_data(request, data)
                return redirect("electricity:electrician_booking_step", step=2)
        elif step == 2:
            service_type = request.POST.get("service_type")
            data["service_type"] = service_type
            if not service_type:
                errors.append("Please select a service type.")
            if not errors:
                _set_electrician_booking_data(request, data)
                return redirect("electricity:electrician_booking_step", step=3)
        elif step == 3:
            street_address = request.POST.get("street_address", "").strip()
            zip_code = request.POST.get("zip_code", "").strip()
            city = request.POST.get("city", "").strip()
            customer_type = request.POST.get("customer_type")
            personal_id = request.POST.get("personal_id", "").strip()
            full_name = request.POST.get("full_name", "").strip()
            phone = request.POST.get("phone", "").strip()
            email = request.POST.get("email", "").strip()
            company_name = request.POST.get("company_name", "").strip()
            organization_number = request.POST.get("organization_number", "").strip()
            contact_confirm = request.POST.get("contact_confirm")
            data.update(
                {
                    "street_address": street_address,
                    "zip_code": zip_code,
                    "city": city,
                    "customer_type": customer_type,
                    "personal_id": personal_id,
                    "full_name": full_name,
                    "phone": phone,
                    "email": email,
                    "company_name": company_name,
                    "organization_number": organization_number,
                    "contact_confirm": contact_confirm == "yes",
                }
            )
            if not street_address:
                errors.append("Street address is required.")
            if not zip_code:
                errors.append("Postal code is required.")
            if not city:
                errors.append("City is required.")
            if not customer_type:
                errors.append("Please choose a customer type.")
            if customer_type == "business":
                if not company_name:
                    errors.append("Company name is required.")
                if not organization_number:
                    errors.append("Organization number is required.")
                if not email:
                    errors.append("Email address is required.")
            else:
                if not personal_id:
                    errors.append("Personal ID number is required.")
                elif not re.fullmatch(r"\d{8}-\d{4}", personal_id):
                    errors.append("Please enter your personal ID in the format yyyymmdd-xxxx.")
                if not full_name:
                    errors.append("Full name is required.")
                if not phone:
                    errors.append("Phone number is required.")
                if not email:
                    errors.append("Email address is required.")
            if contact_confirm != "yes":
                errors.append("Please confirm your contact details.")
            if not errors:
                _set_electrician_booking_data(request, data)
                return redirect("electricity:electrician_booking_step", step=4)
        elif step == 4:
            access_notes = request.POST.get("access_notes", "").strip()
            parking_info = request.POST.get("parking_info", "").strip()
            data.update({"access_notes": access_notes, "parking_info": parking_info})
            _set_electrician_booking_data(request, data)
            return redirect("electricity:electrician_booking_step", step=5)
        elif step == 5:
            additional_notes = request.POST.get("additional_notes", "").strip()
            data["additional_notes"] = additional_notes
            _set_electrician_booking_data(request, data)
            return redirect("electricity:electrician_booking_step", step=6)
        elif step == 6:
            preferred_date = request.POST.get("preferred_date", "")
            arrival_window = request.POST.get("arrival_window")
            data.update(
                {
                    "preferred_date": preferred_date,
                    "arrival_window": arrival_window,
                }
            )
            parsed_preferred_date = _parse_date(preferred_date)
            if not preferred_date:
                errors.append("Please select a preferred date.")
            elif not parsed_preferred_date:
                errors.append("Please select a valid date.")
            elif parsed_preferred_date < timezone.localdate():
                errors.append("Please choose a date from today onward.")
            if not arrival_window:
                errors.append("Please select an arrival window.")
            if not errors:
                _set_electrician_booking_data(request, data)
                return redirect("electricity:electrician_booking_step", step=7)
        elif step == 7:
            pricing_ack = request.POST.get("pricing_ack")
            use_rot = request.POST.get("use_rot")
            data["pricing_ack"] = pricing_ack == "yes"
            data["use_rot"] = use_rot == "yes" and data.get("customer_type") == ElectricianBooking.CustomerType.PRIVATE
            if pricing_ack != "yes":
                errors.append("Please acknowledge the pricing estimate.")
            if not errors:
                _set_electrician_booking_data(request, data)
                return redirect("electricity:electrician_booking_step", step=8)
        elif step == 8:
            preferred_date = _parse_date(data.get("preferred_date"))
            confirm_info = request.POST.get("confirm_info")
            accept_terms = request.POST.get("accept_terms")
            data.update(
                {
                    "confirm_info": confirm_info == "yes",
                    "accept_terms": accept_terms == "yes",
                }
            )
            if not preferred_date:
                errors.append("Please select a valid date.")
            elif preferred_date < timezone.localdate():
                errors.append("Please choose a date from today onward.")
            if confirm_info != "yes":
                errors.append("Please confirm the booking information.")
            if accept_terms != "yes":
                errors.append("Please accept the Terms of Service.")
            if not errors:
                pricing = _electrician_pricing_breakdown(data)
                additional_notes = data.get("additional_notes", "")
                identity_notes = []
                if data.get("customer_type") == ElectricianBooking.CustomerType.BUSINESS:
                    if data.get("company_name"):
                        identity_notes.append(f"Company name: {data.get('company_name')}")
                    if data.get("organization_number"):
                        identity_notes.append(
                            f"Organization number: {data.get('organization_number')}"
                        )
                else:
                    if data.get("personal_id"):
                        identity_notes.append(f"Personal ID: {data.get('personal_id')}")
                if identity_notes:
                    additional_notes = "\n".join(
                        part for part in [additional_notes, *identity_notes] if part
                    )
                booking = ElectricianBooking.objects.create(
                    customer_type=data.get("customer_type") or ElectricianBooking.CustomerType.PRIVATE,
                    full_name=data.get("company_name") or data.get("full_name", ""),
                    email=data.get("email", ""),
                    phone=data.get("phone", ""),
                    street_address=data.get("street_address", ""),
                    city=data.get("city", ""),
                    zip_code=data.get("zip_code", ""),
                    property_type=data.get("property_type") or data.get("service_type", ""),
                    work_description=data.get("work_description", ""),
                    access_notes=data.get("access_notes", ""),
                    parking_info=data.get("parking_info", ""),
                    additional_notes=additional_notes,
                    hours=pricing["hours"],
                    hourly_rate_snapshot=pricing["hourly_rate"],
                    transport_fee_snapshot=pricing["transport_fee"],
                    rot_requested=pricing["rot_requested"],
                    rot_percent_snapshot=pricing["rot_percent"] if pricing["rot_requested"] else 0,
                    estimated_total=pricing["total"],
                    preferred_date=_parse_date(data.get("preferred_date")),
                    arrival_window=data.get("arrival_window", ""),
                    currency=pricing["currency"],
                )
                AdminNotification.objects.create(
                    message=f"New electrician booking from {booking.full_name}.",
                )
                _send_custom_booking_confirmation_email(
                    to_email=booking.email,
                    customer_name=booking.full_name,
                    booking_reference=f"RWM-{booking.id:06d}",
                    booking_type_label="Electrician Booking",
                    team_name=_booking_team_name(booking.assigned_provider),
                    preferred_date=booking.preferred_date,
                    preferred_time=booking.arrival_window,
                    summary_lines=[
                        f"Service type: {_electrician_service_type_label(booking.property_type)}",
                        f"Service address: {', '.join(part for part in [booking.street_address, booking.zip_code, booking.city] if part) or '-'}",
                        f"Estimated duration: {booking.hours} hour(s)",
                        f"Estimated total: {_format_currency_amount(booking.estimated_total, booking.currency or 'SEK')}",
                    ],
                    next_steps=[
                        "Our dispatch team will review your requested arrival window.",
                        "You will be contacted if we need access details or scheduling adjustments.",
                    ],
                )
                request.session.pop(ELECTRICIAN_BOOKING_SESSION_KEY, None)
                request.session["electrician_booking_id"] = booking.id
                request.session["electrician_booking_reference"] = f"RWM-{booking.id:06d}"
                return redirect("electricity:electrician_booking_thank_you")

        if errors:
            _set_electrician_booking_data(request, data)

    pricing = _electrician_pricing_breakdown(data)
    progress = int((step / 8) * 100)
    return render(
        request,
        f"electricity/electrician_booking/step_{step}.html",
        {
            "step": step,
            "progress_percent": progress,
            "data": data,
            "errors": errors,
            "pricing": pricing,
        },
    )


def electrician_booking_thank_you(request):
    reference = request.session.get("electrician_booking_reference", "RWM-000000")
    booking_id = request.session.get("electrician_booking_id")
    booking = ElectricianBooking.objects.filter(pk=booking_id).first() if booking_id else None
    data = _get_electrician_booking_data(request)
    receipt = _electrician_receipt_context(booking=booking, data=data)
    return render(
        request,
        "electricity/electrician_booking/thank_you.html",
        {
            "reference": reference,
            "booking": booking,
            "data": data,
            "pricing": receipt["pricing"],
            "receipt": receipt,
        },
    )


def service_booking_calendar(request, pk):
    booking = ServiceBooking.objects.filter(pk=pk).first()
    if not booking:
        raise Http404("Booking not found")

    start_date = booking.preferred_date or datetime.date.today()
    start_dt = booking.start_at
    end_dt = booking.end_at
    if not start_dt or not end_dt:
        start_time = _parse_time(booking.preferred_time_slot)
        if start_time:
            start_dt = datetime.datetime.combine(start_date, start_time)
            end_dt = start_dt + datetime.timedelta(hours=1)
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt)
                end_dt = timezone.make_aware(end_dt)

    if start_dt and end_dt:
        dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
        dtend = end_dt.strftime("%Y%m%dT%H%M%S")
        dtstart_line = f"DTSTART:{dtstart}"
        dtend_line = f"DTEND:{dtend}"
    else:
        dtstart_line = f"DTSTART;VALUE=DATE:{start_date.strftime('%Y%m%d')}"
        dtend_line = f"DTEND;VALUE=DATE:{(start_date + datetime.timedelta(days=1)).strftime('%Y%m%d')}"

    summary = f"Service Booking {booking.id}"
    description = f"Service booking for {booking.full_name} ({booking.email})."
    ics = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//RWM EL//Service Booking//EN",
            "BEGIN:VEVENT",
            dtstart_line,
            dtend_line,
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    response = HttpResponse(ics, content_type="text/calendar")
    response["Content-Disposition"] = f'attachment; filename="service-booking-{booking.id}.ics"'
    return response


def service_booking_slots(request):
    if not _ensure_zip_verified(request, "service"):
        return JsonResponse({"slots": []})
    date_value = request.GET.get("date", "")
    for_date = _parse_date(date_value)
    data = _get_service_booking_data(request)
    if not data.get("pricing_type"):
        data["pricing_type"] = ServiceBooking.PricingType.FIXED
    if not data.get("hourly_hours"):
        data["hourly_hours"] = 1
    pricing_type = (data.get("pricing_type") or ServiceBooking.PricingType.FIXED).lower()
    hours_param = request.GET.get("hours", "")
    if not for_date:
        return JsonResponse({"slots": []})
    try:
        if pricing_type == ServiceBooking.PricingType.HOURLY:
            duration_minutes = _service_booking_duration_minutes(data, hours_param)
        else:
            duration_minutes = _service_duration_minutes(data.get("services", []))
    except ValidationError:
        return JsonResponse({"slots": []})
    if not duration_minutes:
        # Fallback preview window to show availability even if duration is not finalized yet.
        duration_minutes = 60
    zip_code = request.session.get(ZIP_CHECK_SESSION_KEY, {}).get("service", "")
    slots = _format_slots(zip_code, for_date, duration_minutes)
    return JsonResponse({"slots": slots})


def service_booking_step(request, step):
    if not _ensure_zip_verified(request, "service"):
        return redirect("electricity:zip_check", flow="service")
    if step < 1 or step > 12:
        return redirect("electricity:service_booking_step", step=1)

    data = _get_service_booking_data(request)
    titles = {
        1: _("Start Your Booking"),
        2: _("Where will the work be done?"),
        3: _("Tell us about the property"),
        4: _("What do you need help with?"),
        5: _("Describe the work"),
        6: _("Finalize Schedule & Cost"),
        7: _("Schedule & Pricing"),
        8: _("Billing & Documentation"),
        9: _("Apartment & BRF Details"),
        10: _("Visual Documentation"),
        11: _("Final Review"),
        12: _("Booking Received"),
    }
    subtitles = {
        1: _("Account & Contact"),
        2: _("Location Details"),
        3: _("Property Details"),
        4: _("Service Selection"),
        5: _("Work Summary"),
        6: _("Schedule & Pricing"),
        7: _("Pricing & Savings"),
        8: _("Identity & Billing"),
        9: _("Association Details"),
        10: _("Files & Media"),
        11: _("Confirm & Submit"),
        12: _("Confirmation"),
    }
    descriptions = {
        1: _(
            "First, we need to know who we are working with to provide the correct pricing and tax options."
        ),
        2: _("We need your exact location for compliance and technician dispatching."),
        3: _("Engineering details help us prepare the right equipment."),
        4: _("Select all services that apply to your request."),
        5: _("The more detail you share, the better we can prepare."),
        6: _("Choose your primary and alternative time windows."),
        7: _("Confirm your pricing options and savings."),
        8: _("Provide billing identity and documentation details."),
        9: _("Add association details for multi-unit properties."),
        10: _("Upload photos of the area or existing electrical cabinet."),
        11: _("Please confirm your appointment details and secure your booking."),
        12: _("Your booking is confirmed."),
    }

    errors = []
    if request.method == "POST":
        if step == 1:
            data["account_type"] = request.POST.get("account_type", "")
            data["full_name"] = request.POST.get("full_name", "").strip()
            data["email"] = request.POST.get("email", "").strip()
            data["phone"] = request.POST.get("phone", "").strip()
            data["zip_code"] = request.session.get(ZIP_CHECK_SESSION_KEY, {}).get("service", "")
            if not data["account_type"]:
                errors.append("Please choose who the booking is for.")
            if not data["full_name"]:
                errors.append("Full name is required.")
            if not data["email"]:
                errors.append("Email address is required.")
        elif step == 2:
            data["street_address"] = request.POST.get("street_address", "").strip()
            data["city"] = request.POST.get("city", "").strip()
            data["region"] = request.POST.get("region", "").strip()
            data["country"] = request.POST.get("country", "").strip() or "Sweden"
            if not data["street_address"]:
                errors.append("Street address is required.")
            if not data["city"]:
                errors.append("City is required.")
            if not data["region"]:
                errors.append("Region is required.")
        elif step == 3:
            data["property_type"] = request.POST.get("property_type", "").strip()
            data["year_built"] = request.POST.get("year_built", "").strip()
            data["property_size"] = request.POST.get("property_size", "").strip()
            data["system_upgraded"] = bool(request.POST.get("system_upgraded"))
            if not data["property_type"]:
                errors.append("Property type is required.")
            if not data["year_built"]:
                errors.append("Year of construction is required.")
        elif step == 4:
            data["pricing_type"] = request.POST.get("pricing_type", ServiceBooking.PricingType.FIXED)
            services = request.POST.getlist("services")
            if data["pricing_type"] == ServiceBooking.PricingType.HOURLY:
                data["services"] = []
                data["service_names"] = ""
            else:
                data["services"] = services
                if not services:
                    errors.append("Please select at least one service.")
                else:
                    eligible = _eligible_services().filter(id__in=services)
                    if eligible.count() != len(services):
                        errors.append("Selected services must include price and duration.")
                    service_names = list(eligible.values_list("title", flat=True))
                    data["service_names"] = ", ".join(service_names)
        elif step == 5:
            data["work_description"] = request.POST.get("work_description", "").strip()
            data["urgent"] = bool(request.POST.get("urgent"))
            if not data["work_description"]:
                errors.append("Please describe the work.")
        elif step == 6:
            data["preferred_date"] = request.POST.get("preferred_date", "")
            data["preferred_time_slot"] = request.POST.get("preferred_time_slot", "")
            data["alt_date"] = request.POST.get("alt_date", "")
            data["alt_time_slot"] = request.POST.get("alt_time_slot", "")
            if (data.get("pricing_type") or ServiceBooking.PricingType.FIXED) == ServiceBooking.PricingType.HOURLY:
                data["hourly_hours"] = request.POST.get("hourly_hours", "").strip()
                try:
                    hours_val = int(data["hourly_hours"])
                except (TypeError, ValueError):
                    hours_val = 0
                if hours_val <= 0:
                    errors.append("Please select the estimated number of hours.")
            has_primary_choice = bool(data["preferred_date"] or data["preferred_time_slot"])
            if has_primary_choice and (not data["preferred_date"] or not data["preferred_time_slot"]):
                errors.append("Please select a primary date and time slot.")
            if not errors and has_primary_choice:
                try:
                    duration_minutes = _service_booking_duration_minutes(data)
                except ValidationError as exc:
                    errors.append(str(exc))
                else:
                    zip_code = request.session.get(ZIP_CHECK_SESSION_KEY, {}).get("service", "")
                    data["zip_code"] = zip_code
                    preferred_date = _parse_date(data.get("preferred_date"))
                    preferred_time = _parse_time(data.get("preferred_time_slot"))
                    if not preferred_date or not preferred_time:
                        errors.append("Please select a valid date and start time.")
                    else:
                        slots = _available_slots_for_zip(zip_code, preferred_date, duration_minutes)
                        slot_labels = {slot.time().strftime("%H:%M") for slot in slots}
                        if preferred_time.strftime("%H:%M") not in slot_labels:
                            provider, earliest = _earliest_availability_for_zip(
                                zip_code, duration_minutes, preferred_date
                            )
                            if earliest:
                                provider_name = provider.display_name if provider else "a provider"
                                minutes = int((earliest - timezone.now()).total_seconds() // 60)
                                errors.append(
                                    f"No providers are available at that time. "
                                    f"Earliest availability with {provider_name} is {earliest:%Y-%m-%d %H:%M} "
                                    f"({max(minutes, 0)} minutes from now)."
                                )
                            else:
                                errors.append("No available providers for the selected date and duration.")
        elif step == 7:
            data["rot_deduction"] = bool(request.POST.get("rot_deduction"))
            data["pricing_accept"] = bool(request.POST.get("pricing_accept"))
            _get_service_pricing_context(data)
            if not data["pricing_accept"]:
                errors.append("Please confirm the pricing breakdown.")
        elif step == 8:
            data["billing_type"] = request.POST.get("billing_type", "")
            data["personal_id"] = request.POST.get("personal_id", "").strip()
            data["organization_number"] = request.POST.get("organization_number", "").strip()
            data["company_name"] = request.POST.get("company_name", "").strip()
            if not data["billing_type"]:
                errors.append("Please choose a billing type.")
            if data["billing_type"] == "private" and not data["personal_id"]:
                errors.append("Personal identity number is required for private billing.")
            if data["billing_type"] == "business" and not data["organization_number"]:
                errors.append("Organization number is required for business billing.")
            if not data["company_name"]:
                errors.append("Full legal name is required.")
        elif step == 9:
            data["brf_property"] = bool(request.POST.get("brf_property"))
            data["brf_name"] = request.POST.get("brf_name", "").strip()
            data["apartment_number"] = request.POST.get("apartment_number", "").strip()
            if data["brf_property"] and not data["brf_name"]:
                errors.append("BRF name is required when BRF is selected.")
            if data["brf_property"] and not data["apartment_number"]:
                errors.append("Apartment number is required when BRF is selected.")
        elif step == 10:
            saved = _save_service_uploads(request)
            data["uploads"] = data.get("uploads", []) + saved
        elif step == 11:
            try:
                duration_minutes = _service_booking_duration_minutes(data)
            except ValidationError as exc:
                errors.append(str(exc))
                duration_minutes = None
            preferred_date = _parse_date(data.get("preferred_date"))
            preferred_time = _parse_time(data.get("preferred_time_slot"))
            start_at = _combine_date_time(preferred_date, preferred_time) if preferred_date and preferred_time else None
            end_at = start_at + datetime.timedelta(minutes=duration_minutes) if start_at and duration_minutes else None
            zip_code = data.get("zip_code") or request.session.get(ZIP_CHECK_SESSION_KEY, {}).get("service", "")
            if not start_at or not end_at:
                errors.append("Please select a valid start time.")
            assigned_provider = None
            if start_at and end_at and zip_code:
                assigned_provider = _find_provider_for_slot(zip_code, start_at, end_at)
                if not assigned_provider:
                    provider, earliest = _earliest_availability_for_zip(zip_code, duration_minutes, preferred_date)
                    if earliest:
                        provider_name = provider.display_name if provider else "a provider"
                        errors.append(
                            f"No providers are available at the selected time. "
                            f"Earliest availability with {provider_name} is {earliest:%Y-%m-%d %H:%M}."
                        )
                    else:
                        errors.append("No available providers for the selected date and duration.")

            if errors:
                _set_service_booking_data(request, data)
                cost_context = _get_service_pricing_context(data)
                context = {
                    "step": step,
                    "progress_percent": int((step / 12) * 100),
                    "title": titles.get(step),
                    "subtitle": subtitles.get(step),
                    "description": descriptions.get(step),
                    "data": data,
                    "errors": errors,
                    **cost_context,
                }
                return render(request, f"electricity/service_booking/step_{step}.html", context)

            try:
                pricing_context = _get_service_pricing_context(data)
                booking = ServiceBooking.objects.create(
                    account_type=data.get("account_type") or ServiceBooking.AccountType.PRIVATE,
                    full_name=data.get("full_name", ""),
                    email=data.get("email", ""),
                    phone=data.get("phone", ""),
                    street_address=data.get("street_address", ""),
                    city=data.get("city", ""),
                    region=data.get("region", ""),
                    country=data.get("country", "Sweden"),
                    property_type=data.get("property_type", ""),
                    year_built=data.get("year_built", ""),
                    property_size=data.get("property_size", ""),
                    system_upgraded=bool(data.get("system_upgraded")),
                    services=data.get("services", []),
                    work_description=data.get("work_description", ""),
                    urgent=bool(data.get("urgent")),
                    pricing_type=data.get("pricing_type") or ServiceBooking.PricingType.FIXED,
                    hourly_hours=int(data.get("hourly_hours") or 1),
                    hourly_rate_snapshot=pricing_context.get("hourly_rate_electrician") or 0,
                    fixed_services_total=pricing_context.get("fixed_services_total") or 0,
                    preferred_date=_parse_date(data.get("preferred_date")),
                    preferred_time_slot=data.get("preferred_time_slot", ""),
                    alt_date=_parse_date(data.get("alt_date")),
                    alt_time_slot=data.get("alt_time_slot", ""),
                    zip_code=zip_code or "",
                    duration_minutes=duration_minutes or 0,
                    start_at=start_at,
                    end_at=end_at,
                    labor_rate=data.get("labor_rate") or 0,
                    transport_fee=data.get("transport_fee") or 0,
                    base_fee=data.get("base_fee") or 0,
                    service_fee_total=data.get("service_fee_total") or 0,
                    night_rate=data.get("night_rate") or 0,
                    currency=data.get("currency") or "SEK",
                    promo_code=data.get("promo_code", ""),
                    rot_deduction=bool(data.get("rot_deduction")),
                    estimated_total=data.get("estimated_total") or 0,
                    billing_type=data.get("billing_type", ""),
                    personal_id=data.get("personal_id", ""),
                    organization_number=data.get("organization_number", ""),
                    company_name=data.get("company_name", ""),
                    brf_property=bool(data.get("brf_property")),
                    brf_name=data.get("brf_name", ""),
                    apartment_number=data.get("apartment_number", ""),
                    uploads=data.get("uploads", []),
                    assigned_provider=assigned_provider,
                    status=ServiceBooking.Status.SCHEDULED if assigned_provider else ServiceBooking.Status.PENDING,
                )
            except ValidationError:
                errors.append("Selected time overlaps with another booking. Please choose another slot.")
                _set_service_booking_data(request, data)
                cost_context = _get_service_pricing_context(data)
                context = {
                    "step": step,
                    "progress_percent": int((step / 12) * 100),
                    "title": titles.get(step),
                    "subtitle": subtitles.get(step),
                    "description": descriptions.get(step),
                    "data": data,
                    "errors": errors,
                    **cost_context,
                }
                return render(request, f"electricity/service_booking/step_{step}.html", context)
            AdminNotification.objects.create(
                service_booking=booking,
                message=f"New service booking from {booking.full_name}.",
            )
            _send_custom_booking_confirmation_email(
                to_email=booking.email,
                customer_name=booking.full_name,
                booking_reference=f"SB-{booking.id:06d}",
                booking_type_label="Service Booking",
                team_name=_booking_team_name(booking.assigned_provider),
                preferred_date=booking.preferred_date,
                preferred_time=booking.preferred_time_slot,
                summary_lines=[
                    f"Selected services: {', '.join(_service_titles_for_ids(booking.services)) or 'Custom service request'}",
                    f"Service address: {', '.join(part for part in [booking.street_address, booking.zip_code, booking.city] if part) or '-'}",
                    f"Pricing model: {booking.get_pricing_type_display()}",
                    f"Estimated total: {_format_currency_amount(booking.estimated_total, booking.currency or 'SEK')}",
                ],
                next_steps=[
                    "We will review provider availability for your selected time.",
                    "Your assigned team will contact you if any change is needed before arrival.",
                ],
            )
            request.session["service_booking_id"] = f"SB-{booking.id:06d}"
            request.session["service_booking_pk"] = booking.id
            request.session.pop(SERVICE_BOOKING_SESSION_KEY, None)
            return redirect("electricity:service_booking_step", step=12)

        _set_service_booking_data(request, data)
        if errors:
            cost_context = _get_service_pricing_context(data)
            context = {
                "step": step,
                "progress_percent": int((step / 12) * 100),
                "title": titles.get(step),
                "subtitle": subtitles.get(step),
                "description": descriptions.get(step),
                "data": data,
                "errors": errors,
                **cost_context,
            }
            if step == 4:
                context["services"] = _eligible_services().order_by("order", "title")
            if step == 6:
                zip_code = request.session.get(ZIP_CHECK_SESSION_KEY, {}).get("service", "")
                preferred_date = _parse_date(data.get("preferred_date"))
                alt_date = _parse_date(data.get("alt_date"))
                try:
                    duration_minutes = _service_booking_duration_minutes(data)
                except ValidationError:
                    duration_minutes = None
                duration_assumed = False
                duration_for_slots = duration_minutes
                if not duration_for_slots:
                    duration_for_slots = 60
                    duration_assumed = True
                if not preferred_date and duration_minutes:
                    earliest_provider, earliest = _earliest_availability_for_zip(
                        zip_code, duration_minutes
                    )
                    if earliest:
                        preferred_date = earliest.date()
                        data["preferred_date"] = preferred_date.isoformat()
                context["available_slots"] = (
                    _format_slots(zip_code, preferred_date, duration_for_slots)
                    if preferred_date and duration_for_slots
                    else []
                )
                context["alt_available_slots"] = (
                    _format_slots(zip_code, alt_date, duration_for_slots)
                    if alt_date and duration_for_slots
                    else []
                )
                context["duration_assumed"] = duration_assumed
            if step == 12:
                context["booking_id"] = request.session.get("service_booking_id", "SB-000000")
            if step == 1:
                context["kicker"] = _("ONBOARDING")
                context["note"] = _("Great choice! Let's start with your details.")
            return render(request, f"electricity/service_booking/step_{step}.html", context)
        return redirect("electricity:service_booking_step", step=step + 1)

    progress_percent = int((step / 12) * 100)
    cost_context = _get_service_pricing_context(data)
    context = {
        "step": step,
        "progress_percent": progress_percent,
        "title": titles.get(step),
        "subtitle": subtitles.get(step),
        "description": descriptions.get(step),
        "data": data,
        "errors": errors,
        **cost_context,
    }
    if step == 1:
        context["kicker"] = _("ONBOARDING")
        context["note"] = _("Great choice! Let's start with your details.")
    if step == 4:
        context["services"] = _eligible_services().order_by("order", "title")
    if step == 6:
        zip_code = request.session.get(ZIP_CHECK_SESSION_KEY, {}).get("service", "")
        preferred_date = _parse_date(data.get("preferred_date"))
        alt_date = _parse_date(data.get("alt_date"))
        try:
            duration_minutes = _service_booking_duration_minutes(data)
        except ValidationError:
            duration_minutes = None
        duration_assumed = False
        duration_for_slots = duration_minutes
        if not duration_for_slots:
            duration_for_slots = 60
            duration_assumed = True
        if not preferred_date and duration_minutes:
            earliest_provider, earliest = _earliest_availability_for_zip(
                zip_code, duration_minutes
            )
            if earliest:
                preferred_date = earliest.date()
                data["preferred_date"] = preferred_date.isoformat()
        context["available_slots"] = (
            _format_slots(zip_code, preferred_date, duration_for_slots)
            if preferred_date and duration_for_slots
            else []
        )
        context["alt_available_slots"] = (
            _format_slots(zip_code, alt_date, duration_for_slots)
            if alt_date and duration_for_slots
            else []
        )
        context["duration_assumed"] = duration_assumed
    if step == 12:
        context["booking_id"] = request.session.get("service_booking_id", "SB-000000")
        booking_pk = request.session.get("service_booking_pk")
        if booking_pk:
            booking = ServiceBooking.objects.filter(pk=booking_pk).first()
            if booking:
                context["booking"] = booking
                context["data"] = {
                    **data,
                    "preferred_date": booking.preferred_date,
                    "preferred_time_slot": booking.preferred_time_slot,
                }
    return render(request, f"electricity/service_booking/step_{step}.html", context)


def on_call_booking_step(request, step):
    if not _ensure_zip_verified(request, "on_call"):
        return redirect("electricity:zip_check", flow="on_call")
    if step < 1 or step > 4:
        return redirect("electricity:on_call_booking_step", step=1)

    data = _get_on_call_booking_data(request)
    errors = []
    titles = {
        1: _("On-Call Electrical Service"),
        2: _("Who is applying?"),
        3: _("Property & Risk Profile"),
        4: _("Finalize Your Registration"),
    }
    subtitles = {
        1: _("Coverage & Response"),
        2: _("Entity Selection & Organization Info"),
        3: _("Property Details"),
        4: _("Review & Submit"),
    }

    if request.method == "POST":
        if step == 1:
            data["coverage_times"] = request.POST.getlist("coverage_times")
            data["response_speed"] = request.POST.get("response_speed", "")
            data["coverage_scope"] = request.POST.getlist("coverage_scope")
            if not data["coverage_times"]:
                errors.append("Please choose at least one coverage window.")
            if not data["response_speed"]:
                errors.append("Please choose a response speed.")
            if not data["coverage_scope"]:
                errors.append("Please choose at least one coverage scope.")
        elif step == 2:
            data["entity_type"] = request.POST.get("entity_type", "")
            data["organization_name"] = request.POST.get("organization_name", "").strip()
            data["organization_number"] = request.POST.get("organization_number", "").strip()
            data["contact_person"] = request.POST.get("contact_person", "").strip()
            data["phone"] = request.POST.get("phone", "").strip()
            data["email"] = request.POST.get("email", "").strip()
            data["company_address"] = request.POST.get("company_address", "").strip()
            data["zip_code"] = request.POST.get("zip_code", "").strip()
            data["city"] = request.POST.get("city", "").strip()
            if not data["entity_type"]:
                errors.append("Please select the entity type.")
            if not data["organization_name"]:
                errors.append("Organization name is required.")
            if not data["organization_number"]:
                errors.append("Organization number is required.")
            if not data["contact_person"]:
                errors.append("Contact person is required.")
            if not data["phone"]:
                errors.append("Phone number is required.")
            if not data["email"]:
                errors.append("Email address is required.")
            else:
                try:
                    validate_email(data["email"])
                except ValidationError:
                    errors.append("Please provide a valid email address.")
            if not data["company_address"]:
                errors.append("Company address is required.")
            if not data["zip_code"]:
                errors.append("ZIP code is required.")
            if not data["city"]:
                errors.append("City is required.")
        elif step == 3:
            data["property_type"] = request.POST.get("property_type", "").strip()
            data["assets_count"] = request.POST.get("assets_count", "").strip()
            data["primary_region"] = request.POST.get("primary_region", "").strip()
            data["shared_critical_systems"] = bool(request.POST.get("shared_critical_systems"))
            if not data["property_type"]:
                errors.append("Property type is required.")
            if not data["assets_count"]:
                errors.append("Number of assets/properties is required.")
            if not data["primary_region"]:
                errors.append("Primary city/region is required.")
        elif step == 4:
            data["last_issue_date"] = request.POST.get("last_issue_date", "").strip()
            data["active_contract"] = bool(request.POST.get("active_contract"))
            data["recurring_issues"] = request.POST.get("recurring_issues", "").strip()
            data["additional_notes"] = request.POST.get("additional_notes", "").strip()
            data["emergency_hours"] = request.POST.get("emergency_hours", "").strip()
            if not data["recurring_issues"]:
                errors.append("Please describe the recurring electrical issues.")
            try:
                emergency_hours = int(data.get("emergency_hours") or 0)
            except (TypeError, ValueError):
                emergency_hours = 0
            if emergency_hours <= 0:
                errors.append("Please enter the estimated emergency hours.")

            if not errors:
                pricing = _get_active_pricing()
                hourly_rate_emergency = float(pricing.hourly_rate_emergency) if pricing else 0
                estimated_total = hourly_rate_emergency * emergency_hours
                site_address = ", ".join(
                    [p for p in [data.get("company_address", ""), data.get("city", "")] if p]
                )
                booking = OnCallBooking.objects.create(
                    entity_type=data.get("entity_type", ""),
                    organization_name=data.get("organization_name", ""),
                    organization_number=data.get("organization_number", ""),
                    contact_person=data.get("contact_person", ""),
                    phone=data.get("phone", ""),
                    email=data.get("email", ""),
                    company_address=data.get("company_address", ""),
                    zip_code=data.get("zip_code", ""),
                    city=data.get("city", ""),
                    coverage_times=data.get("coverage_times", []),
                    response_speed=data.get("response_speed", ""),
                    coverage_scope=data.get("coverage_scope", []),
                    property_type=data.get("property_type", ""),
                    assets_count=int(data.get("assets_count") or 0),
                    primary_region=data.get("primary_region", ""),
                    shared_critical_systems=bool(data.get("shared_critical_systems")),
                    last_issue_date=_parse_date(data.get("last_issue_date")),
                    active_contract=bool(data.get("active_contract")),
                    recurring_issues=data.get("recurring_issues", ""),
                    additional_notes=data.get("additional_notes", ""),
                    emergency_hours=emergency_hours,
                    hourly_rate_emergency_snapshot=hourly_rate_emergency,
                    estimated_total=estimated_total,
                    site_address=site_address,
                )
                AdminNotification.objects.create(
                    on_call_booking=booking,
                    message=f"New on-call booking from {booking.organization_name or booking.contact_person}.",
                )
                booking_id = f"OC-{booking.id:06d}"
                _send_custom_booking_confirmation_email(
                    to_email=booking.email,
                    customer_name=booking.contact_person or booking.organization_name,
                    booking_reference=booking_id,
                    booking_type_label="On-Call Booking",
                    team_name=_booking_team_name(booking.assigned_provider),
                    summary_lines=[
                        f"Organization: {booking.organization_name or '-'}",
                        f"Coverage times: {', '.join(_on_call_coverage_time_labels().get(item, item) for item in (booking.coverage_times or [])) or '-'}",
                        f"Coverage scope: {', '.join(_on_call_coverage_scope_labels().get(item, item) for item in (booking.coverage_scope or [])) or '-'}",
                        f"Estimated total: {_format_currency_amount(estimated_total, pricing.currency if pricing else 'SEK')}",
                    ],
                    next_steps=[
                        "Our team will review your requested coverage and response profile.",
                        "We will contact you to finalize activation details if needed.",
                    ],
                )
                request.session["on_call_booking_id"] = booking_id
                request.session["on_call_booking_success"] = {
                    "booking_id": booking_id,
                    "organization_name": booking.organization_name or booking.contact_person,
                    "contact_person": booking.contact_person,
                    "site_address": booking.site_address,
                    "coverage_times": list(booking.coverage_times or []),
                    "coverage_scope": list(booking.coverage_scope or []),
                    "response_speed": booking.response_speed,
                    "property_type": booking.property_type,
                    "assets_count": booking.assets_count,
                    "emergency_hours": booking.emergency_hours,
                    "estimated_total": estimated_total,
                    "currency": pricing.currency if pricing else "SEK",
                }
                request.session.pop(ON_CALL_BOOKING_SESSION_KEY, None)
                return redirect("electricity:on_call_booking_step", step=4)

        _set_on_call_booking_data(request, data)
        if errors:
            pricing = _get_active_pricing()
            hourly_rate_emergency = float(pricing.hourly_rate_emergency) if pricing else 0
            currency = pricing.currency if pricing else "SEK"
            try:
                emergency_hours = int(data.get("emergency_hours") or 0)
            except (TypeError, ValueError):
                emergency_hours = 0
            context = {
                "step": step,
                "progress_percent": int((step / 4) * 100),
                "title": titles.get(step),
                "subtitle": subtitles.get(step),
                "errors": errors,
                "data": data,
                "hourly_rate_emergency": hourly_rate_emergency,
                "emergency_estimated_total": hourly_rate_emergency * emergency_hours,
                "currency": currency,
            }
            return render(request, f"electricity/on_call_booking/step_{step}.html", context)
        return redirect("electricity:on_call_booking_step", step=step + 1)

    progress_percent = int((step / 4) * 100)
    success_payload = request.session.pop("on_call_booking_success", None) if step == 4 else None
    submitted = bool(success_payload)
    context = {
        "step": step,
        "progress_percent": progress_percent,
        "title": titles.get(step),
        "subtitle": subtitles.get(step),
        "data": data,
        "errors": errors,
        "submitted": submitted,
        "booking_id": (success_payload or {}).get(
            "booking_id",
            request.session.get("on_call_booking_id", "OC-000000"),
        ),
        "redirect_after_submit_url": reverse("electricity:services"),
    }
    if step == 4:
        pricing = _get_active_pricing()
        hourly_rate_emergency = float(pricing.hourly_rate_emergency) if pricing else 0
        currency = pricing.currency if pricing else "SEK"
        to_discuss_label = _("To discuss")
        try:
            emergency_hours = int(data.get("emergency_hours") or 0)
        except (TypeError, ValueError):
            emergency_hours = 0
        entity_type_labels = dict(OnCallBooking.EntityType.choices)
        response_speed_labels = dict(OnCallBooking.ResponseSpeed.choices)
        coverage_time_labels = {
            "evenings": _("Evenings"),
            "nights": _("Nights"),
            "weekends": _("Weekends & holidays"),
        }
        coverage_scope_labels = {
            "power_outages": _("Power outages"),
            "fuse_boards": _("Fuse boards"),
            "common_areas": _("Common areas"),
            "critical_systems": _("Critical systems"),
            "general_faults": _("General faults"),
        }
        property_type_labels = {
            "commercial": _("Commercial"),
            "industrial": _("Industrial"),
            "mixed_use": _("Mixed Use"),
            "residential": _("Residential"),
        }
        selection_summary_rows = [
            {
                "label": _("Entity type"),
                "value": entity_type_labels.get(data.get("entity_type"), "-"),
            },
            {
                "label": _("Coverage times"),
                "value": ", ".join(
                    coverage_time_labels.get(item, item)
                    for item in (data.get("coverage_times") or [])
                ) or "-",
            },
            {
                "label": _("Response speed"),
                "value": response_speed_labels.get(data.get("response_speed"), "-"),
            },
            {
                "label": _("Coverage scope"),
                "value": ", ".join(
                    coverage_scope_labels.get(item, item)
                    for item in (data.get("coverage_scope") or [])
                ) or "-",
            },
            {
                "label": _("Property type"),
                "value": property_type_labels.get(data.get("property_type"), data.get("property_type") or "-"),
            },
            {
                "label": _("Assets count"),
                "value": str(data.get("assets_count") or "-"),
            },
        ]
        context["hourly_rate_emergency"] = hourly_rate_emergency
        context["emergency_estimated_total"] = hourly_rate_emergency * emergency_hours
        context["currency"] = currency
        context["pricing_display_label"] = to_discuss_label
        context["selection_summary_rows"] = selection_summary_rows
        if success_payload:
            summary = [
                {
                    "label": _("Organization"),
                    "value": success_payload.get("organization_name") or "-",
                },
                {
                    "label": _("Contact person"),
                    "value": success_payload.get("contact_person") or "-",
                },
                {
                    "label": _("Site address"),
                    "value": success_payload.get("site_address") or "-",
                },
                {
                    "label": _("Coverage times"),
                    "value": ", ".join(
                        coverage_time_labels.get(item, item)
                        for item in (success_payload.get("coverage_times") or [])
                    ) or "-",
                },
                {
                    "label": _("Coverage scope"),
                    "value": ", ".join(
                        coverage_scope_labels.get(item, item)
                        for item in (success_payload.get("coverage_scope") or [])
                    ) or "-",
                },
                {
                    "label": _("Response speed"),
                    "value": response_speed_labels.get(success_payload.get("response_speed"), "-"),
                },
                {
                    "label": _("Property type"),
                    "value": property_type_labels.get(
                        success_payload.get("property_type"),
                        success_payload.get("property_type") or "-",
                    ),
                },
                {
                    "label": _("Assets count"),
                    "value": str(success_payload.get("assets_count") or "-"),
                },
                {
                    "label": _("Estimated emergency hours"),
                    "value": str(success_payload.get("emergency_hours") or "-"),
                },
                {
                    "label": _("Estimated total"),
                    "value": to_discuss_label,
                },
            ]
            context["submitted_summary"] = summary
    return render(request, f"electricity/on_call_booking/step_{step}.html", context)


def _get_service_pricing_context(data):
    pricing = _get_active_pricing()
    pricing_type = (data.get("pricing_type") or ServiceBooking.PricingType.FIXED).lower()
    currency = pricing.currency if pricing else "SEK"
    rot_percent = float(pricing.rot_percent) if pricing else 0
    rot_value = 0
    promo_value = 0

    if pricing_type == ServiceBooking.PricingType.HOURLY:
        try:
            hours = int(data.get("hourly_hours") or 1)
        except (TypeError, ValueError):
            hours = 1
        hourly_rate = float(pricing.hourly_rate_electrician) if pricing else 0
        if not hourly_rate and pricing:
            hourly_rate = float(pricing.labor_rate)
        total = hours * hourly_rate
        data["estimated_total"] = total
        data["hourly_rate_electrician"] = hourly_rate
        data["fixed_services_total"] = 0
        data["labor_rate"] = hourly_rate
        data["transport_fee"] = 0
        data["base_fee"] = 0
        data["service_fee_total"] = 0
        data["night_rate"] = 0
        data["currency"] = currency
        return {
            "pricing_type": pricing_type,
            "hourly_hours": hours,
            "hourly_rate_electrician": hourly_rate,
            "fixed_services_total": 0,
            "labor_rate": hourly_rate,
            "transport_fee": 0,
            "base_fee": 0,
            "service_fee_total": 0,
            "night_rate": 0,
            "rot_percent": rot_percent,
            "rot_value": 0,
            "promo_value": promo_value,
            "cost_total": total,
            "currency": currency,
        }

    service_ids = data.get("services", [])
    services = ElectricalService.objects.filter(id__in=service_ids)
    fixed_total = sum(float(s.price) for s in services)
    data["estimated_total"] = fixed_total
    data["fixed_services_total"] = fixed_total
    data["labor_rate"] = 0
    data["transport_fee"] = 0
    data["base_fee"] = 0
    data["service_fee_total"] = 0
    data["night_rate"] = 0
    data["currency"] = currency
    return {
        "pricing_type": pricing_type,
        "hourly_hours": int(data.get("hourly_hours") or 0),
        "hourly_rate_electrician": float(pricing.hourly_rate_electrician) if pricing else 0,
        "fixed_services_total": fixed_total,
        "labor_rate": 0,
        "transport_fee": 0,
        "base_fee": 0,
        "service_fee_total": 0,
        "night_rate": 0,
        "rot_percent": rot_percent,
        "rot_value": 0,
        "promo_value": promo_value,
        "cost_total": fixed_total,
        "currency": currency,
    }


def signup(request):
    if request.user.is_authenticated:
        return redirect("electricity:home")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("electricity:home")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def login_redirect(request):
    user = request.user
    if hasattr(user, "provider_profile"):
        return redirect("electricity:provider_dashboard")
    if user.is_superuser or user.is_staff or electricity_admin_site.has_permission(request):
        return redirect("electricity:dashboard")
    return redirect("electricity:home")


@login_required
def external_dashboard(request):
    user = request.user
    if not (user.is_superuser or user.is_staff or electricity_admin_site.has_permission(request)):
        return redirect("admin:login")

    app_config = apps.get_app_config("electricity")
    model_cards = []

    for model in app_config.get_models():
        model_name = model._meta.model_name
        manage_url = None
        if model_name == "electricalservice":
            manage_url = "electricity:dashboard_services"
        elif model_name == "consultationrequest":
            manage_url = "electricity:dashboard_requests"
        elif model_name == "consultationbooking":
            manage_url = "electricity:dashboard_bookings"
        elif model_name == "servicebooking":
            manage_url = "electricity:dashboard_service_bookings"
        elif model_name == "electricianbooking":
            manage_url = "electricity:dashboard_electrician_bookings"
        elif model_name == "oncallbooking":
            manage_url = "electricity:dashboard_on_call_bookings"
        elif model_name == "servicepricing":
            manage_url = "electricity:dashboard_pricing"
        elif model_name == "supportticket":
            manage_url = "electricity:dashboard_support_tickets"
        elif model_name == "acceptedzipcode":
            manage_url = "electricity:dashboard_zip_codes"
        elif model_name == "servicerequestoutsidearea":
            manage_url = "electricity:dashboard_outside_area_requests"
        elif model_name == "customerprofile":
            manage_url = "electricity:dashboard_profiles"
        elif model_name == "providerprofile":
            manage_url = "electricity:dashboard_providers"

        fields = [f for f in model._meta.fields if f.name != "id"]
        display_fields = [f for f in fields if f.get_internal_type() not in {"TextField", "JSONField"}]
        if not display_fields:
            display_fields = fields[:3]
        else:
            display_fields = display_fields[:3]

        order_field = "-id"
        if any(f.name == "created_at" for f in model._meta.fields):
            order_field = "-created_at"
        queryset = model.objects.all().order_by(order_field)[:6]

        model_cards.append(
            {
                "name": model._meta.verbose_name_plural.title(),
                "object_name": model._meta.object_name,
                "count": model.objects.count(),
                "fields": display_fields,
                "rows": queryset,
                "manage_url": manage_url,
            }
        )

    model_cards.sort(key=lambda item: item["name"])

    stats = {
        "services": ElectricalService.objects.count(),
        "requests": ConsultationRequest.objects.count(),
        "bookings": ConsultationBooking.objects.count(),
        "service_bookings": ServiceBooking.objects.count(),
        "electrician_bookings": ElectricianBooking.objects.count(),
        "on_call_bookings": OnCallBooking.objects.count(),
        "support_tickets": SupportTicket.objects.count(),
        "zip_codes": AcceptedZipCode.objects.count(),
        "outside_area": ServiceRequestOutsideArea.objects.count(),
        "total_models": len(model_cards),
    }
    notifications = AdminNotification.objects.order_by("-created_at")[:6]
    unread_count = AdminNotification.objects.filter(is_read=False).count()
    electrician_bookings = ElectricianBooking.objects.order_by("-created_at")[:6]

    return render(
        request,
        "electricity/dashboard.html",
        {
            "stats": stats,
            "model_cards": model_cards,
            "notifications": notifications,
            "unread_count": unread_count,
            "electrician_bookings": electrician_bookings,
        },
    )


@login_required
def admin_notifications_feed(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = AdminNotification.objects.order_by("-created_at")[:10]
    payload = [
        {
            "id": item.id,
            "message": item.message,
            "created_at": item.created_at.isoformat(),
            "is_read": item.is_read,
        }
        for item in items
    ]
    unread_count = AdminNotification.objects.filter(is_read=False).count()
    return JsonResponse({"unread_count": unread_count, "items": payload})


@login_required
def admin_notifications_mark_read(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    if request.method == "POST":
        AdminNotification.objects.filter(is_read=False).update(is_read=True)
    return redirect("electricity:dashboard")


def _require_dashboard_access(request):
    user = request.user
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return electricity_admin_site.has_permission(request)


def _dashboard_access_or_redirect(request):
    if _require_dashboard_access(request):
        return None
    return redirect("admin:login")


def _provider_access_or_redirect(request):
    if not request.user.is_authenticated:
        return redirect("electricity:login")
    if hasattr(request.user, "provider_profile"):
        return None
    return redirect("electricity:home")


@login_required
def dashboard_services(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = ElectricalService.objects.all().order_by("order", "title")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Electrical Services",
            "items": items,
            "fields": [
                "title",
                "service_fee",
                "base_fee",
                "hourly_rate",
                "night_rate",
                "transport_fee",
                "rot_percent",
                "currency",
                "is_active",
                "order",
            ],
            "create_url": "electricity:dashboard_services_add",
            "edit_url": "electricity:dashboard_services_edit",
            "delete_url": "electricity:dashboard_services_delete",
        },
    )


@login_required
def dashboard_services_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = ElectricalServiceForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_services")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add Electrical Service", "form": form, "back_url": "electricity:dashboard_services"},
    )


@login_required
def dashboard_services_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ElectricalService.objects.get(pk=pk)
    form = ElectricalServiceForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_services")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit Electrical Service", "form": form, "back_url": "electricity:dashboard_services"},
    )


@login_required
def dashboard_services_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ElectricalService.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_services")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete Electrical Service", "item": item, "back_url": "electricity:dashboard_services"},
    )


def dashboard_pricing(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = ServicePricing.objects.order_by("-created_at")
    context = {
        "title": "Pricing",
        "items": items,
        "fields": [
            "name",
            "hourly_rate_electrician",
            "hourly_rate_emergency",
            "consultation_price",
            "currency",
            "is_active",
            "created_at",
        ],
        "create_url": "electricity:dashboard_pricing_add",
        "edit_url": "electricity:dashboard_pricing_edit",
        "delete_url": "electricity:dashboard_pricing_delete",
    }
    return render(request, "electricity/dashboard/list.html", context)


def dashboard_pricing_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = ServicePricingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_pricing")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add Pricing", "form": form, "back_url": "electricity:dashboard_pricing"},
    )


def dashboard_pricing_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ServicePricing.objects.get(pk=pk)
    form = ServicePricingForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_pricing")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit Pricing", "form": form, "back_url": "electricity:dashboard_pricing"},
    )


def dashboard_pricing_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ServicePricing.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_pricing")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete Pricing", "item": item, "back_url": "electricity:dashboard_pricing"},
    )


@login_required
def dashboard_requests(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = ConsultationRequest.objects.all().order_by("-created_at")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Consultation Requests",
            "items": items,
            "fields": ["full_name", "phone", "email", "status", "created_at"],
            "create_url": "electricity:dashboard_requests_add",
            "edit_url": "electricity:dashboard_requests_edit",
            "delete_url": "electricity:dashboard_requests_delete",
        },
    )


@login_required
def dashboard_requests_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = ConsultationRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        AdminNotification.objects.create(
            consultation_request=item,
            message=f"New consultation request from {item.full_name}.",
        )
        return redirect("electricity:dashboard_requests")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add Consultation Request", "form": form, "back_url": "electricity:dashboard_requests"},
    )


@login_required
def dashboard_requests_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ConsultationRequest.objects.get(pk=pk)
    form = ConsultationRequestForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_requests")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit Consultation Request", "form": form, "back_url": "electricity:dashboard_requests"},
    )


@login_required
def dashboard_requests_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ConsultationRequest.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_requests")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete Consultation Request", "item": item, "back_url": "electricity:dashboard_requests"},
    )


@login_required
def dashboard_bookings(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = ConsultationBooking.objects.all().order_by("-created_at")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Consultation Bookings",
            "items": items,
            "fields": ["full_name", "consultation_type", "property_type", "urgent", "created_at"],
            "create_url": "electricity:dashboard_bookings_add",
            "edit_url": "electricity:dashboard_bookings_edit",
            "delete_url": "electricity:dashboard_bookings_delete",
            "assign_url": "electricity:dashboard_bookings_assign",
        },
      )


@login_required
def dashboard_service_bookings(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = ServiceBooking.objects.all().order_by("-created_at")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Service Bookings",
            "items": items,
            "fields": [
                "full_name",
                "account_type",
                "preferred_date",
                "preferred_time_slot",
                "assigned_provider",
                "status",
                "created_at",
            ],
            "create_url": "electricity:dashboard_service_bookings_add",
            "edit_url": "electricity:dashboard_service_bookings_edit",
            "delete_url": "electricity:dashboard_service_bookings_delete",
            "assign_url": "electricity:dashboard_service_bookings_assign",
        },
    )


@login_required
def dashboard_service_bookings_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = ServiceBookingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        AdminNotification.objects.create(
            service_booking=item,
            message=f"Service booking added from dashboard: {item.full_name}.",
        )
        return redirect("electricity:dashboard_service_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add Service Booking", "form": form, "back_url": "electricity:dashboard_service_bookings"},
    )


@login_required
def dashboard_service_bookings_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ServiceBooking.objects.get(pk=pk)
    form = ServiceBookingForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_service_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit Service Booking", "form": form, "back_url": "electricity:dashboard_service_bookings"},
    )


@login_required
def dashboard_service_bookings_assign(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    booking = ServiceBooking.objects.get(pk=pk)
    form = ServiceBookingAssignForm(request.POST or None, instance=booking)
    duration_minutes = booking.duration_minutes
    if not duration_minutes:
        try:
            duration_minutes = _service_duration_minutes(booking.services or [])
        except ValidationError:
            duration_minutes = 0
    start_time = _parse_time(booking.preferred_time_slot)
    start_at = booking.start_at or _combine_date_time(booking.preferred_date, start_time)
    end_at = booking.end_at
    if start_at and duration_minutes and not end_at:
        end_at = start_at + datetime.timedelta(minutes=duration_minutes)
    available_qs = ProviderProfile.objects.filter(is_active=True)
    if booking.zip_code:
        available_qs = available_qs.filter(zip_code=booking.zip_code)
    if start_at and end_at:
        available_ids = [
            provider.id
            for provider in available_qs
            if _provider_is_available(provider, start_at, end_at, exclude_booking_id=booking.id)
        ]
        available_qs = available_qs.filter(id__in=available_ids)
    form.fields["assigned_provider"].queryset = available_qs
    all_providers = ProviderProfile.objects.all().order_by("display_name")
    reasons = {}
    start_time = _parse_time(booking.preferred_time_slot)
    if not booking.preferred_date or not start_time:
        for provider in all_providers:
            reasons[provider.id] = {
                "available": False,
                "reason": "Missing preferred date/time on booking.",
            }
    elif not duration_minutes:
        for provider in all_providers:
            reasons[provider.id] = {"available": False, "reason": "Missing duration/services."}
    else:
        weekday = booking.preferred_date.weekday()
        shift_ids = set(
            ProviderShift.objects.filter(
                weekday=weekday,
                start_time__lte=start_time,
                end_time__gte=(datetime.datetime.combine(booking.preferred_date, start_time)
                               + datetime.timedelta(minutes=duration_minutes)).time(),
            ).values_list("provider_id", flat=True)
        )
        for provider in all_providers:
            if not provider.is_active:
                reasons[provider.id] = {"available": False, "reason": "Inactive provider."}
                continue
            if booking.zip_code and provider.zip_code != booking.zip_code:
                reasons[provider.id] = {"available": False, "reason": "ZIP code mismatch."}
                continue
            if provider.id not in shift_ids:
                reasons[provider.id] = {
                    "available": False,
                    "reason": "No shift coverage for the selected time.",
                }
                continue
            if start_at and end_at and not _provider_is_available(
                provider, start_at, end_at, exclude_booking_id=booking.id
            ):
                reasons[provider.id] = {
                    "available": False,
                    "reason": "Overlaps another service booking.",
                }
                continue
            reasons[provider.id] = {"available": True, "reason": "Available for the selected time."}
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        if updated.assigned_provider and start_at and end_at:
            if not _provider_is_available(updated.assigned_provider, start_at, end_at, exclude_booking_id=booking.id):
                form.add_error("assigned_provider", "Provider is not available for the full duration.")
                return render(
                    request,
                    "electricity/dashboard/form.html",
                    {"title": "Assign Provider", "form": form, "back_url": "electricity:dashboard_service_bookings"},
                )
        if updated.assigned_provider and updated.status == ServiceBooking.Status.PENDING:
            updated.status = ServiceBooking.Status.SCHEDULED
        if start_at and end_at:
            updated.start_at = start_at
            updated.end_at = end_at
            updated.duration_minutes = duration_minutes or updated.duration_minutes
        updated.save()
        return redirect("electricity:dashboard_service_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {
            "title": "Assign Provider",
            "form": form,
            "back_url": "electricity:dashboard_service_bookings",
            "provider_table": {
                "title": "Provider Availability",
                "rows": _provider_table_rows(all_providers, reasons),
            },
        },
    )


@login_required
def dashboard_service_bookings_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ServiceBooking.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_service_bookings")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete Service Booking", "item": item, "back_url": "electricity:dashboard_service_bookings"},
    )


@login_required
def dashboard_on_call_bookings(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = OnCallBooking.objects.all().order_by("-created_at")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "On-Call Bookings",
            "items": items,
            "fields": [
                "organization_name",
                "contact_person",
                "phone",
                "email",
                "city",
                "response_speed",
                "assigned_provider",
                "status",
                "created_at",
            ],
            "create_url": "electricity:dashboard_on_call_bookings_add",
            "edit_url": "electricity:dashboard_on_call_bookings_edit",
            "delete_url": "electricity:dashboard_on_call_bookings_delete",
            "assign_url": "electricity:dashboard_on_call_bookings_assign",
        },
    )


@login_required
def dashboard_on_call_bookings_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = OnCallBookingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        AdminNotification.objects.create(
            on_call_booking=item,
            message=f"On-call booking added from dashboard: {item.organization_name or item.contact_person}.",
        )
        return redirect("electricity:dashboard_on_call_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add On-Call Booking", "form": form, "back_url": "electricity:dashboard_on_call_bookings"},
    )


@login_required
def dashboard_on_call_bookings_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = OnCallBooking.objects.get(pk=pk)
    form = OnCallBookingForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_on_call_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit On-Call Booking", "form": form, "back_url": "electricity:dashboard_on_call_bookings"},
    )


@login_required
def dashboard_on_call_bookings_assign(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    booking = OnCallBooking.objects.get(pk=pk)
    form = OnCallBookingAssignForm(request.POST or None, instance=booking)
    available_qs = ProviderProfile.objects.filter(is_active=True)
    form.fields["assigned_provider"].queryset = available_qs
    all_providers = ProviderProfile.objects.all().order_by("display_name")
    reasons = {}
    for provider in all_providers:
        if not provider.is_active:
            reasons[provider.id] = {"available": False, "reason": "Inactive provider."}
            continue
        if booking.zip_code and provider.zip_code != booking.zip_code:
            reasons[provider.id] = {"available": False, "reason": "ZIP code mismatch."}
            continue
        reasons[provider.id] = {"available": True, "reason": "Active provider."}
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        if updated.assigned_provider and updated.status in [
            OnCallBooking.Status.PENDING,
            OnCallBooking.Status.REVIEWING,
        ]:
            updated.status = OnCallBooking.Status.APPROVED
        updated.save()
        return redirect("electricity:dashboard_on_call_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {
            "title": "Assign Provider",
            "form": form,
            "back_url": "electricity:dashboard_on_call_bookings",
            "provider_table": {
                "title": "Provider Availability",
                "rows": _provider_table_rows(all_providers, reasons),
            },
        },
    )


@login_required
def dashboard_on_call_bookings_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = OnCallBooking.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_on_call_bookings")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete On-Call Booking", "item": item, "back_url": "electricity:dashboard_on_call_bookings"},
    )


@login_required
def dashboard_electrician_bookings(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = ElectricianBooking.objects.all().order_by("-created_at")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Electrician Bookings",
            "items": items,
            "fields": [
                "full_name",
                "customer_type",
                "preferred_date",
                "arrival_window",
                "assigned_provider",
                "status",
                "created_at",
            ],
            "create_url": "electricity:dashboard_electrician_bookings_add",
            "edit_url": "electricity:dashboard_electrician_bookings_edit",
            "delete_url": "electricity:dashboard_electrician_bookings_delete",
            "assign_url": "electricity:dashboard_electrician_bookings_assign",
        },
    )


@login_required
def dashboard_electrician_bookings_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = ElectricianBookingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        AdminNotification.objects.create(
            message=f"Electrician booking added from dashboard: {item.full_name}.",
        )
        return redirect("electricity:dashboard_electrician_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {
            "title": "Add Electrician Booking",
            "form": form,
            "back_url": "electricity:dashboard_electrician_bookings",
        },
    )


@login_required
def dashboard_electrician_bookings_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ElectricianBooking.objects.get(pk=pk)
    form = ElectricianBookingForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_electrician_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {
            "title": "Edit Electrician Booking",
            "form": form,
            "back_url": "electricity:dashboard_electrician_bookings",
        },
    )


@login_required
def dashboard_electrician_bookings_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ElectricianBooking.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_electrician_bookings")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {
            "title": "Delete Electrician Booking",
            "item": item,
            "back_url": "electricity:dashboard_electrician_bookings",
        },
    )


@login_required
def dashboard_electrician_bookings_assign(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    booking = ElectricianBooking.objects.get(pk=pk)
    form = ElectricianBookingAssignForm(request.POST or None, instance=booking)
    available_qs = ProviderProfile.objects.filter(is_active=True)
    if booking.zip_code:
        available_qs = available_qs.filter(zip_code=booking.zip_code)
    form.fields["assigned_provider"].queryset = available_qs
    all_providers = ProviderProfile.objects.all().order_by("display_name")
    reasons = {}
    for provider in all_providers:
        if not provider.is_active:
            reasons[provider.id] = {"available": False, "reason": "Inactive provider."}
            continue
        if booking.zip_code and provider.zip_code != booking.zip_code:
            reasons[provider.id] = {"available": False, "reason": "ZIP code mismatch."}
            continue
        reasons[provider.id] = {"available": True, "reason": "Active provider."}
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        if updated.assigned_provider and updated.status == ElectricianBooking.Status.PENDING:
            updated.status = ElectricianBooking.Status.CONFIRMED
        updated.save()
        return redirect("electricity:dashboard_electrician_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {
            "title": "Assign Provider",
            "form": form,
            "back_url": "electricity:dashboard_electrician_bookings",
            "provider_table": {
                "title": "Provider Availability",
                "rows": _provider_table_rows(all_providers, reasons),
            },
        },
    )


@login_required
def dashboard_support_tickets(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = SupportTicket.objects.all().order_by("-created_at")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Support Tickets",
            "items": items,
            "fields": ["full_name", "email", "phone", "status", "created_at"],
            "create_url": "electricity:dashboard_support_tickets_add",
            "edit_url": "electricity:dashboard_support_tickets_edit",
            "delete_url": "electricity:dashboard_support_tickets_delete",
        },
    )


@login_required
def dashboard_support_tickets_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = SupportTicketForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        AdminNotification.objects.create(
            message=f"Support ticket added from dashboard: {item.full_name}.",
        )
        return redirect("electricity:dashboard_support_tickets")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add Support Ticket", "form": form, "back_url": "electricity:dashboard_support_tickets"},
    )


@login_required
def dashboard_support_tickets_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = SupportTicket.objects.get(pk=pk)
    form = SupportTicketForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_support_tickets")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit Support Ticket", "form": form, "back_url": "electricity:dashboard_support_tickets"},
    )


@login_required
def dashboard_support_tickets_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = SupportTicket.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_support_tickets")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete Support Ticket", "item": item, "back_url": "electricity:dashboard_support_tickets"},
    )


@login_required
def dashboard_faq(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = FAQEntry.objects.all().order_by("order", "-created_at")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "FAQ",
            "items": items,
            "fields": ["question", "is_active", "order", "created_at"],
            "create_url": "electricity:dashboard_faq_add",
            "edit_url": "electricity:dashboard_faq_edit",
            "delete_url": "electricity:dashboard_faq_delete",
        },
    )


@login_required
def dashboard_faq_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = FAQEntryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_faq")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add FAQ", "form": form, "back_url": "electricity:dashboard_faq"},
    )


@login_required
def dashboard_faq_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = FAQEntry.objects.get(pk=pk)
    form = FAQEntryForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_faq")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit FAQ", "form": form, "back_url": "electricity:dashboard_faq"},
    )


@login_required
def dashboard_faq_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = FAQEntry.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_faq")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete FAQ", "item": item, "back_url": "electricity:dashboard_faq"},
    )


@login_required
def dashboard_zip_codes(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = AcceptedZipCode.objects.all().order_by("code")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Accepted ZIP Codes",
            "items": items,
            "fields": ["code", "is_active", "note", "created_at"],
            "create_url": "electricity:dashboard_zip_codes_add",
            "edit_url": "electricity:dashboard_zip_codes_edit",
            "delete_url": "electricity:dashboard_zip_codes_delete",
        },
    )


@login_required
def dashboard_zip_codes_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = AcceptedZipCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_zip_codes")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add ZIP Code", "form": form, "back_url": "electricity:dashboard_zip_codes"},
    )


@login_required
def dashboard_zip_codes_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = AcceptedZipCode.objects.get(pk=pk)
    form = AcceptedZipCodeForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_zip_codes")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit ZIP Code", "form": form, "back_url": "electricity:dashboard_zip_codes"},
    )


@login_required
def dashboard_zip_codes_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = AcceptedZipCode.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_zip_codes")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete ZIP Code", "item": item, "back_url": "electricity:dashboard_zip_codes"},
    )


@login_required
def dashboard_outside_area_requests(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = ServiceRequestOutsideArea.objects.all().order_by("-created_at")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Outside Area Requests",
            "items": items,
            "fields": ["full_name", "email", "phone", "zip_code", "request_type", "created_at"],
            "create_url": "electricity:dashboard_outside_area_requests_add",
            "edit_url": "electricity:dashboard_outside_area_requests_edit",
            "delete_url": "electricity:dashboard_outside_area_requests_delete",
        },
    )


@login_required
def dashboard_outside_area_requests_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = ServiceRequestOutsideAreaAdminForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_outside_area_requests")
    return render(
        request,
        "electricity/dashboard/form.html",
        {
            "title": "Add Outside Area Request",
            "form": form,
            "back_url": "electricity:dashboard_outside_area_requests",
        },
    )


@login_required
def dashboard_outside_area_requests_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ServiceRequestOutsideArea.objects.get(pk=pk)
    form = ServiceRequestOutsideAreaAdminForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_outside_area_requests")
    return render(
        request,
        "electricity/dashboard/form.html",
        {
            "title": "Edit Outside Area Request",
            "form": form,
            "back_url": "electricity:dashboard_outside_area_requests",
        },
    )


@login_required
def dashboard_outside_area_requests_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ServiceRequestOutsideArea.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_outside_area_requests")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {
            "title": "Delete Outside Area Request",
            "item": item,
            "back_url": "electricity:dashboard_outside_area_requests",
        },
    )


@login_required
def dashboard_bookings_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = ConsultationBookingForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add Consultation Booking", "form": form, "back_url": "electricity:dashboard_bookings"},
    )


@login_required
def dashboard_bookings_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ConsultationBooking.objects.get(pk=pk)
    form = ConsultationBookingForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit Consultation Booking", "form": form, "back_url": "electricity:dashboard_bookings"},
    )


@login_required
def dashboard_bookings_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ConsultationBooking.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_bookings")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete Consultation Booking", "item": item, "back_url": "electricity:dashboard_bookings"},
    )


@login_required
def dashboard_bookings_assign(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    booking = ConsultationBooking.objects.get(pk=pk)
    form = ProviderAssignForm(request.POST or None, instance=booking)
    available_qs = available_providers(
        booking.preferred_date, booking.preferred_time_slot, exclude_booking_id=booking.id
    )
    form.fields["assigned_provider"].queryset = available_qs
    all_providers = ProviderProfile.objects.all().order_by("display_name")
    reasons = {}
    if not booking.preferred_date or not booking.preferred_time_slot:
        for provider in all_providers:
            reasons[provider.id] = {
                "available": False,
                "reason": "Missing preferred date/time on booking.",
            }
    else:
        conflict_ids = set(
            ConsultationBooking.objects.filter(
                preferred_date=booking.preferred_date,
                preferred_time_slot=booking.preferred_time_slot,
                status__in=[
                    ConsultationBooking.BookingStatus.ASSIGNED,
                    ConsultationBooking.BookingStatus.ON_THE_WAY,
                    ConsultationBooking.BookingStatus.STARTED,
                    ConsultationBooking.BookingStatus.PAUSED,
                    ConsultationBooking.BookingStatus.RESUMED,
                    ConsultationBooking.BookingStatus.NOT_AVAILABLE,
                ],
            )
            .exclude(id=booking.id)
            .values_list("assigned_provider_id", flat=True)
        )
        for provider in all_providers:
            if not provider.is_active:
                reasons[provider.id] = {"available": False, "reason": "Inactive provider."}
            elif provider.id in conflict_ids:
                reasons[provider.id] = {
                    "available": False,
                    "reason": "Conflicting consultation at the same time.",
                }
            else:
                reasons[provider.id] = {"available": True, "reason": "Available for the selected time."}
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        if updated.assigned_provider and booking.status == ConsultationBooking.BookingStatus.PENDING:
            updated.status = ConsultationBooking.BookingStatus.ASSIGNED
        updated.save()
        return redirect("electricity:dashboard_bookings")
    return render(
        request,
        "electricity/dashboard/form.html",
        {
            "title": "Assign Provider",
            "form": form,
            "back_url": "electricity:dashboard_bookings",
            "provider_table": {
                "title": "Provider Availability",
                "rows": _provider_table_rows(all_providers, reasons),
            },
        },
    )


@login_required
def dashboard_profiles(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = CustomerProfile.objects.all().order_by("-created_at")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Customer Profiles",
            "items": items,
            "fields": ["full_name", "account_type", "email", "phone", "city"],
            "create_url": "electricity:dashboard_profiles_add",
            "edit_url": "electricity:dashboard_profiles_edit",
            "delete_url": "electricity:dashboard_profiles_delete",
        },
    )


@login_required
def dashboard_profiles_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = CustomerProfileForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_profiles")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add Customer Profile", "form": form, "back_url": "electricity:dashboard_profiles"},
    )


@login_required
def dashboard_profiles_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = CustomerProfile.objects.get(pk=pk)
    form = CustomerProfileForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_profiles")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit Customer Profile", "form": form, "back_url": "electricity:dashboard_profiles"},
    )


@login_required
def dashboard_profiles_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = CustomerProfile.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_profiles")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete Customer Profile", "item": item, "back_url": "electricity:dashboard_profiles"},
    )


@login_required
def dashboard_provider_shifts(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = ProviderShift.objects.select_related("provider").all().order_by("provider", "weekday", "start_time")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Provider Shifts",
            "items": items,
            "fields": ["provider", "weekday_label", "start_time", "end_time"],
            "create_url": "electricity:dashboard_provider_shifts_add",
            "edit_url": "electricity:dashboard_provider_shifts_edit",
            "delete_url": "electricity:dashboard_provider_shifts_delete",
        },
    )


@login_required
def dashboard_provider_shifts_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = ProviderShiftForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_provider_shifts")
    return render(
        request,
        "electricity/dashboard/form.html",
        {
            "title": "Add Provider Shift",
            "form": form,
            "back_url": "electricity:dashboard_provider_shifts",
        },
    )


@login_required
def dashboard_provider_shifts_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ProviderShift.objects.get(pk=pk)
    form = ProviderShiftForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_provider_shifts")
    return render(
        request,
        "electricity/dashboard/form.html",
        {
            "title": "Edit Provider Shift",
            "form": form,
            "back_url": "electricity:dashboard_provider_shifts",
        },
    )


@login_required
def dashboard_provider_shifts_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ProviderShift.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_provider_shifts")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {
            "title": "Delete Provider Shift",
            "item": item,
            "back_url": "electricity:dashboard_provider_shifts",
        },
    )


def dashboard_providers(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = ProviderProfile.objects.all().order_by("display_name")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Providers",
            "items": items,
            "fields": ["display_name", "phone", "zip_code", "availability_status", "is_active"],
            "create_url": "electricity:dashboard_providers_add",
            "edit_url": "electricity:dashboard_providers_edit",
            "delete_url": "electricity:dashboard_providers_delete",
        },
    )


@login_required
def dashboard_providers_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = ProviderProfileForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_providers")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add Provider", "form": form, "back_url": "electricity:dashboard_providers"},
    )


@login_required
def dashboard_providers_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ProviderProfile.objects.get(pk=pk)
    form = ProviderProfileForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_providers")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit Provider", "form": form, "back_url": "electricity:dashboard_providers"},
    )


@login_required
def dashboard_providers_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = ProviderProfile.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_providers")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete Provider", "item": item, "back_url": "electricity:dashboard_providers"},
    )


@login_required
def dashboard_users(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    items = User.objects.all().order_by("username")
    return render(
        request,
        "electricity/dashboard/list.html",
        {
            "title": "Users",
            "items": items,
            "fields": ["username", "email", "is_staff", "is_active"],
            "create_url": "electricity:dashboard_users_add",
            "edit_url": "electricity:dashboard_users_edit",
            "delete_url": "electricity:dashboard_users_delete",
        },
    )


@login_required
def dashboard_users_add(request):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_users")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Add User", "form": form, "back_url": "electricity:dashboard_users"},
    )


@login_required
def dashboard_users_edit(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = User.objects.get(pk=pk)
    form = UserEditForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("electricity:dashboard_users")
    return render(
        request,
        "electricity/dashboard/form.html",
        {"title": "Edit User", "form": form, "back_url": "electricity:dashboard_users"},
    )


@login_required
def dashboard_users_delete(request, pk):
    guard = _dashboard_access_or_redirect(request)
    if guard:
        return guard
    item = User.objects.get(pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("electricity:dashboard_users")
    return render(
        request,
        "electricity/dashboard/delete.html",
        {"title": "Delete User", "item": item, "back_url": "electricity:dashboard_users"},
    )


@login_required
def provider_dashboard(request):
    guard = _provider_access_or_redirect(request)
    if guard:
        return guard
    provider = request.user.provider_profile
    bookings = ConsultationBooking.objects.filter(assigned_provider=provider).order_by("-created_at")
    service_bookings = ServiceBooking.objects.filter(assigned_provider=provider).order_by("-created_at")
    on_call_bookings = OnCallBooking.objects.filter(assigned_provider=provider).order_by("-created_at")
    return render(
        request,
        "electricity/provider/dashboard.html",
        {
            "provider": provider,
            "bookings": bookings,
            "service_bookings": service_bookings,
            "on_call_bookings": on_call_bookings,
        },
    )


@login_required
def provider_order_detail(request, pk):
    guard = _provider_access_or_redirect(request)
    if guard:
        return guard
    provider = request.user.provider_profile
    booking = ConsultationBooking.objects.get(pk=pk, assigned_provider=provider)
    updates = booking.status_updates.all()
    return render(
        request,
        "electricity/provider/order_detail.html",
        {"booking": booking, "updates": updates},
    )


@login_required
def provider_service_booking_detail(request, pk):
    guard = _provider_access_or_redirect(request)
    if guard:
        return guard
    provider = request.user.provider_profile
    booking = ServiceBooking.objects.get(pk=pk, assigned_provider=provider)
    updates = booking.status_updates.all()
    extension_error = request.session.pop("service_extension_error", None)
    extension_success = request.session.pop("service_extension_success", None)
    return render(
        request,
        "electricity/provider/service_booking_detail.html",
        {
            "booking": booking,
            "updates": updates,
            "extension_error": extension_error,
            "extension_success": extension_success,
        },
    )


@login_required
def provider_service_booking_extend(request, pk):
    guard = _provider_access_or_redirect(request)
    if guard:
        return guard
    provider = request.user.provider_profile
    booking = ServiceBooking.objects.get(pk=pk, assigned_provider=provider)
    if request.method == "POST":
        if booking.status not in [
            ServiceBooking.Status.STARTED,
            ServiceBooking.Status.RESUMED,
            ServiceBooking.Status.PAUSED,
            ServiceBooking.Status.ON_THE_WAY,
        ]:
            request.session["service_extension_error"] = "Only active services can be extended."
            return redirect("electricity:provider_service_booking_detail", pk=booking.id)
        try:
            extra_minutes = int(request.POST.get("extend_minutes") or 0)
        except ValueError:
            extra_minutes = 0
        if extra_minutes <= 0:
            request.session["service_extension_error"] = "Extension time must be greater than 0 minutes."
            return redirect("electricity:provider_service_booking_detail", pk=booking.id)
        if not booking.end_at or not booking.start_at:
            request.session["service_extension_error"] = "Cannot extend a booking without a scheduled time."
            return redirect("electricity:provider_service_booking_detail", pk=booking.id)
        new_end = booking.end_at + datetime.timedelta(minutes=extra_minutes)
        if not _provider_is_available(provider, booking.start_at, new_end, exclude_booking_id=booking.id):
            request.session["service_extension_error"] = (
                "Extension conflicts with another booking. Please contact admin."
            )
            return redirect("electricity:provider_service_booking_detail", pk=booking.id)
        booking.end_at = new_end
        booking.duration_minutes = (booking.duration_minutes or 0) + extra_minutes
        booking.save()
        request.session["service_extension_success"] = "Service duration extended successfully."
    return redirect("electricity:provider_service_booking_detail", pk=booking.id)


@login_required
def provider_on_call_booking_detail(request, pk):
    guard = _provider_access_or_redirect(request)
    if guard:
        return guard
    provider = request.user.provider_profile
    booking = OnCallBooking.objects.get(pk=pk, assigned_provider=provider)
    show_customer_contact = booking.status == OnCallBooking.Status.ACTIVE
    return render(
        request,
        "electricity/provider/on_call_booking_detail.html",
        {
            "booking": booking,
            "show_customer_contact": show_customer_contact,
        },
    )


@login_required
def provider_service_booking_update_status(request, pk):
    guard = _provider_access_or_redirect(request)
    if guard:
        return guard
    provider = request.user.provider_profile
    booking = ServiceBooking.objects.get(pk=pk, assigned_provider=provider)
    if request.method == "POST":
        status = request.POST.get("status")
        note = request.POST.get("note", "").strip()
        if status in ServiceBooking.Status.values:
            booking.status = status
            booking.save()
            ServiceBookingStatusUpdate.objects.create(
                booking=booking,
                status=status,
                note=note,
            )
            AdminNotification.objects.create(
                service_booking=booking,
                message=f"Provider {provider.display_name} set service booking status to {status.replace('_', ' ').title()}",
            )
            if status == ServiceBooking.Status.NOT_AVAILABLE and note:
                AdminNotification.objects.create(
                    service_booking=booking,
                    message=f"Provider note: {note[:180]}",
                )
        return redirect("electricity:provider_service_booking_detail", pk=booking.id)
    return redirect("electricity:provider_service_booking_detail", pk=booking.id)


@login_required
def provider_update_status(request, pk):
    guard = _provider_access_or_redirect(request)
    if guard:
        return guard
    provider = request.user.provider_profile
    booking = ConsultationBooking.objects.get(pk=pk, assigned_provider=provider)
    if request.method == "POST":
        status = request.POST.get("status")
        note = request.POST.get("note", "").strip()
        if status in ConsultationBooking.BookingStatus.values:
            booking.status = status
            booking.save()
            BookingStatusUpdate.objects.create(booking=booking, status=status, note=note)
            AdminNotification.objects.create(
                booking=booking,
                message=f"Provider {provider.display_name} set status to {status.replace('_', ' ').title()}",
            )
            if status == ConsultationBooking.BookingStatus.NOT_AVAILABLE and note:
                AdminNotification.objects.create(
                    booking=booking,
                    message=f"Provider note: {note[:180]}",
                )
        return redirect("electricity:provider_order_detail", pk=booking.id)
    return redirect("electricity:provider_order_detail", pk=booking.id)
