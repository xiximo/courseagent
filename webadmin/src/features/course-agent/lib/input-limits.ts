/** 对话输入字数上限（与需求 / workflow policies.maxInputChars 对齐） */
export const COURSE_AGENT_MAX_INPUT_CHARS = 500

export function countInputChars(text: string): number {
  return [...text].length
}

export function isInputTooLong(
  text: string,
  max = COURSE_AGENT_MAX_INPUT_CHARS
): boolean {
  return countInputChars(text.trim()) > max
}
