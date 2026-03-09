"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ActivityDashboard from "@/components/ActivityDashboard";
import ChatPanel from "@/components/ChatPanel";
import ConversationList from "@/components/ConversationList";
import DocumentsPanel from "@/components/DocumentsPanel";
import MetricsDashboard from "@/components/MetricsDashboard";
import { apiCall, runtimeApiCall, uploadPdf } from "@/lib/api";
import { subscribeToRunStream } from "@/lib/runStream";

const RUN_POLL_INTERVAL_MS = 500;
const RUN_POLL_MAX_ATTEMPTS = 120;
const MAX_VISIBLE_RUN_EVENTS = 4;
const NEW_CONVERSATION_KEY = "__new__";
const DEFAULT_LEFT_PANEL_WIDTH = 272;
const DEFAULT_RIGHT_PANEL_WIDTH = 316;
const MIN_LEFT_PANEL_WIDTH = 220;
const MAX_LEFT_PANEL_WIDTH = 420;
const MIN_RIGHT_PANEL_WIDTH = 260;
const MAX_RIGHT_PANEL_WIDTH = 460;
const COLLAPSED_PANEL_WIDTH = 0;
const PANEL_COLLAPSE_THRESHOLD = 120;
const APP_ROOT_PADDING = 16;
const PANEL_GAP = 16;
const DESKTOP_RESIZE_BREAKPOINT = 1120;

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

function isInteractiveElement(node) {
  if (!(node instanceof HTMLElement)) {
    return false;
  }

  return Boolean(
    node.closest(
      [
        "button",
        "a",
        "summary",
        "[role='button']",
        "[role='link']",
        "[role='tab']",
        "[role='checkbox']",
        "[role='menuitem']",
      ].join(", "),
    ),
  );
}

