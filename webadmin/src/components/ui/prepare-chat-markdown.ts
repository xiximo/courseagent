/** 模型常用 1.6~2.2 表示区间；GFM 默认把单个 ~ 当成删除线。 */
export function prepareChatMarkdown(source: string): string {
  return source.replace(
    /(\d+(?:\.\d+)?)[~～〜](\d+(?:\.\d+)?)/g,
    '$1—$2'
  )
}
