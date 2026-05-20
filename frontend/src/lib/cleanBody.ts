// Display-side filter: trims well-known page-footer boilerplate
// (terms / privacy / "Story Continues" / Yahoo "View Comments", etc.) from
// extracted news bodies. DB stores the full text unchanged — this only
// affects what NewsDetail renders.
//
// We cut at the FIRST occurrence of any marker rather than removing matched
// lines, because the markers tend to be the start of a footer block that
// runs to the end of the document.
const BOILERPLATE_MARKERS: RegExp[] = [
  /Story Continues/i,
  /View Comments/i,
  /^\[Terms\]\(/im,
  /^\[Privacy Policy\]\(/im,
  /Your Privacy Choices/i,
  /^\[More Info\]\(/im,
  /^Have feedback on this article\?/im,
  /^Companies discussed in this article/im,
  /This article by Simply Wall St is general in nature/i,
  /This website uses cookies/i,
  /^Do Not Sell or Share My Personal Information/im,
  /Do Not Sell My Personal Information/i,
  /^Got it\s*$/im,
  /\* +\[Do Not Sell My Personal Information\]/i,
  // Long tracking-pixel markdown image, often clustered in the footer.
  /!\[Image \d+\]\(https?:\/\/[^)]{50,}\)/,
  /\[Image \d+\]\(https?:\/\/(t\.co|analytics\.twitter|bat\.bing|googleads|doubleclick)/i,
  /^\[Click here to view this article/im,
  /^Continue Reading/im,
  /^\s*\*\s*\*\s*\*\s*$/m, // markdown horizontal rule trios used as section dividers
]

export function stripBoilerplate(text: string | null | undefined): string {
  if (!text) return ''
  let cutoff = text.length
  for (const re of BOILERPLATE_MARKERS) {
    const m = text.match(re)
    if (m && m.index !== undefined && m.index < cutoff) {
      cutoff = m.index
    }
  }
  return text.slice(0, cutoff).trimEnd()
}
