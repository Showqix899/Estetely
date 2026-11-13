# Estately: Rental Management Backend

Django REST Framework + JWT + PostgreSQL + Redis cache + Celery (worker and beat), all in Docker.

## Run it

1. Open `.env` and set `EMAIL_HOST_PASSWORD` to a **new** Gmail App Password.
2. Start everything:
   ```
   docker compose up --build
   ```
3. API: http://localhost:8000/api/   Admin: http://localhost:8000/admin/
   **Swagger docs: http://localhost:8000/api/docs/**   (raw OpenAPI file: /api/schema/)
4. Create an admin user (needed to add amenities from the API):
   ```
   docker compose exec web python manage.py createsuperuser
   ```
5. Run the tests: `docker compose exec web python manage.py test`

## Using Swagger with JWT

1. Open http://localhost:8000/api/docs/
2. Register with `POST /api/auth/register/`, then log in with `POST /api/auth/login/`.
3. Copy the `access` value from the login response.
4. Click **Authorize** (top right), paste the token (without the word `Bearer`) and press Authorize.
5. Every endpoint with a padlock now sends your token automatically.

## Database tables

| Table    | Relations |
|----------|-----------|
| User     | login with email, role = owner / tenant |
| Profile  | **one-to-one** with User (phone, address, city) |
| Amenity  | **many-to-many** with Property |
| Property | foreign key to owner (User), many-to-many to Amenity |
| Lease    | foreign key to Property and to tenant (User) |

## Endpoints

Send the access token as `Authorization: Bearer <access>` on everything except the first six.

| Method | URL | What it does |
|--------|-----|--------------|
| POST | /api/auth/register/ | create account (`email, full_name, password, role`) |
| POST | /api/auth/login/ | returns `access` + `refresh` tokens |
| POST | /api/auth/token/refresh/ | `refresh` -> new `access` |
| POST | /api/auth/forgot-password/ | emails a reset link (`email`) |
| POST | /api/auth/reset-password/ | `uid, token, new_password` (from the email) |
| GET / PATCH | /api/auth/me/ | my account + nested profile |
| GET / POST | /api/amenities/ | list / add (admin only) |
| GET / POST | /api/properties/ | list available (Redis cached) / create (owner) |
| GET / PUT / PATCH / DELETE | /api/properties/<id>/ | one property (changes: its owner only) |
| GET | /api/my-properties/ | the owner's own properties |
| GET / POST | /api/leases/ | my leases / create a lease (owner) |
| GET | /api/leases/<id>/ | one lease |
| POST | /api/leases/<id>/end/ | end a lease early (owner) |

Property filters: `?city=dhaka&min_rent=100&max_rent=900&bedrooms=2&amenity=1`
The `X-Cache: HIT / MISS` response header shows whether Redis answered.

## Where is Celery used?

* `accounts/tasks.py`: welcome email, password reset email
* `rentals/tasks.py`: lease email, and `close_expired_leases` (scheduled every night by Celery beat)

## Project layout

```
core/       settings (incl. Swagger), urls, celery setup
accounts/   User, Profile, JWT register/login, forgot + reset password
rentals/    Amenity, Property, Lease, caching, tasks
```
