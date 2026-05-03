import { sourceAnchorId } from "../utils/searchPresentation";

interface Props {
  content: string;
  citationAnchorPrefix?: string;
  citationCount?: number;
}

function renderInlineMarkdown(
  text: string,
  citationAnchorPrefix?: string,
  citationCount = 0,
): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const inlinePattern = /(\*\*(.+?)\*\*|\[S(\d+)\])/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = inlinePattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    const boldText = match[2];
    const citationNumber = match[3] ? Number.parseInt(match[3], 10) : null;

    if (boldText !== undefined) {
      nodes.push(
        <strong key={`strong-${match.index}`}>{boldText}</strong>,
      );
    } else if (
      citationAnchorPrefix &&
      citationNumber !== null &&
      citationNumber >= 1 &&
      citationNumber <= citationCount
    ) {
      nodes.push(
        <a
          aria-label={`Перейти к источнику S${citationNumber}`}
          className="citation-marker"
          href={`#${sourceAnchorId(citationAnchorPrefix, citationNumber - 1)}`}
          key={`citation-${match.index}`}
        >
          S{citationNumber}
        </a>,
      );
    } else {
      nodes.push(match[0]);
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

export default function AssistantContent({
  content,
  citationAnchorPrefix,
  citationCount = 0,
}: Props) {
  const paragraphs = content
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);

  if (paragraphs.length === 0) return null;

  return (
    <>
      {paragraphs.map((paragraph, paragraphIndex) => (
        <p key={`paragraph-${paragraphIndex}`}>
          {paragraph.split("\n").map((line, lineIndex) => (
            <span key={`line-${lineIndex}`}>
              {lineIndex > 0 && <br />}
              {renderInlineMarkdown(line, citationAnchorPrefix, citationCount)}
            </span>
          ))}
        </p>
      ))}
    </>
  );
}
