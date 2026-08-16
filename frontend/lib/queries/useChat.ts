import { useMutation, useQuery } from "@tanstack/react-query";

import { apiClient } from "../api-client";
import type { ChatResponse, ChatStatus } from "../types";

export function useChatStatus() {
  return useQuery({
    queryKey: ["chat", "status"],
    queryFn: () => apiClient.get<ChatStatus>("/api/chat/status"),
  });
}

export function useSendChatMessage() {
  return useMutation({
    mutationFn: (message: string) => apiClient.post<ChatResponse>("/api/chat/message", { message }),
  });
}
