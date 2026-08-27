import { useState, useEffect, useRef, FormEvent } from 'react';
import {
  listMyUsersApiV1AdminUsersGet,
  chatAsTargetApiV1SessionChatTargetUserIdPost,
  listTargetConversationsApiV1SessionTargetUserIdConversationsGet,
  getTargetConversationApiV1SessionTargetUserIdConversationsConvIdGet,
  clearTargetSessionApiV1SessionTargetUserIdDelete,
} from '../../client/sdk.gen';
import type { UserProfileResponse, ConversationSummary } from '../../client/types.gen';
import { Button, Spinner, Alert, EmptyState, Badge } from '../shared/ui';

interface Message { role: string; content: string; }

export function AdminChatAsUser() {
  const [users, setUsers] = useState<UserProfileResponse[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserProfileResponse | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isLoadingUsers, setIsLoadingUsers] = useState(true);
  const [isLoadingMsgs, setIsLoadingMsgs] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const loadUsers = async () => {
      const result = await listMyUsersApiV1AdminUsersGet();
      if (result.data) setUsers(result.data.users ?? []);
      setIsLoadingUsers(false);
    };
    loadUsers();
  }, []);

  // Load conversations when user changes
  useEffect(() => {
    if (!selectedUser) { setConversations([]); return; }
    const load = async () => {
      const result = await listTargetConversationsApiV1SessionTargetUserIdConversationsGet({
        path: { target_user_id: selectedUser.id },
      });
      if (result.data) setConversations(result.data.conversations ?? []);
    };
    load();
  }, [selectedUser]);

  // Load messages when conversation changes
  useEffect(() => {
    if (!selectedUser || !activeConvId) { setMessages([]); return; }
    const load = async () => {
      setIsLoadingMsgs(true);
      const result = await getTargetConversationApiV1SessionTargetUserIdConversationsConvIdGet({
        path: { target_user_id: selectedUser.id, conv_id: activeConvId },
      });
      if (result.data) setMessages(result.data.conversation_history ?? []);
      setIsLoadingMsgs(false);
    };
    load();
  }, [selectedUser, activeConvId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!query.trim() || !selectedUser || isSending) return;
    setError(null);
    const userMessage: Message = { role: 'user', content: query };
    setMessages((prev) => [...prev, userMessage]);
    const sentQuery = query;
    setQuery('');
    setIsSending(true);

    const result = await chatAsTargetApiV1SessionChatTargetUserIdPost({
      path: { target_user_id: selectedUser.id },
      body: { query: sentQuery },
    });

    if (result.data) {
      setMessages((prev) => [...prev, { role: 'assistant', content: result.data!.reply }]);
    } else {
      setError('Failed to send message');
      setMessages((prev) => prev.slice(0, -1));
    }
    setIsSending(false);
  };

  const handleClearSession = async () => {
    if (!selectedUser || !confirm("Clear this user's active session?")) return;
    await clearTargetSessionApiV1SessionTargetUserIdDelete({
      path: { target_user_id: selectedUser.id },
    });
    setMessages([]);
    setActiveConvId(null);
  };

  if (isLoadingUsers) {
    return <div className="flex justify-center py-16"><Spinner size="lg" /></div>;
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Chat as User</h1>
        <p className="text-sm text-gray-500 mt-0.5">Select a user to chat within their session</p>
      </div>

      {/* User selector */}
      <div className="flex gap-3 flex-wrap mb-6">
        {users.length === 0 ? (
          <p className="text-sm text-gray-500">No users yet. Create users from the My Users tab.</p>
        ) : (
          users.map((u) => (
            <button
              key={u.id}
              onClick={() => { setSelectedUser(u); setActiveConvId(null); setMessages([]); }}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors
                ${selectedUser?.id === u.id
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-indigo-400'}`}
            >
              <span>{u.username}</span>
              {!u.is_active && <Badge variant="red">inactive</Badge>}
            </button>
          ))
        )}
      </div>

      {selectedUser ? (
        <div className="flex gap-4 h-[520px]">
          {/* Conversations */}
          <div className="w-52 bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden">
            <div className="px-3 py-3 border-b border-gray-100 flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Conversations</span>
              <button
                onClick={handleClearSession}
                title="Clear active session"
                className="text-xs text-red-400 hover:text-red-600"
              >
                Clear
              </button>
            </div>
            <div className="flex-1 overflow-y-auto py-1">
              {conversations.length === 0 ? (
                <EmptyState icon="💬" title="No conversations" />
              ) : (
                conversations.map((conv) => (
                  <button
                    key={conv.conversation_id}
                    onClick={() => setActiveConvId(conv.conversation_id)}
                    className={`w-full text-left px-3 py-2.5 text-sm transition-colors
                      ${activeConvId === conv.conversation_id
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'text-gray-700 hover:bg-gray-50'}`}
                  >
                    <p className="truncate font-medium">{conv.title || 'Untitled'}</p>
                    <p className="text-xs text-gray-400">{conv.message_count} messages</p>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Chat panel */}
          <div className="flex-1 bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
              <div className="w-6 h-6 rounded-full bg-amber-100 flex items-center justify-center text-amber-700 text-xs font-bold">
                {selectedUser.username[0].toUpperCase()}
              </div>
              <span className="text-sm font-medium text-gray-700">
                Chatting as <strong>{selectedUser.username}</strong>
              </span>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {isLoadingMsgs ? (
                <div className="flex justify-center py-8"><Spinner /></div>
              ) : messages.length === 0 ? (
                <EmptyState
                  icon="🔁"
                  title="No messages"
                  description={activeConvId
                    ? "This conversation is empty"
                    : "Type below to start chatting in this user's rolling session"}
                />
              ) : (
                messages.map((msg, i) => (
                  <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                    <div
                      className={`max-w-[70%] px-3 py-2 rounded-xl text-sm whitespace-pre-wrap
                        ${msg.role === 'user'
                          ? 'bg-amber-500 text-white rounded-tr-none'
                          : 'bg-gray-100 text-gray-800 rounded-tl-none'}`}
                    >
                      {msg.content}
                    </div>
                  </div>
                ))
              )}
              {isSending && (
                <div className="flex gap-2">
                  <div className="bg-gray-100 px-3 py-2 rounded-xl rounded-tl-none">
                    <Spinner size="sm" />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {error && (
              <div className="px-4 pb-2">
                <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>
              </div>
            )}

            {/* Input */}
            <div className="px-4 py-3 border-t border-gray-100">
              <form onSubmit={handleSend} className="flex gap-2">
                <input
                  className="flex-1 text-sm px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Type a message…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
                  }}
                />
                <Button type="submit" isLoading={isSending} disabled={!query.trim()}>Send</Button>
              </form>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 p-16">
          <EmptyState icon="👆" title="Select a user" description="Choose a user above to view or chat in their session" />
        </div>
      )}
    </div>
  );
}