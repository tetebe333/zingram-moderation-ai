
# Zingram Image Moderation — Annotation Guide

## Purpose
Create consistent labels for training Zingram's own image moderation model.

## Labels

- nudity: visible nudity according to Zingram's policy.
- sexual_content: explicit sexual activity or imagery.
- suggestive_content: sexualized imagery that is not explicit.
- violence: violent acts, threats depicted visually, or physical fighting.
- graphic_content: graphic injuries, gore, or disturbing bodily harm.
- weapons: visible weapons, interpreted in context.
- self_harm: imagery depicting self-harm or suicide-related acts.
- hate_symbols: identifiable symbols used to promote hate or extremist ideology.

## Annotation values

- 1 = label applies.
- 0 = label does not apply.
- blank = not reviewed or insufficient information.

## Review rules

- Mark ambiguous cases for human review.
- Do not infer harmful intent from appearance alone.
- Distinguish harmless contexts from harmful depictions.
- Do not automatically approve an image because the model is uncertain.
- Record the policy version used for annotation.

## Dataset rules

- Use only images we have permission to use.
- Record dataset source and applicable licence.
- Keep training, validation, and test sets separate.
- Do not place personal or sensitive user images in the dataset without proper authorization.
