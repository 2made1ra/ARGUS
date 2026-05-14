export interface AssistantTimelineCandidatePayload {
  foundItems?: unknown[];
  foundItemsEmptyState?: "pending" | "no-results";
  verificationResults?: unknown[];
  renderedBrief?: unknown;
}

export function appendAssistantTimelineMessage<
  TMessage extends AssistantTimelineCandidatePayload,
>(messages: TMessage[], nextMessage: TMessage): TMessage[] {
  const stripFoundItems = nextMessage.foundItems !== undefined;
  const stripVerificationResults = nextMessage.verificationResults !== undefined;
  const stripRenderedBrief = nextMessage.renderedBrief !== undefined;

  if (!stripFoundItems && !stripVerificationResults && !stripRenderedBrief) {
    return [...messages, nextMessage];
  }

  return [
    ...messages.map((message) =>
      withoutStaleEvidence(message, {
        stripFoundItems,
        stripVerificationResults,
        stripRenderedBrief,
      }),
    ),
    nextMessage,
  ];
}

function withoutStaleEvidence<
  TMessage extends AssistantTimelineCandidatePayload,
>(
  message: TMessage,
  options: {
    stripFoundItems: boolean;
    stripVerificationResults: boolean;
    stripRenderedBrief: boolean;
  },
): TMessage {
  const nextMessage = { ...message };
  if (options.stripFoundItems) {
    delete nextMessage.foundItems;
    delete nextMessage.foundItemsEmptyState;
  }
  if (options.stripVerificationResults) {
    delete nextMessage.verificationResults;
  }
  if (options.stripRenderedBrief) {
    delete nextMessage.renderedBrief;
  }
  return nextMessage;
}
