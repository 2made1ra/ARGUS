interface Props {
  text: string;
  query: string;
}

export default function SnippetHighlight({ text, query }: Props) {
  const needle = query.trim();
  if (!needle) return <>{text}</>;

  const lowerText = text.toLocaleLowerCase();
  const lowerNeedle = needle.toLocaleLowerCase();
  const lowerParts = lowerText.split(lowerNeedle);
  const parts: Array<{ text: string; match: boolean }> = [];
  let cursor = 0;

  lowerParts.forEach((part, index) => {
    const end = cursor + part.length;
    if (end > cursor) {
      parts.push({ text: text.slice(cursor, end), match: false });
    }
    cursor = end;
    if (index < lowerParts.length - 1) {
      parts.push({
        text: text.slice(cursor, cursor + needle.length),
        match: true,
      });
      cursor += needle.length;
    }
  });

  if (parts.length === 0) {
    return <>{text}</>;
  }

  return (
    <>
      {parts.map((part, index) =>
        part.match ? (
          <strong className="snippet-hit" key={index}>
            {part.text}
          </strong>
        ) : (
          <span key={index}>{part.text}</span>
        )
      )}
    </>
  );
}
