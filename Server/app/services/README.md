# Services

This package will hold use-case coordinators such as "start assessment"
or "publish report".

Ownership:

* `app.api` validates HTTP input and output.
* `app.services` orchestrates a single use case.
* `app.engine` performs deterministic assessment work.
* `app.domain` holds stable concepts and rules.
* `app.repositories` persists data behind vendor-neutral interfaces.

Do not implement scoring, uploads or authentication here until those
contracts are approved.
