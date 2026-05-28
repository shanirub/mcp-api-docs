---
name: mcp-api-doc
description: >
  Verify FreeRTOS and ESP-IDF API symbols before using them in code.
  ALWAYS use this skill whenever producing any code snippet, example, or explanation
  that involves FreeRTOS or ESP-IDF function calls — even if you're confident about
  the signature. Do NOT skip this for "obvious" or "well-known" symbols; training data
  goes stale and silent signature drift is the exact failure mode this prevents.
  Trigger on: any embedded code involving FreeRTOS (xTaskCreate, xQueueSend, vTaskDelay,
  xSemaphoreTake, xEventGroupWaitBits, etc.) or ESP-IDF (esp_wifi_*, nvs_*, gpio_*,
  esp_err_t patterns, etc.). Do NOT use for non-embedded code, Arduino-only sketches
  without FreeRTOS/ESP-IDF, or purely conceptual questions with no code output.
---

# MCP API Doc — Usage Guide

## What this does

Before writing any FreeRTOS or ESP-IDF symbol into a code response, look it up via
the `mcp-api-doc:lookup_symbol` tool. The tool cross-checks the symbol against a
local indexed documentation snapshot, returning the verified signature, parameter
list, and return type — or fuzzy matches if the name is slightly off.

## When to invoke

- **Always**: any FreeRTOS or ESP-IDF function, macro, or type that appears in code you produce
- **Even if confident**: confidence is not a substitute for verification — this is the whole point
- **Every symbol**: if a snippet uses 3 FreeRTOS calls, look up all 3

## How to invoke

Use `mcp-api-doc:lookup_symbol` with these fields:

```
symbol:          exact name, e.g. "xTaskCreate"
api:             "freertos" or "espidf" (or "any" if unsure which namespace)
expected_params: your expected param list as [{name, type}, ...]
expected_returns: your expected return type as a string
```

**On exact match**: returns the verified signature. If your `expected_params` /
`expected_returns` differ from the index, the tool reports the discrepancy — update
your code accordingly.

**On miss**: returns top fuzzy matches with confidence scores (Jaro-Winkler
similarity — a string distance metric). Pick the closest match and re-lookup, or
flag to the user that the symbol wasn't found in the index.

## Workflow

1. Draft the code mentally (or write it)
2. Identify every FreeRTOS / ESP-IDF symbol used
3. Look up each one **before** finalizing the response
4. If the index returns a discrepancy → use the indexed signature, not your prior
5. If a symbol is not found → note it explicitly in the response ("not in index — verify manually")
6. Then produce the final code response

## What NOT to do

- Do not skip lookup because the symbol "seems obvious"
- Do not produce code first and look up later
- Do not silently ignore discrepancies — always surface them to the user
