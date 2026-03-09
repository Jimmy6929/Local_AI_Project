export interface ParsedContent {
  thinking: string | null;
  isThinking: boolean;
  response: string;
}

/**
 * Separates thinking blocks from the main response content.
 *
 * Handles three formats:
 *  A) `<think>...</think>` — standard tags in content
 *  B) `<think>...` (no close yet) — streaming, model still reasoning
 *  C) `...</think>` (no open tag) — mlx_vlm strips the `<think>` special
 *     token to an empty string; the gateway re-injects it, but this
 *     handles the case defensively if it arrives raw.
 */
export function parseThinkingContent(raw: string): ParsedContent {
  const thinkOpen = raw.indexOf("<think>");
  const thinkClose = raw.indexOf("</think>");

  // Case A/B: explicit <think> tag found
  if (thinkOpen !== -1) {
    const contentStart = thinkOpen + "<think>".length;

    if (thinkClose === -1 || thinkClose < thinkOpen) {
      return {
        thinking: raw.slice(contentStart).trimStart(),
        isThinking: true,
        response: raw.slice(0, thinkOpen).trim(),
      };
    }

    const thinking = raw.slice(contentStart, thinkClose).trim();
    const before = raw.slice(0, thinkOpen);
    const after = raw.slice(thinkClose + "</think>".length);
    const response = (before + after).trim();

    return {
      thinking: thinking || null,
      isThinking: false,
      response,
    };
  }

  // Case C: </think> present but <think> missing (server stripped it)
  if (thinkClose !== -1) {
    const thinking = raw.slice(0, thinkClose).trim();
    const response = raw.slice(thinkClose + "</think>".length).trim();
    return {
      thinking: thinking || null,
      isThinking: false,
      response,
    };
  }

  return { thinking: null, isThinking: false, response: raw };
}
