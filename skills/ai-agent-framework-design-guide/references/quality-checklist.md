# Quality Checklist

Run this checklist before delivering the document.

## Boundary clarity

- Have you explained what each major layer owns?
- Have you stated what each major layer must not do?
- If two layers sound similar, have you made their difference explicit?

## Source grounding

- Is the "现状依据" section backed by real source artifacts or clearly labeled assumptions?
- Have you separated current facts from proposed design?
- If sources conflict, have you named the conflict instead of smoothing it over?

## Flow completeness

- Does the document include at least one end-to-end call path?
- For every major flow, is it clear who selects, who executes, and who validates?
- Are stop conditions, retry points, or replanning points explained when relevant?

## Contract precision

- When the design introduces config, plan, or context objects, have you shown a minimal schema or example?
- Is it clear which fields are model-controlled, server-controlled, or runtime-derived?
- Have high-impact parameters been constrained or revalidated?

## Safety and fallback

- Is it clear what the model is not allowed to control?
- Does the document explain how matching, routing, runtime selection, or downstream APIs fail safely?
- Are downgrade and noop paths described where needed?

## Rollout quality

- Is the rollout path staged by dependency and value, not just chronology?
- Does each phase leave the system in a coherent state?
- Are there clear pilot points or MVP slices when the design is large?

## Writing quality

- Is the language concise and Chinese-first unless the task required otherwise?
- Are key terms stable across sections?
- Did you avoid padding the document with generic architecture language?
- Are risks and open questions only included when they add real decision value?
