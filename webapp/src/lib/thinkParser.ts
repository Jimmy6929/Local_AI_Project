export interface ParsedContent {
  thinking: string | null;
  isThinking: boolean;
  response: string;
}

/**
 * Separates `<think>...</think>` blocks from the main response content.
 * Handles partial tags during streaming — if `<think>` is open but
 * `</think>` hasn't arrived yet, `isThinking` will be true.
 */
export function parseThinkingContent(raw: string): ParsedContent {
  const thinkOpen = raw.indexOf("<think>");
  if (thinkOpen === -1) {
    return { thinking: null, isThinking: false, response: raw };
  }

  const thinkClose = raw.indexOf("</think>", thinkOpen);
  const contentStart = thinkOpen + "<think>".length;

  if (thinkClose === -1) {
    // Tag opened but not closed yet — model is still reasoning
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
