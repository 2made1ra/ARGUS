import type {
  AssistantChatRequest,
  BriefState,
  ChatMessage,
  FoundItem,
} from "../api";
import { buildVisibleCandidates } from "./assistantCandidates.ts";

export interface AssistantRequestTimelineMessage extends ChatMessage {
  foundItems?: FoundItem[];
}

export interface BuildAssistantChatRequestInput {
  sessionId: string | null;
  message: string;
  brief: BriefState;
  messages: AssistantRequestTimelineMessage[];
  visibleFoundItems: FoundItem[];
}

export function buildAssistantChatRequest({
  sessionId,
  message,
  brief,
  messages,
  visibleFoundItems,
}: BuildAssistantChatRequestInput): AssistantChatRequest {
  const visibleCandidates = buildVisibleCandidates(visibleFoundItems);

  return {
    session_id: sessionId,
    message,
    brief,
    recent_turns: messages
      .slice(-6)
      .map(({ role, content }) => ({ role, content })),
    visible_candidates: visibleCandidates,
    candidate_item_ids: visibleCandidates.map((candidate) => candidate.item_id),
  };
}
