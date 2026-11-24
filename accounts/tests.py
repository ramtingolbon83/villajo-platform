from datetime import timedelta

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from properties.models import Property

from .models import (
    Account,
    AuditEvent,
    AvailabilitySlot,
    Reservation,
    Task,
    WorkTime,
)

PASSWORD = "Zx9!vQ2#kLm8@wR"


# ==================================================
#                      Helpers
# ==================================================
def make_user(email, role=Account.Role.CUSTOMER, **extra):
    return Account.objects.create_user(
        email=email, password=PASSWORD, role=role, **extra
    )


def make_property(owner, title="Test Villa", **extra):
    values = {
        "owner": owner,
        "title": title,
        "description": "desc",
        "accommodation_type": "villa",
        "max_guests": 4,
        "bedrooms": 2,
        "beds": 3,
        "building_area": 100,
        "land_area": 200,
        "nightly_price": 1000,
        "status": "published",
        "is_active": True,
    }
    values.update(extra)
    return Property.objects.create(**values)


def results(response):
    """Works with or without pagination."""
    data = response.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


def days(count):
    return timezone.now() + timedelta(days=count)


class BaseApiTest(TestCase):
    def setUp(self):
        cache.clear()  # throttle counters live in the cache
        self.client = APIClient()

    def login(self, user):
        self.client.force_authenticate(user=user)
        return self.client


# ==================================================
#                  Account (model)
# ==================================================
class AccountModelTests(TestCase):
    def test_email_is_lowercased_and_default_role(self):
        user = Account.objects.create_user(email="Test@Example.COM", password=PASSWORD)
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.role, Account.Role.CUSTOMER)

    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            Account.objects.create_user(email="", password=PASSWORD)

    def test_superuser_flags(self):
        admin = Account.objects.create_superuser(
            email="a@example.com", password=PASSWORD
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, Account.Role.ADMIN)

    def test_timestamps_are_set(self):
        user = make_user("t@example.com")
        self.assertIsNotNone(user.created_at)
        self.assertIsNotNone(user.updated_at)


