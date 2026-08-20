# Database migrations

SQL migrations will be added only after the assessment contract and
persistence model are approved.

Until then:

* Do not create Supabase tables from this repository.
* Do not store secrets in migration files.
* Domain types in `app/domain` stay independent of Supabase.