function buildRunEventsUrl(runId, afterCursor) {
  const params = new URLSearchParams();
  params.set("limit", String(MAX_VISIBLE_RUN_EVENTS));
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

function readConversationIdFromLocation() {
  if (typeof window === "undefined") {
    return null;
  }

  return new URLSearchParams(window.location.search).get("conversation");
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export default function WorkspaceApp({ view, currentPath, initialConversationId = null }) {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(initialConversationId);
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
  const [leftPanelWidth, setLeftPanelWidth] = useState(DEFAULT_LEFT_PANEL_WIDTH);
  const [rightPanelWidth, setRightPanelWidth] = useState(DEFAULT_RIGHT_PANEL_WIDTH);
  const [documentsExpanded, setDocumentsExpanded] = useState(true);
  const [dragActive, setDragActive] = useState(false);
  const [resizingSidebar, setResizingSidebar] = useState(null);

  const appRootRef = useRef(null);
  const activeStreamCleanupRef = useRef(null);
  const fileInputRef = useRef(null);
  const messageInputRef = useRef(null);
  const focusAnimationFrameRef = useRef(null);
  const activeConversationIdRef = useRef(null);
  const latestConversationsRequestRef = useRef(0);
  const latestMessagesRequestRef = useRef(0);
  const uploadRunRef = useRef(0);
  const uploadResetTimerRef = useRef(null);
  const uploadingRef = useRef(false);

  const syncConversationUrl = useCallback(
    (conversationId) => {
      if (typeof window === "undefined") {
        return;
      }

      const params = new URLSearchParams(window.location.search);
      if (conversationId) {
        params.set("conversation", conversationId);
      } else {
        params.delete("conversation");
      }

      const nextQuery = params.toString();
      const nextUrl = nextQuery ? `${currentPath}?${nextQuery}` : currentPath;
      const currentUrl = `${window.location.pathname}${window.location.search}`;
      if (currentUrl === nextUrl) {
        return;
      }
      window.history.replaceState(null, "", nextUrl);
    },
    [currentPath],
  );

  const setConversationSelection = useCallback(
    (conversationId, { syncUrl = true } = {}) => {
      activeConversationIdRef.current = conversationId;
      setCurrentConversationId(conversationId);
      if (syncUrl) {
        syncConversationUrl(conversationId);
      }
    },
    [syncConversationUrl],
  );

  const focusComposer = useCallback(() => {
    const input = messageInputRef.current;
    if (!input || view !== "chat") {
      return;
    }

    input.focus({ preventScroll: true });
    if (focusAnimationFrameRef.current !== null) {
      cancelAnimationFrame(focusAnimationFrameRef.current);
    }

    focusAnimationFrameRef.current = requestAnimationFrame(() => {
      focusAnimationFrameRef.current = null;
      if (document.activeElement === input && typeof input.setSelectionRange === "function") {
        const cursorPosition = input.value.length;
        input.setSelectionRange(cursorPosition, cursorPosition);
      }
    });
  }, [view]);

  const toggleLeftCollapsed = useCallback(() => {
    setLeftCollapsed((isCollapsed) => !isCollapsed);
  }, []);

  const toggleRightCollapsed = useCallback(() => {
    setRightCollapsed((isCollapsed) => !isCollapsed);
  }, []);

  const startSidebarResize = useCallback(
    (side) => (event) => {
      if (typeof window === "undefined" || window.innerWidth <= DESKTOP_RESIZE_BREAKPOINT) {
        return;
      }

      event.preventDefault();
      setResizingSidebar(side);
    },
    [],
  );

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

  const loadConversations = useCallback(
    async (preferredConversationId = null) => {
      const requestId = latestConversationsRequestRef.current + 1;
      latestConversationsRequestRef.current = requestId;

      setLoadingConversations(true);
      setConversationError("");

      try {
        const payload = await apiCall("/conversations");
        if (requestId !== latestConversationsRequestRef.current) {
          return;
        }

        const nextConversations = Array.isArray(payload) ? payload : [];
        setConversations(nextConversations);
        const previousConversationId = activeConversationIdRef.current;
        let resolvedConversationId = nextConversations[0]?.id || null;

        if (
          preferredConversationId &&
          nextConversations.some((conversation) => conversation.id === preferredConversationId)
        ) {
          resolvedConversationId = preferredConversationId;
        } else if (
          previousConversationId &&
          nextConversations.some((conversation) => conversation.id === previousConversationId)
        ) {
          resolvedConversationId = previousConversationId;
        }

        setConversationSelection(resolvedConversationId);
      } catch {
        if (requestId !== latestConversationsRequestRef.current) {
          return;
        }
        setConversationError("Failed to load conversations.");
      } finally {
        if (requestId === latestConversationsRequestRef.current) {
          setLoadingConversations(false);
        }
      }
    },
    [setConversationSelection],
  );

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
        const validIds = new Set(
          nextDocuments
            .filter((document) => document.processed === "completed")
            .map((document) => document.id),
        );

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
      setConversationSelection(nextConversationId);
      await loadConversations(nextConversationId);
      setMessages([]);
      focusComposer();
    } catch {
      setConversationError("Failed to create conversation.");
    }
  }, [focusComposer, loadConversations, setConversationSelection]);

  const handleSelectConversation = useCallback(
    (conversationId) => {
      setConversationSelection(conversationId);
    },
    [setConversationSelection],
  );

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
        setConversationSelection(requestConversationId);
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

      updateRunState(requestConversationId, {
        runId,
        status: "queued",
        error: "",
        latestEvent: null,
        events: [],
      });

      async function pollRunUntilComplete(pollRunId, conversationId) {
        let pollStatus = null;
        let latestEventsCursor = null;

        for (let attempt = 0; attempt < RUN_POLL_MAX_ATTEMPTS; attempt += 1) {
          try {
            const [statusResult, eventsResult] = await Promise.allSettled([
              runtimeApiCall(`/runs/${pollRunId}/status`),
              runtimeApiCall(buildRunEventsUrl(pollRunId, latestEventsCursor)),
            ]);

            if (statusResult.status !== "fulfilled") {
              throw statusResult.reason || new Error("Run status request failed");
            }

            pollStatus = statusResult.value;
            let nextEvents = [];

            if (eventsResult.status === "fulfilled") {
              const eventsPayload = eventsResult.value;
              nextEvents = Array.isArray(eventsPayload?.events) ? eventsPayload.events : [];
              latestEventsCursor = eventsPayload?.next_after || latestEventsCursor;
            }

            updateRunState(conversationId, (previousRunState) => {
              const mergedEvents = mergeRunEvents(previousRunState.events, nextEvents);

              return {
                runId: pollRunId,
                status: pollStatus?.status || previousRunState.status || "queued",
                error: pollStatus?.error || "",
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

          if (!RUN_IN_PROGRESS_STATUSES.has(pollStatus?.status)) {
            break;
          }

          await sleep(RUN_POLL_INTERVAL_MS);
        }

        if (!pollStatus || RUN_IN_PROGRESS_STATUSES.has(pollStatus.status)) {
          throw new Error("Run polling timed out");
        }

        return pollStatus;
      }

      let runFinalStatus = null;
      let runFinalError = null;

      await new Promise((resolve, reject) => {
        const cleanup = subscribeToRunStream(runId, {
          onStateUpdate: ({ type, event, status: completeStatus, error }) => {
            if (type === "run_event") {
              updateRunState(requestConversationId, (prev) => {
                const merged = mergeRunEvents(prev.events, [event]);
                return {
                  runId,
                  status: event.status || prev.status,
                  error: prev.error,
                  events: merged,
                  latestEvent: merged[merged.length - 1] || prev.latestEvent || null,
                };
              });
            } else if (type === "run_complete") {
              runFinalStatus = completeStatus;
              runFinalError = error;
              updateRunState(requestConversationId, (prev) => ({
                ...prev,
                status: completeStatus,
                error: error || "",
              }));
            }
          },
          onComplete: () => {
            resolve();
          },
          onFallback: () => {
            pollRunUntilComplete(runId, requestConversationId)
              .then((s) => {
                runFinalStatus = s?.status;
                runFinalError = s?.error;
                resolve();
              })
              .catch(reject);
          },
        });
        activeStreamCleanupRef.current = cleanup;
      });
      activeStreamCleanupRef.current = null;

      const status = { status: runFinalStatus, error: runFinalError };

      if (!status.status || RUN_IN_PROGRESS_STATUSES.has(status.status)) {
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
      activeStreamCleanupRef.current = null;

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
    setConversationSelection,
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
    const preferredConversationId = initialConversationId || readConversationIdFromLocation();
    if (preferredConversationId) {
      setConversationSelection(preferredConversationId, { syncUrl: false });
    }

    void loadTools();
    void loadConversations(preferredConversationId);
    void loadDocuments();
  }, [initialConversationId, loadConversations, loadDocuments, loadTools, setConversationSelection]);

  useEffect(() => {
    activeConversationIdRef.current = currentConversationId;
  }, [currentConversationId]);

  useEffect(() => {
    uploadingRef.current = uploading;
  }, [uploading]);

  useEffect(() => {
    if (view !== "chat") {
      return;
    }

    focusComposer();
  }, [focusComposer, currentConversationId, view]);

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
    if (view !== "chat") {
      return;
    }

    const lastMessage = messages[messages.length - 1];
    if (!lastMessage || lastMessage.role !== "assistant" || lastMessage.isThinking) {
      return;
    }

    focusComposer();
  }, [focusComposer, messages, view]);

  useEffect(() => {
    if (view !== "chat") {
      return undefined;
    }

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
        event.key === " " ||
        isEditableElement(event.target) ||
        isInteractiveElement(event.target)
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
  }, [focusComposer, view]);

  useEffect(() => {
    return () => {
      if (focusAnimationFrameRef.current !== null) {
        cancelAnimationFrame(focusAnimationFrameRef.current);
      }

      if (uploadResetTimerRef.current) {
        clearTimeout(uploadResetTimerRef.current);
      }

      if (activeStreamCleanupRef.current) {
        activeStreamCleanupRef.current();
      }
    };
  }, []);

  useEffect(() => {
    if (!resizingSidebar) {
      return undefined;
    }

    const updateSidebarWidth = (clientX) => {
      const appRoot = appRootRef.current;
      if (!appRoot) {
        return;
      }

      const rootBounds = appRoot.getBoundingClientRect();

      if (resizingSidebar === "left") {
        const rawWidth = clientX - rootBounds.left - APP_ROOT_PADDING - PANEL_GAP / 2;
        if (rawWidth <= PANEL_COLLAPSE_THRESHOLD) {
          setLeftCollapsed(true);
          return;
        }

        setLeftCollapsed(false);
        setLeftPanelWidth(Math.min(MAX_LEFT_PANEL_WIDTH, Math.max(MIN_LEFT_PANEL_WIDTH, rawWidth)));
        return;
      }

      const rawWidth = rootBounds.right - APP_ROOT_PADDING - clientX - PANEL_GAP / 2;
      if (rawWidth <= PANEL_COLLAPSE_THRESHOLD) {
        setRightCollapsed(true);
        return;
      }

      setRightCollapsed(false);
      setRightPanelWidth(Math.min(MAX_RIGHT_PANEL_WIDTH, Math.max(MIN_RIGHT_PANEL_WIDTH, rawWidth)));
    };

    const onPointerMove = (event) => {
      updateSidebarWidth(event.clientX);
    };

    const onPointerUp = () => {
      setResizingSidebar(null);
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);

    document.body.style.cursor = "ew-resize";
    document.body.style.userSelect = "none";

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [resizingSidebar]);

  const currentConversation =
    conversations.find((conversation) => conversation.id === currentConversationId) || null;
  const activeRun =
    (currentConversationId && runStateByConversation[currentConversationId]) ||
    runStateByConversation[NEW_CONVERSATION_KEY] ||
    null;
  const selectedDocumentDetails = documents.filter(
    (document) => selectedDocuments.has(document.id) && document.processed === "completed",
  );
  const currentConversationKey = currentConversationId || NEW_CONVERSATION_KEY;
  const appRootStyle = {
    "--left-panel-width": `${leftCollapsed ? COLLAPSED_PANEL_WIDTH : leftPanelWidth}px`,
    "--right-panel-width": `${rightCollapsed ? COLLAPSED_PANEL_WIDTH : rightPanelWidth}px`,
  };

  return (
    <div
      ref={appRootRef}
      style={appRootStyle}
      className={`app-root ${leftCollapsed ? "left-collapsed" : ""} ${rightCollapsed ? "right-collapsed" : ""} ${resizingSidebar ? "resizing" : ""}`}
    >
      <ConversationList
        conversations={conversations}
        currentConversationId={currentConversationId}
        runStateByConversation={runStateByConversation}
        isLoading={loadingConversations}
        error={conversationError}
        isCollapsed={leftCollapsed}
        onToggleCollapse={toggleLeftCollapsed}
        onCreateConversation={createConversation}
        onSelectConversation={handleSelectConversation}
      />

      {leftCollapsed ? (
        <button
          type="button"
          className="sidebar-reopen-button left"
          onClick={toggleLeftCollapsed}
          aria-label="Reopen conversations sidebar"
        >
          ☰
        </button>
      ) : null}

      <div
        className={`sidebar-resizer left ${resizingSidebar === "left" ? "active" : ""}`}
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize conversations sidebar"
        onPointerDown={startSidebarResize("left")}
      />

      {view === "activity" ? (
        <ActivityDashboard
          currentConversationId={currentConversationId}
          currentConversationTitle={currentConversation?.title || ""}
          activeRun={activeRun}
          selectedDocumentCount={selectedDocuments.size}
          tools={tools}
          conversations={conversations}
        />
      ) : view === "metrics" ? (
        <MetricsDashboard currentConversationId={currentConversationId} />
      ) : (
        <ChatPanel
          ref={messageInputRef}
          currentView={view}
          currentConversationId={currentConversationId}
          currentConversationTitle={currentConversation?.title || ""}
          activeRun={activeRun}
          selectedDocumentDetails={selectedDocumentDetails}
          tools={tools}
          messages={messages}
          isLoadingMessages={loadingMessages}
          chatError={chatError}
          messageInput={messageInput}
          isSending={sendingConversations.has(currentConversationKey)}
          onChangeMessage={setMessageInput}
          onChoosePromptStarter={(prompt) => {
            setMessageInput(prompt);
            focusComposer();
          }}
          onSendMessage={sendMessage}
          onFocusComposer={focusComposer}
        />
      )}

      {rightCollapsed ? (
        <button
          type="button"
          className="sidebar-reopen-button right"
          onClick={toggleRightCollapsed}
          aria-label="Reopen workspace sidebar"
        >
          ≡
        </button>
      ) : null}

      <div
        className={`sidebar-resizer right ${resizingSidebar === "right" ? "active" : ""}`}
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize workspace sidebar"
        onPointerDown={startSidebarResize("right")}
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
        onToggleCollapse={toggleRightCollapsed}
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
              const document = documents.find((item) => item.id === documentId);
              if (document?.processed === "completed") {
                nextSelected.add(documentId);
              }
            } else {
              nextSelected.delete(documentId);
            }
            return nextSelected;
          });
        }}
        onSelectReadyDocuments={() => {
          setSelectedDocuments(new Set(documents
            .filter((document) => document.processed === "completed")
            .map((document) => document.id)));
        }}
        onClearSelectedDocuments={() => {
          setSelectedDocuments(new Set());
        }}
        onDeleteDocument={onDeleteDocument}
        fileInputRef={fileInputRef}
      />
    </div>
  );
}
