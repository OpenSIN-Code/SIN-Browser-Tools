# `pii_redaction.py`

Automatic PII (Personally Identifiable Information) redaction for logs and outputs.

## `PIIRedactor`

Detects and redacts sensitive data patterns.

### Supported Patterns

| Type | Example | Redacted As |
|------|---------|-------------|
| Email | `user@example.com` | `[EMAIL_REDACTED]` |
| Phone | `+1-555-123-4567` | `[PHONE_REDACTED]` |
| Credit Card | `4111-1111-1111-1111` | `[CC_REDACTED]` |
| IBAN | `DE89370400440532013000` | `[IBAN_REDACTED]` |
| Session ID | `sess_abc123...` | `[SESSION_REDACTED]` |
| Custom | User-defined patterns | `[CUSTOM_REDACTED]` |

### Usage

```python
redactor = PIIRedactor()
stats = RedactionStats()
clean_text = redactor.redact("Contact: user@example.com", stats)
# clean_text = "Contact: [EMAIL_REDACTED]"
# stats.emails = 1, stats.total = 1
```

### Custom Patterns

```python
redactor = PIIRedactor(custom_patterns=[
    (r"API-[A-Z0-9]{32}", "[API_KEY_REDACTED]")
])
```

## `RedactionStats`

Tracks counts of each redaction type.

| Field | Description |
|-------|-------------|
| `emails` | Email addresses redacted |
| `phones` | Phone numbers redacted |
| `credit_cards` | Credit card numbers redacted |
| `ibans` | IBANs redacted |
| `session_ids` | Session identifiers redacted |
| `custom` | Custom pattern matches |
| `total` | Sum of all redactions |

## Integration

Used by `SmartBrowserTools` to automatically redact PII from logs and trace
output, ensuring sensitive data doesn't leak into observability systems.
