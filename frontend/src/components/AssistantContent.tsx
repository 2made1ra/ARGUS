interface Props {
  content: string;
}

function renderInlineMarkdown(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const boldPattern = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = boldPattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    nodes.push(
      <strong key={`strong-${match.index}`}>{match[1]}</strong>,
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

export default function AssistantContent({ content }: Props) {
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
              {renderInlineMarkdown(line)}
            </span>
          ))}
        </p>
      ))}
    </>
  );
}
