# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""PagerDuty Events API V2 trigger (v1.5.0).

Pages the on-call rotation when a SentinelQA run's
``quality_score`` drops below a configured threshold. Triggers (and
auto-resolves) incidents via the Events API V2.
"""

from __future__ import annotations

from integrations.pagerduty.trigger import (
    PAGERDUTY_ROUTING_KEY_ENV,
    PagerDutyError,
    PagerDutyTrigger,
    PagerDutyTriggerRequest,
    PagerDutyTriggerResult,
    main,
    should_trigger,
)

__all__ = [
    "PAGERDUTY_ROUTING_KEY_ENV",
    "PagerDutyError",
    "PagerDutyTrigger",
    "PagerDutyTriggerRequest",
    "PagerDutyTriggerResult",
    "main",
    "should_trigger",
]
