# Failure diagnosis via screen recording + vision

## Recipe: an automation just failed

```python
# 1. Stop the recording you started at run begin
video = await screen_record_stop()              # -> {"path": ".sin_recordings/...mp4"}

# 2. Ask vision exactly what went wrong
report = await screen_record_analyze(
    video["path"],
    question="The click on the 'Send' button failed. Watch the video and tell me: "
             "did the button move, was there an overlay/cookie banner, did the page "
             "redirect, or did a dialog appear? Report the timestamp of the problem."
)
# report -> {"summary": "...", "frames_analyzed": 12, "analysis": {...}}

# 3. Apply the recommended fix, retry once, then record the corrected playbook
```

## What the analyzer extracts

- The frame/timestamp where the UI diverged from the expected state.
- Visual blockers: cookie banners, modals, CAPTCHAs, spinners, error toasts.
- Whether a navigation/redirect happened unexpectedly.
- A concrete mapped-to-tool recommendation when possible.

## Privacy / scope

Recording captures the screen (or, preferred, only the browser window region).
Use `screen_record_start(region="window")` to limit capture to the browser
window bounds. Recordings live in `.sin_recordings/` and are gitignored.