# ==================================================
#              Database constraints (model)
# ==================================================
class ConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user("owner@example.com", Account.Role.OWNER)
        cls.customer = make_user("cust@example.com")
        cls.property = make_property(cls.owner)
        cls.now = timezone.now()

    def test_availability_end_must_be_after_start(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AvailabilitySlot.objects.create(
                property_obj=self.property,
                starts_at=self.now,
                ends_at=self.now - timedelta(days=1),
            )

    def test_reservation_end_must_be_after_start(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reservation.objects.create(
                customer=self.customer,
                property_obj=self.property,
                starts_at=self.now,
                ends_at=self.now - timedelta(days=1),
            )

    def test_reservation_guest_count_must_be_positive(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reservation.objects.create(
                customer=self.customer,
                property_obj=self.property,
                starts_at=self.now,
                ends_at=self.now + timedelta(days=1),
                guest_count=0,
            )

    def test_open_task_without_assignee_is_allowed(self):
        task = Task.objects.create(title="Clean", created_by=self.owner)
        self.assertIsNone(task.assigned_to)

    def test_active_task_without_assignee_is_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Task.objects.create(
                title="Clean",
                created_by=self.owner,
                status=Task.Status.IN_PROGRESS,
            )

    def test_worktime_end_must_be_after_start(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkTime.objects.create(
                employee=self.owner,
                started_at=self.now,
                ended_at=self.now - timedelta(hours=1),
            )

    def test_owner_with_property_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.owner.delete()

    def test_audit_event_survives_actor_deletion(self):
        actor = make_user("actor@example.com")
        event = AuditEvent.objects.create(
            actor=actor, action="test", object_type="Property"
        )
        actor.delete()
        event.refresh_from_db()
        self.assertIsNone(event.actor)


# ==================================================
#                Registration, Me, Admin
# ==================================================
class AccountApiTests(BaseApiTest):
    def test_register_creates_customer_and_ignores_role(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "New@Example.com",
                "password": PASSWORD,
                "role": "ADMIN",
                "is_staff": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        user = Account.objects.get(email="new@example.com")
        self.assertEqual(user.role, Account.Role.CUSTOMER)
        self.assertFalse(user.is_staff)
        self.assertNotIn("password", response.data)

    def test_register_rejects_duplicate_email_in_any_case(self):
        make_user("dup@example.com")
        response = self.client.post(
            reverse("accounts:register"),
            {"email": "DUP@example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_register_rejects_weak_password(self):
        # Needs the default AUTH_PASSWORD_VALIDATORS to be enabled in settings
        response = self.client.post(
            reverse("accounts:register"),
            {"email": "weak@example.com", "password": "123"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_me_requires_authentication(self):
        response = self.client.get(reverse("accounts:me"))
        self.assertIn(response.status_code, (401, 403))

    def test_me_cannot_change_role(self):
        user = make_user("me@example.com")
        response = self.login(user).patch(
            reverse("accounts:me"),
            {"first_name": "Ali", "role": "ADMIN"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Ali")
        self.assertEqual(user.role, Account.Role.CUSTOMER)

    def test_admin_endpoints_are_admin_only(self):
        customer = make_user("c@example.com")
        response = self.login(customer).get(reverse("accounts:admin-account-list"))
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_deactivate_self(self):
        admin = Account.objects.create_superuser(
            email="root@example.com", password=PASSWORD
        )
        response = self.login(admin).post(
            reverse("accounts:admin-account-deactivate", args=[admin.pk])
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_can_deactivate_another_account(self):
        admin = Account.objects.create_superuser(
            email="root@example.com", password=PASSWORD
        )
        target = make_user("t@example.com")
        response = self.login(admin).post(
            reverse("accounts:admin-account-deactivate", args=[target.pk])
        )
        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertFalse(target.is_active)


# ==================================================
#                   Availability (API)
# ==================================================
class AvailabilityApiTests(BaseApiTest):
    def setUp(self):
        super().setUp()
        self.owner = make_user("owner@example.com", Account.Role.OWNER)
        self.other_owner = make_user("owner2@example.com", Account.Role.OWNER)
        self.customer = make_user("cust@example.com")
        self.property = make_property(self.owner)

    def payload(self, start=5, end=10, prop=None):
        return {
            "property_obj": (prop or self.property).pk,
            "starts_at": days(start).isoformat(),
            "ends_at": days(end).isoformat(),
        }

    def test_owner_can_create_slot_for_own_property(self):
        response = self.login(self.owner).post(
            reverse("accounts:availability-list"), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 201)

    def test_other_owner_cannot_create_slot_for_foreign_property(self):
        response = self.login(self.other_owner).post(
            reverse("accounts:availability-list"), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_create_slot(self):
        response = self.login(self.customer).post(
            reverse("accounts:availability-list"), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_overlapping_slots_are_rejected(self):
        AvailabilitySlot.objects.create(
            property_obj=self.property, starts_at=days(5), ends_at=days(10)
        )
        response = self.login(self.owner).post(
            reverse("accounts:availability-list"),
            self.payload(start=8, end=12),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_other_owner_does_not_see_foreign_slots(self):
        AvailabilitySlot.objects.create(
            property_obj=self.property, starts_at=days(5), ends_at=days(10)
        )
        response = self.login(self.other_owner).get(
            reverse("accounts:availability-list")
        )
        self.assertEqual(len(results(response)), 0)

    def test_customer_sees_only_open_slots_of_published_properties(self):
        visible = AvailabilitySlot.objects.create(
            property_obj=self.property, starts_at=days(5), ends_at=days(10)
        )
        AvailabilitySlot.objects.create(
            property_obj=self.property,
            starts_at=days(20),
            ends_at=days(25),
            status=AvailabilitySlot.Status.BLOCKED,
        )
        draft = make_property(self.owner, title="Draft Villa", status="draft")
        AvailabilitySlot.objects.create(
            property_obj=draft, starts_at=days(5), ends_at=days(10)
        )
        response = self.login(self.customer).get(reverse("accounts:availability-list"))
        self.assertEqual([item["id"] for item in results(response)], [visible.pk])


# ==================================================
#                  Reservations (API)
# ==================================================
class ReservationApiTests(BaseApiTest):
    def setUp(self):
        super().setUp()
        self.owner = make_user("owner@example.com", Account.Role.OWNER)
        self.other_owner = make_user("owner2@example.com", Account.Role.OWNER)
        self.customer = make_user("cust@example.com")
        self.other_customer = make_user("cust2@example.com")
        self.admin = Account.objects.create_superuser(
            email="root@example.com", password=PASSWORD
        )
        self.property = make_property(self.owner)
        AvailabilitySlot.objects.create(
            property_obj=self.property, starts_at=days(10), ends_at=days(30)
        )

    def payload(self, start=11, end=13, guests=2, **extra):
        data = {
            "property_obj": self.property.pk,
            "starts_at": days(start).isoformat(),
            "ends_at": days(end).isoformat(),
            "guest_count": guests,
        }
        data.update(extra)
        return data

    def book(self, user=None, **kwargs):
        return self.login(user or self.customer).post(
            reverse("accounts:reservation-list"), self.payload(**kwargs), format="json"
        )

    def make_reservation(self):
        return Reservation.objects.create(
            customer=self.customer,
            property_obj=self.property,
            starts_at=days(11),
            ends_at=days(13),
        )

    def test_requires_authentication(self):
        response = self.client.get(reverse("accounts:reservation-list"))
        self.assertIn(response.status_code, (401, 403))

    def test_customer_can_book_and_is_audited(self):
        response = self.book()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["customer"], self.customer.pk)
        self.assertEqual(response.data["status"], Reservation.Status.PENDING)
        event = AuditEvent.objects.get(action="reservation.create")
        self.assertEqual(event.actor, self.customer)
        self.assertEqual(event.ip_address, "127.0.0.1")

    def test_customer_cannot_choose_customer_or_status(self):
        response = self.book(customer=self.other_customer.pk, status="CONFIRMED")
        self.assertEqual(response.status_code, 201)
        reservation = Reservation.objects.get(pk=response.data["id"])
        self.assertEqual(reservation.customer, self.customer)
        self.assertEqual(reservation.status, Reservation.Status.PENDING)

    def test_only_customers_can_book(self):
        self.assertEqual(self.book(user=self.owner).status_code, 403)

    def test_cannot_book_unpublished_property(self):
        self.property.status = "draft"
        self.property.save()
        self.assertEqual(self.book().status_code, 400)

    def test_cannot_book_inactive_property(self):
        self.property.is_active = False
        self.property.save()
        self.assertEqual(self.book().status_code, 400)

    def test_cannot_exceed_capacity(self):
        self.assertEqual(self.book(guests=99).status_code, 400)

    def test_cannot_book_in_the_past(self):
        self.assertEqual(self.book(start=-3, end=-1).status_code, 400)

    def test_cannot_book_outside_availability(self):
        self.assertEqual(self.book(start=40, end=42).status_code, 400)

    def test_overlapping_booking_is_rejected(self):
        self.assertEqual(self.book().status_code, 201)
        self.assertEqual(
            self.book(user=self.other_customer, start=12, end=14).status_code, 400
        )

    def test_other_customer_cannot_read_reservation(self):
        reservation = self.make_reservation()
        response = self.login(self.other_customer).get(
            reverse("accounts:reservation-detail", args=[reservation.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_other_owner_cannot_read_or_update_reservation(self):
        reservation = self.make_reservation()
        url = reverse("accounts:reservation-detail", args=[reservation.pk])
        client = self.login(self.other_owner)
        self.assertEqual(client.get(url).status_code, 404)
        self.assertEqual(
            client.patch(url, {"status": "CONFIRMED"}, format="json").status_code, 404
        )

    def test_owner_can_only_change_status(self):
        reservation = self.make_reservation()
        url = reverse("accounts:reservation-detail", args=[reservation.pk])
        client = self.login(self.owner)
        ok = client.patch(url, {"status": "CONFIRMED"}, format="json")
        self.assertEqual(ok.status_code, 200)
        denied = client.patch(url, {"guest_count": 1}, format="json")
        self.assertEqual(denied.status_code, 403)

    def test_customer_cannot_confirm_own_reservation(self):
        reservation = self.make_reservation()
        self.login(self.customer).patch(
            reverse("accounts:reservation-detail", args=[reservation.pk]),
            {"status": "CONFIRMED"},
            format="json",
        )

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PENDING)

    def test_only_admin_can_delete(self):
        reservation = self.make_reservation()
        url = reverse("accounts:reservation-detail", args=[reservation.pk])
        self.assertEqual(self.login(self.customer).delete(url).status_code, 403)
        self.assertEqual(self.login(self.admin).delete(url).status_code, 204)


# ==================================================
#                      Tasks (API)
# ==================================================
class TaskApiTests(BaseApiTest):
    def setUp(self):
        super().setUp()
        self.admin = Account.objects.create_superuser(
            email="root@example.com", password=PASSWORD
        )
        self.employee = make_user("emp@example.com", Account.Role.EMPLOYEE)
        self.employee2 = make_user("emp2@example.com", Account.Role.EMPLOYEE)
        self.customer = make_user("cust@example.com")

    def make_task(self, **extra):
        values = {"title": "Clean", "created_by": self.admin}
        values.update(extra)
        return Task.objects.create(**values)

    def test_admin_creates_task_and_is_creator(self):
        response = self.login(self.admin).post(
            reverse("accounts:task-list"), {"title": "Paint"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["created_by"], self.admin.pk)

    def test_employee_cannot_create_task(self):
        response = self.login(self.employee).post(
            reverse("accounts:task-list"), {"title": "Paint"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_employee_sees_own_and_open_tasks_only(self):
        own = self.make_task(assigned_to=self.employee, status=Task.Status.ACCEPTED)
        open_task = self.make_task()
        self.make_task(assigned_to=self.employee2, status=Task.Status.ACCEPTED)
        response = self.login(self.employee).get(reverse("accounts:task-list"))
        ids = {item["id"] for item in results(response)}
        self.assertEqual(ids, {own.pk, open_task.pk})

    def test_customer_sees_no_tasks(self):
        self.make_task()
        response = self.login(self.customer).get(reverse("accounts:task-list"))
        self.assertEqual(len(results(response)), 0)

    def test_employee_can_claim_open_task(self):
        task = self.make_task()
        response = self.login(self.employee).post(
            reverse("accounts:task-accept", args=[task.pk])
        )
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.assigned_to, self.employee)
        self.assertEqual(task.status, Task.Status.ACCEPTED)

    def test_second_employee_cannot_take_a_claimed_task(self):
        task = self.make_task()
        self.login(self.employee).post(reverse("accounts:task-accept", args=[task.pk]))
        response = self.login(self.employee2).post(
            reverse("accounts:task-accept", args=[task.pk])
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_accept_task_offered_to_someone_else(self):
        task = self.make_task(assigned_to=self.employee2)
        response = self.login(self.employee).post(
            reverse("accounts:task-accept", args=[task.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_only_assigned_employee_can_complete(self):
        task = self.make_task(assigned_to=self.employee, status=Task.Status.ACCEPTED)
        url = reverse("accounts:task-complete", args=[task.pk])
        self.assertEqual(self.login(self.employee2).post(url).status_code, 404)
        response = self.login(self.employee).post(
            url, {"result": "done"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.COMPLETED)
        self.assertEqual(task.result, "done")

    def test_employee_cannot_read_other_employee_task(self):
        task = self.make_task(assigned_to=self.employee2, status=Task.Status.ACCEPTED)
        response = self.login(self.employee).get(
            reverse("accounts:task-detail", args=[task.pk])
        )
        self.assertEqual(response.status_code, 404)


# ==================================================
#                   Work Time (API)
# ==================================================
class WorkTimeApiTests(BaseApiTest):
    def setUp(self):
        super().setUp()
        self.admin = Account.objects.create_superuser(
            email="root@example.com", password=PASSWORD
        )
        self.employee = make_user("emp@example.com", Account.Role.EMPLOYEE)
        self.employee2 = make_user("emp2@example.com", Account.Role.EMPLOYEE)
        self.customer = make_user("cust@example.com")

    def payload(self, start_hours=-8, end_hours=-4, **extra):
        now = timezone.now()
        data = {
            "started_at": (now + timedelta(hours=start_hours)).isoformat(),
            "ended_at": (now + timedelta(hours=end_hours)).isoformat(),
        }
        data.update(extra)
        return data

    def log_time(self, user, **kwargs):
        return self.login(user).post(
            reverse("accounts:worktime-list"), self.payload(**kwargs), format="json"
        )

    def test_employee_logs_time_for_self_and_cannot_self_approve(self):
        response = self.log_time(
            self.employee, approved=True, employee=self.employee2.pk
        )
        self.assertEqual(response.status_code, 201)
        record = WorkTime.objects.get(pk=response.data["id"])
        self.assertEqual(record.employee, self.employee)
        self.assertFalse(record.approved)

    def test_customer_cannot_log_time(self):
        self.assertEqual(self.log_time(self.customer).status_code, 403)

    def test_overlapping_periods_are_rejected(self):
        self.assertEqual(self.log_time(self.employee).status_code, 201)
        self.assertEqual(
            self.log_time(self.employee, start_hours=-6, end_hours=-2).status_code, 400
        )

    def test_cannot_log_time_on_task_assigned_to_someone_else(self):
        task = Task.objects.create(
            title="Clean",
            created_by=self.admin,
            assigned_to=self.employee2,
            status=Task.Status.ACCEPTED,
        )
        self.assertEqual(self.log_time(self.employee, task=task.pk).status_code, 400)

    def test_employee_sees_only_own_records(self):
        mine = WorkTime.objects.create(
            employee=self.employee,
            started_at=days(-2),
            ended_at=days(-2) + timedelta(hours=3),
        )
        WorkTime.objects.create(
            employee=self.employee2,
            started_at=days(-2),
            ended_at=days(-2) + timedelta(hours=3),
        )
        response = self.login(self.employee).get(reverse("accounts:worktime-list"))
        self.assertEqual([item["id"] for item in results(response)], [mine.pk])

    def test_approved_record_cannot_be_edited_by_employee(self):
        record = WorkTime.objects.create(
            employee=self.employee,
            started_at=days(-2),
            ended_at=days(-2) + timedelta(hours=3),
            approved=True,
        )
        response = self.login(self.employee).patch(
            reverse("accounts:worktime-detail", args=[record.pk]),
            {"note": "changed"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_is_not_allowed(self):
        record = WorkTime.objects.create(
            employee=self.employee,
            started_at=days(-2),
            ended_at=days(-2) + timedelta(hours=3),
        )
        response = self.login(self.admin).delete(
            reverse("accounts:worktime-detail", args=[record.pk])
        )
        self.assertEqual(response.status_code, 405)

    def test_employee_cannot_read_other_worktime(self):
        record = WorkTime.objects.create(
            employee=self.employee2,
            started_at=days(-2),
            ended_at=days(-2) + timedelta(hours=1),
        )
        response = self.login(self.employee).get(
            reverse("accounts:worktime-detail", args=[record.pk])
        )
        self.assertEqual(response.status_code, 404)
