"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import ConversationList from "@/components/ConversationList";
import DocumentsPanel from "@/components/DocumentsPanel";
import { apiCall, uploadPdf } from "@/lib/api";

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

export default function HomePage() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [tools, setTools] = useState([]);
  const [documents, setDocuments] = useState([]);

  const [selectedDocuments, setSelectedDocuments] = useState(() => new Set());

  const [messageInput, setMessageInput] = useState("");

  const [loadingConversations, setLoadingConversations] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const [conversationError, setConversationError] = useState("");
  const [chatError, setChatError] = useState("");
  const [documentError, setDocumentError] = useState("");

  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const fileInputRef = useRef(null);

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
      setMessages([]);
      return;
    }

    setLoadingMessages(true);
    setChatError("");

    try {
      const payload = await apiCall(`/conversations/${conversationId}/messages`);
      setMessages(normalizeMessages(payload));
    } catch {
      setMessages([]);
      setChatError("Failed to load conversation messages.");
    } finally {
      setLoadingMessages(false);
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
    } catch {
      setConversationError("Failed to create conversation.");
    }
  }, [loadConversations]);

  const sendMessage = useCallback(async () => {
    const trimmedMessage = messageInput.trim();

    if (!trimmedMessage || sendingMessage) {
      return;
    }

    if (!currentConversationId) {
      setChatError("Create a conversation before sending a message.");
      return;
    }

    setSendingMessage(true);
    setChatError("");
    setMessageInput("");

    const thinkingId = localId("thinking");

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

    try {
      const response = await apiCall("/chat", {
        method: "POST",
        body: JSON.stringify({
          message: trimmedMessage,
          conversation_id: currentConversationId,
          selected_documents: Array.from(selectedDocuments),
        }),
      });

      const assistantMessage = {
        id: localId("assistant"),
        role: "assistant",
        content: response?.response || "",
        timestamp: new Date().toISOString(),
        agent_actions: response?.agent_actions || [],
      };

      setMessages((previousMessages) => [
        ...previousMessages.filter((message) => message.id !== thinkingId),
        assistantMessage,
      ]);

      await loadConversations(currentConversationId);
    } catch {
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
    } finally {
      setSendingMessage(false);
    }
  }, [
    currentConversationId,
    loadConversations,
    messageInput,
    selectedDocuments,
    sendingMessage,
  ]);

  const uploadFiles = useCallback(
    async (files) => {
      const pdfFiles = files.filter((file) => file.type === "application/pdf");

      if (pdfFiles.length === 0) {
        setDocumentError("Please select PDF files only.");
        return;
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

      setTimeout(() => {
        setUploading(false);
        setUploadProgress(0);
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
    void loadConversationMessages(currentConversationId);
  }, [currentConversationId, loadConversationMessages]);

  useEffect(() => {
    const container = document.getElementById("chat-container");
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages]);

  const selectedDocumentsStable = useMemo(() => selectedDocuments, [selectedDocuments]);

  return (
    <div className="app-root">
      <ConversationList
        conversations={conversations}
        currentConversationId={currentConversationId}
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
        isLoadingMessages={loadingMessages}
        chatError={chatError}
        messageInput={messageInput}
        isSending={sendingMessage}
        onChangeMessage={setMessageInput}
        onSendMessage={sendMessage}
      />

      <DocumentsPanel
        documents={documents}
        selectedDocuments={selectedDocumentsStable}
        isLoading={loadingDocuments}
        error={documentError}
        isUploading={uploading}
        uploadProgress={uploadProgress}
        isCollapsed={rightCollapsed}
        isDragActive={dragActive}
        onToggleCollapse={() => setRightCollapsed((isCollapsed) => !isCollapsed)}
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
