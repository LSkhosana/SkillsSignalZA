"""Safe commerce failures. Never include provider payloads or secret material."""


class PaymentProviderError(Exception):
    """Provider call failed. Message must stay generic."""

    retryable = False


class PaymentProviderUnavailable(PaymentProviderError):
    """Timeout, transport failure, or unexpected provider outage."""

    retryable = True


class PaymentProviderRejected(PaymentProviderError):
    """Provider returned a definite, non-retryable failure or malformed payload."""

    retryable = False
