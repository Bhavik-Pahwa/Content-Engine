<!-- version: 1.0.0 -->
Create one LinkedIn post draft from the structured context below.

Content item:

{content_item_title}

Knowledge summary:

{knowledge_summary}

Knowledge keywords:

{knowledge_keywords}

Technology tags:

{technology_tags}

Companies:

{companies}

Concepts:

{concepts}

Content plan:

- Primary angle: {primary_angle}
- Target audience: {target_audience}
- Content goal: {content_goal}
- Content type: {content_type}
- Hook style: {hook_style}
- Writing persona: {writing_persona}
- Key points:
{key_points}
- Call to action: {call_to_action}
- Visual theme: {visual_theme}

Validation feedback from previous attempt:

{validation_feedback}

Output requirements:

- Write for LinkedIn only.
- Use a strong hook.
- Use short paragraphs.
- Include practical insight, not a summary dump.
- Keep hashtags relevant and limited.
- Do not include markdown fences.
- Return valid JSON only with this exact shape:

{{
  "title": "short internal title",
  "hook": "opening hook",
  "body": "main post body with paragraph breaks",
  "call_to_action": "short closing prompt",
  "hashtags": ["#Example", "#ExampleTwo"]
}}
