"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import ConversationList from "@/components/ConversationList";
import DocumentsPanel from "@/components/DocumentsPanel";
import { apiCall, runtimeApiCall, uploadPdf } from "@/lib/api";

const RUN_POLL_INTERVAL_MS = 500;
const RUN_POLL_MAX_ATTEMPTS = 120;
const MAX_VISIBLE_RUN_EVENTS = 4;
const NEW_CONVERSATION_KEY = "__new__";

const RUN_IN_PROGRESS_STATUSES = new Set(["queued", "running", "retrying", "cancelling"]);

function localId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function normalizeMessages(payload) {
  if (!Array.isArray(payload)) {
    return [];
  }

  return payload.map((message, index) => ({
    id: message.id || localId(`message-${index}`),
    role: message.role,
    content: message.content,
    timestamp: message.timestamp,
    agent_actions: message.agent_actions || [],
  }));
}

function isEditableElement(node) {
  if (!(node instanceof HTMLElement)) {
    return false;
  }

  return (
    node.isContentEditable ||
    node.tagName === "INPUT" ||
    node.tagName === "TEXTAREA" ||
    node.tagName === "SELECT"
  );
}

function buildRunEventsUrl(runId, afterCursor) {
  const params = new URLSearchParams();
  if (afterCursor) {
    params.set("after", afterCursor);
  }

  const query = params.toString();
  return query ? `/runs/${runId}/events?${query}` : `/runs/${runId}/events`;
}

