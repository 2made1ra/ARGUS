export interface AssistantTimelineCandidatePayload {
  foundItems?: unknown[];
  foundItemsEmptyState?: "pending" | "no-results";
}

export function appendAssistantTimelineMessage<
  TMessage extends AssistantTimelineCandidatePayload,
>(messages: TMessage[], nextMessage: TMessage): TMessage[] {
  if (nextMessage.foundItems === undefined) {
    return [...messages, nextMessage];
  }

  return [
    ...messages.map((message) => withoutCandidateCards(message)),
    nextMessage,
  ];
}

function withoutCandidateCards<TMessage extends AssistantTimelineCandidatePayload>(
  message: TMessage,
): TMessage {
  const { foundItems, foundItemsEmptyState, ...rest } = message;
  void foundItems;
  void foundItemsEmptyState;
  return rest as TMessage;
}
