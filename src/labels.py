
"""Zingram's initial image moderation taxonomy.

These labels define what our future model will learn.
They do not perform moderation by themselves.
"""

MODERATION_LABELS = (
    "safe",
    "nudity",
    "sexual_content",
    "suggestive_content",
    "violence",
    "graphic_content",
    "weapons",
    "self_harm",
    "hate_symbols",
)

# These categories can overlap in one image.
CONTENT_LABELS = MODERATION_LABELS[1:]

# Uncertain predictions should go to review rather than
# being treated as a separate visual content category.
REVIEW_REQUIRED = "review_required"