function mergeRunEvents(previousEvents, nextEvents) {
  const merged = [...(previousEvents || [])];
  const seen = new Set(merged.map((event) => event.event_id));

  for (const event of nextEvents || []) {
    if (!seen.has(event.event_id)) {
      merged.push(event);
      seen.add(event.event_id);
    }
  }

  return merged.slice(-MAX_VISIBLE_RUN_EVENTS);
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export default function HomePage() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [tools, setTools] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [runStateByConversation, setRunStateByConversation] = useState({});

  const [selectedDocuments, setSelectedDocuments] = useState(() => new Set());

  const [messageInput, setMessageInput] = useState("");

  const [loadingConversations, setLoadingConversations] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [sendingConversations, setSendingConversations] = useState(() => new Set());
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const [conversationError, setConversationError] = useState("");
  const [chatError, setChatError] = useState("");
  const [documentError, setDocumentError] = useState("");

  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [documentsExpanded, setDocumentsExpanded] = useState(true);
  const [dragActive, setDragActive] = useState(false);

  const fileInputRef = useRef(null);
  const messageInputRef = useRef(null);
  const activeConversationIdRef = useRef(null);
  const latestMessagesRequestRef = useRef(0);
  const uploadRunRef = useRef(0);
  const uploadResetTimerRef = useRef(null);
  const uploadingRef = useRef(false);

  const focusComposer = useCallback(() => {
    const input = messageInputRef.current;
    if (!input) {
      return;
    }

    input.focus({ preventScroll: true });
    const cursorPosition = input.value.length;
    requestAnimationFrame(() => {
      if (document.activeElement === input && typeof input.setSelectionRange === "function") {
        input.setSelectionRange(cursorPosition, cursorPosition);
      }
    });
  }, []);

  const updateRunState = useCallback((conversationId, patch) => {
    if (!conversationId) {
      return;
    }

    setRunStateByConversation((previousState) => {
      const currentState = previousState[conversationId] || {};
      const nextPatch = typeof patch === "function" ? patch(currentState) : patch;

      return {
        ...previousState,
        [conversationId]: {
          ...currentState,
          ...nextPatch,
        },
      };
    });
  }, []);

  const loadTools = useCallback(async () => {
    try {
      const payload = await apiCall("/tools");
      setTools(Array.isArray(payload) ? payload : []);
    } catch {
      setTools([
        { name: "calculator" },
        { name: "current_time" },
        { name: "search_documents" },
      ]);
    }
  }, []);

  const loadConversations = useCallback(async (preferredConversationId = null) => {
    setLoadingConversations(true);
    setConversationError("");

    try {
      const payload = await apiCall("/conversations");
      const nextConversations = Array.isArray(payload) ? payload : [];
      setConversations(nextConversations);

      setCurrentConversationId((previousConversationId) => {
        if (
          preferredConversationId &&
          nextConversations.some((conversation) => conversation.id === preferredConversationId)
        ) {
          return preferredConversationId;
        }

        if (
          previousConversationId &&
          nextConversations.some((conversation) => conversation.id === previousConversationId)
        ) {
          return previousConversationId;
        }

        return nextConversations[0]?.id || null;
      });
    } catch {
      setConversationError("Failed to load conversations.");
    } finally {
      setLoadingConversations(false);
    }
  }, []);

  const loadConversationMessages = useCallback(async (conversationId) => {
    if (!conversationId) {
      latestMessagesRequestRef.current += 1;
      setLoadingMessages(false);
      setChatError("");
      setMessages([]);
      return;
    }

    const requestId = latestMessagesRequestRef.current + 1;
    latestMessagesRequestRef.current = requestId;

    setLoadingMessages(true);
    setChatError("");

    try {
      const payload = await apiCall(`/conversations/${conversationId}/messages`);
      if (
        requestId !== latestMessagesRequestRef.current ||
        conversationId !== activeConversationIdRef.current
      ) {
        return;
      }
      setMessages(normalizeMessages(payload));
    } catch {
      if (
        requestId !== latestMessagesRequestRef.current ||
        conversationId !== activeConversationIdRef.current
      ) {
        return;
      }
      setMessages([]);
      setChatError("Failed to load conversation messages.");
    } finally {
      if (requestId === latestMessagesRequestRef.current) {
        setLoadingMessages(false);
      }
    }
  }, []);

  const loadDocuments = useCallback(async () => {
    setLoadingDocuments(true);
    setDocumentError("");

    try {
      const payload = await apiCall("/documents");
      const nextDocuments = payload?.documents || [];
      setDocuments(nextDocuments);

      setSelectedDocuments((previousSelected) => {
        const nextSelected = new Set();
        const validIds = new Set(nextDocuments.map((document) => document.id));

        for (const documentId of previousSelected) {
          if (validIds.has(documentId)) {
            nextSelected.add(documentId);
          }
        }

        return nextSelected;
      });
    } catch {
      setDocumentError("Failed to load documents.");
      setDocuments([]);
    } finally {
      setLoadingDocuments(false);
    }
  }, []);

  const createConversation = useCallback(async () => {
    setConversationError("");

    try {
      const created = await apiCall("/conversations", {
        method: "POST",
        body: JSON.stringify({}),
      });

      const nextConversationId = created?.id || null;
      await loadConversations(nextConversationId);
      setMessages([]);
      focusComposer();
    } catch {
      setConversationError("Failed to create conversation.");
    }
  }, [focusComposer, loadConversations]);

  const sendMessage = useCallback(async () => {
    const trimmedMessage = messageInput.trim();
    let requestConversationId = currentConversationId;
    let sendingConversationKey = requestConversationId || NEW_CONVERSATION_KEY;

    if (!trimmedMessage || sendingConversations.has(sendingConversationKey)) {
      return;
    }

    setSendingConversations((prev) => new Set(prev).add(sendingConversationKey));
    setChatError("");
    let thinkingId = null;

    try {
      if (!requestConversationId) {
        const created = await apiCall("/conversations", {
          method: "POST",
          body: JSON.stringify({}),
        });

        requestConversationId = created?.id || null;
        if (!requestConversationId) {
          throw new Error("Conversation creation failed");
        }

        sendingConversationKey = requestConversationId;
        activeConversationIdRef.current = requestConversationId;
        setCurrentConversationId(requestConversationId);
        setMessages([]);
        setSendingConversations((prev) => {
          const next = new Set(prev);
          next.delete(NEW_CONVERSATION_KEY);
          next.add(requestConversationId);
          return next;
        });
        await loadConversations(requestConversationId);
      }

      setMessageInput("");
      thinkingId = localId("thinking");

      const optimisticUserMessage = {
        id: localId("user"),
        role: "user",
        content: trimmedMessage,
        timestamp: new Date().toISOString(),
        agent_actions: [],
      };

      const thinkingMessage = {
        id: thinkingId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
        agent_actions: [],
        isThinking: true,
      };

      setMessages((previousMessages) => [...previousMessages, optimisticUserMessage, thinkingMessage]);

      const submitResponse = await runtimeApiCall("/chat", {
        method: "POST",
        body: JSON.stringify({
          message: trimmedMessage,
          conversation_id: requestConversationId,
          selected_documents: Array.from(selectedDocuments),
        }),
      });

      const runId = submitResponse?.run_id;
      if (!runId) {
        throw new Error("Run submission did not return run_id");
      }

      let status = null;
      let latestEventsCursor = null;

      updateRunState(requestConversationId, {
        runId,
        status: "queued",
        error: "",
        latestEvent: null,
        events: [],
      });

      for (let attempt = 0; attempt < RUN_POLL_MAX_ATTEMPTS; attempt += 1) {
        try {
          const [nextStatus, eventsPayload] = await Promise.all([
            runtimeApiCall(`/runs/${runId}/status`),
            runtimeApiCall(buildRunEventsUrl(runId, latestEventsCursor)),
          ]);

          status = nextStatus;
          const nextEvents = Array.isArray(eventsPayload?.events) ? eventsPayload.events : [];
          latestEventsCursor = eventsPayload?.next_after || latestEventsCursor;

          updateRunState(requestConversationId, (previousRunState) => {
            const mergedEvents = mergeRunEvents(previousRunState.events, nextEvents);

            return {
              runId,
              status: status?.status || previousRunState.status || "queued",
              error: status?.error || "",
              events: mergedEvents,
              latestEvent: mergedEvents[mergedEvents.length - 1] || previousRunState.latestEvent || null,
            };
          });
        } catch {
          if (attempt === RUN_POLL_MAX_ATTEMPTS - 1) {
            throw new Error("Run status polling failed");
          }
          await sleep(RUN_POLL_INTERVAL_MS);
          continue;
        }

        if (!RUN_IN_PROGRESS_STATUSES.has(status?.status)) {
          break;
        }

        await sleep(RUN_POLL_INTERVAL_MS);
      }

      if (!status || RUN_IN_PROGRESS_STATUSES.has(status.status)) {
        throw new Error("Run polling timed out");
      }

      await loadConversations();
      if (activeConversationIdRef.current === requestConversationId) {
        setMessages((previousMessages) => previousMessages.filter((item) => item.id !== thinkingId));
        await loadConversationMessages(requestConversationId);
        if (status.status !== "succeeded") {
          setChatError(status.error || "Run failed.");
        }
      }
    } catch {
      if (!requestConversationId) {
        setChatError("Failed to start a conversation.");
      }

      if (requestConversationId) {
        updateRunState(requestConversationId, (previousRunState) => ({
          ...previousRunState,
          status: "failed",
          error: "Failed to send message.",
        }));
      }

      if (thinkingId && activeConversationIdRef.current === requestConversationId) {
        setMessages((previousMessages) => [
          ...previousMessages.filter((message) => message.id !== thinkingId),
          {
            id: localId("error"),
            role: "assistant",
            content: "[Error: Failed to send message]",
            timestamp: new Date().toISOString(),
            agent_actions: [],
          },
        ]);
        setChatError("Failed to send message.");
      }
    } finally {
      setSendingConversations((prev) => {
        const next = new Set(prev);
        next.delete(NEW_CONVERSATION_KEY);
        if (sendingConversationKey) {
          next.delete(sendingConversationKey);
        }
        return next;
      });
      focusComposer();
    }
  }, [
    currentConversationId,
    focusComposer,
    loadConversations,
    loadConversationMessages,
    messageInput,
    selectedDocuments,
    sendingConversations,
    updateRunState,
  ]);

  const uploadFiles = useCallback(
    async (files) => {
      if (uploadingRef.current) {
        setDocumentError("Upload already in progress.");
        return;
      }

      const pdfFiles = files.filter((file) => file.type === "application/pdf");

      if (pdfFiles.length === 0) {
        setDocumentError("Please select PDF files only.");
        setUploading(false);
        setUploadProgress(0);
        return;
      }

      uploadRunRef.current += 1;
      const uploadRunId = uploadRunRef.current;
      if (uploadResetTimerRef.current) {
        clearTimeout(uploadResetTimerRef.current);
        uploadResetTimerRef.current = null;
      }

      setUploading(true);
      setUploadProgress(0);
      setDocumentError("");

      const failedUploads = [];

      for (let index = 0; index < pdfFiles.length; index += 1) {
        const file = pdfFiles[index];

        try {
          await uploadPdf(file);
        } catch {
          failedUploads.push(file.name);
        }

        setUploadProgress(Math.round(((index + 1) / pdfFiles.length) * 100));
      }

      await loadDocuments();

      if (failedUploads.length > 0) {
        setDocumentError(`Failed to upload: ${failedUploads.join(", ")}`);
      }

      uploadResetTimerRef.current = setTimeout(() => {
        if (uploadRunId !== uploadRunRef.current) {
          return;
        }
        setUploading(false);
        setUploadProgress(0);
        uploadResetTimerRef.current = null;
      }, 500);
    },
    [loadDocuments],
  );

  const onFileSelect = useCallback(
    async (event) => {
      const files = Array.from(event.target.files || []);
      await uploadFiles(files);
      event.target.value = "";
    },
    [uploadFiles],
  );

  const onDrop = useCallback(
    async (event) => {
      event.preventDefault();
      setDragActive(false);
      const files = Array.from(event.dataTransfer.files || []);
      await uploadFiles(files);
    },
    [uploadFiles],
  );

  const onDeleteDocument = useCallback(
    async (documentId, filename) => {
      if (!window.confirm(`Delete \"${filename}\"?`)) {
        return;
      }

      setDocumentError("");

      try {
        await apiCall(`/documents/${documentId}`, { method: "DELETE" });
        setSelectedDocuments((previousSelected) => {
          const nextSelected = new Set(previousSelected);
          nextSelected.delete(documentId);
          return nextSelected;
        });
        await loadDocuments();
      } catch {
        setDocumentError("Failed to delete document.");
      }
    },
    [loadDocuments],
  );

  useEffect(() => {
    void loadTools();
    void loadConversations();
    void loadDocuments();
  }, [loadConversations, loadDocuments, loadTools]);

  useEffect(() => {
    activeConversationIdRef.current = currentConversationId;
  }, [currentConversationId]);

  useEffect(() => {
    uploadingRef.current = uploading;
  }, [uploading]);

  useEffect(() => {
    focusComposer();
  }, [focusComposer, currentConversationId]);

  useEffect(() => {
    void loadConversationMessages(currentConversationId);
  }, [currentConversationId, loadConversationMessages]);

  useEffect(() => {
    const container = document.getElementById("chat-container");
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage || lastMessage.role !== "assistant" || lastMessage.isThinking) {
      return;
    }

    focusComposer();
  }, [focusComposer, messages]);

  useEffect(() => {
    focusComposer();

    const onWindowFocus = () => {
      focusComposer();
    };

    const onVisibilityChange = () => {
      if (!document.hidden) {
        focusComposer();
      }
    };

    const onTypeToFocus = (event) => {
      if (
        event.defaultPrevented ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey ||
        event.key.length !== 1 ||
        isEditableElement(event.target)
      ) {
        return;
      }

      event.preventDefault();
      focusComposer();
      setMessageInput((previousValue) => previousValue + event.key);
    };

    window.addEventListener("focus", onWindowFocus);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("keydown", onTypeToFocus);

    return () => {
      window.removeEventListener("focus", onWindowFocus);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("keydown", onTypeToFocus);
    };
  }, [focusComposer]);

  useEffect(() => {
    return () => {
      if (uploadResetTimerRef.current) {
        clearTimeout(uploadResetTimerRef.current);
      }
    };
  }, []);

  const currentConversation = conversations.find((conversation) => conversation.id === currentConversationId) || null;
  const activeRun =
    (currentConversationId && runStateByConversation[currentConversationId]) ||
    runStateByConversation[NEW_CONVERSATION_KEY] ||
    null;
  const currentConversationKey = currentConversationId || NEW_CONVERSATION_KEY;

  return (
    <div className="app-root">
      <ConversationList
        conversations={conversations}
        currentConversationId={currentConversationId}
        runStateByConversation={runStateByConversation}
        isLoading={loadingConversations}
        error={conversationError}
        isCollapsed={leftCollapsed}
        onToggleCollapse={() => setLeftCollapsed((isCollapsed) => !isCollapsed)}
        onCreateConversation={createConversation}
        onSelectConversation={setCurrentConversationId}
      />

      <ChatPanel
        tools={tools}
        messages={messages}
        currentConversationTitle={currentConversation?.title || ""}
        activeRun={activeRun}
        selectedDocumentCount={selectedDocuments.size}
        isLoadingMessages={loadingMessages}
        chatError={chatError}
        messageInput={messageInput}
        isSending={sendingConversations.has(currentConversationKey)}
        onChangeMessage={setMessageInput}
        onSendMessage={sendMessage}
        onFocusComposer={focusComposer}
        messageInputRef={messageInputRef}
      />

      <DocumentsPanel
        documents={documents}
        selectedDocuments={selectedDocuments}
        documentsExpanded={documentsExpanded}
        isLoading={loadingDocuments}
        error={documentError}
        isUploading={uploading}
        uploadProgress={uploadProgress}
        isCollapsed={rightCollapsed}
        isDragActive={dragActive}
        onToggleCollapse={() => setRightCollapsed((isCollapsed) => !isCollapsed)}
        onToggleDocumentsExpanded={() => setDocumentsExpanded((isExpanded) => !isExpanded)}
        onOpenFilePicker={() => fileInputRef.current?.click()}
        onFileSelect={onFileSelect}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={(event) => {
          event.preventDefault();
          if (!event.currentTarget.contains(event.relatedTarget)) {
            setDragActive(false);
          }
        }}
        onDrop={onDrop}
        onToggleDocument={(documentId, checked) => {
          setSelectedDocuments((previousSelected) => {
            const nextSelected = new Set(previousSelected);
            if (checked) {
              nextSelected.add(documentId);
            } else {
              nextSelected.delete(documentId);
            }
            return nextSelected;
          });
        }}
        onDeleteDocument={onDeleteDocument}
        fileInputRef={fileInputRef}
      />
    </div>
  );
}
