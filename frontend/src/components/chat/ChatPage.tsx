import { useState, useEffect, useRef, FormEvent, KeyboardEvent } from 'react';
import {
  listOwnConversationsApiV1SessionConversationsGet,
  newChatApiV1SessionNewChatPost,
  continueChatApiV1SessionContinueChatPost,
  getOwnConversationApiV1SessionConversationsConvIdGet,
  clearOwnSessionApiV1SessionConversationsConvIdDelete,
  renameOwnConversationApiV1SessionConversationsConvIdRenamePatch,
} from '../../client/sdk.gen';
import type { ConversationSummary, ChatMessage } from '../../client/types.gen';
import { Button, Spinner, EmptyState, Alert } from '../shared/ui';

interface Message {
  role: string;
  content: string;
  created_at?: string | null;
}

export function ChatPage() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isLoadingConvs, setIsLoadingConvs] = useState(true);
  const [isLoadingMsgs, setIsLoadingMsgs] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  // Load conversation list
  const loadConversations = async () => {
    setIsLoadingConvs(true);
    const result = await listOwnConversationsApiV1SessionConversationsGet();
    if (result.data) {
      setConversations(result.data.conversations ?? []);
    }
    setIsLoadingConvs(false);
  };

  useEffect(() => { loadConversations(); }, []);

  // Load messages when conversation changes
  useEffect(() => {
    if (!activeConvId) { setMessages([]); return; }
    const load = async () => {
      setIsLoadingMsgs(true);
      const result = await getOwnConversationApiV1SessionConversationsConvIdGet({
        path: { conv_id: activeConvId },
      });
      if (result.data) setMessages(result.data.conversation_history ?? []);
      setIsLoadingMsgs(false);
    };
    load();
  }, [activeConvId]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!query.trim() || isSending) return;
    setError(null);

    const userMessage: Message = { role: 'user', content: query };
    setMessages((prev) => [...prev, userMessage]);
    const sentQuery = query;
    setQuery('');
    setIsSending(true);

    try {
      if (!activeConvId) {
        // Start a new conversation
        const result = await newChatApiV1SessionNewChatPost({
          body: { query: sentQuery },
        });
        if (result.data) {
          setActiveConvId(result.data.conversation_id);
          setMessages([
            userMessage,
            { role: 'assistant', content: result.data.reply },
          ]);
          await loadConversations();
        } else {
          setError('Failed to start conversation');
          setMessages((prev) => prev.slice(0, -1));
        }
      } else {
        // Continue existing conversation
        const result = await continueChatApiV1SessionContinueChatPost({
          body: { conversation_id: activeConvId, query: sentQuery },
        });
        if (result.data) {
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: result.data!.reply },
          ]);
        } else {
          setError('Failed to send message');
          setMessages((prev) => prev.slice(0, -1));
        }
      }
    } catch {
      setError('Something went wrong');
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDeleteConv = async (convId: string) => {
    if (!confirm('Delete this conversation?')) return;
    await clearOwnSessionApiV1SessionConversationsConvIdDelete({ path: { conv_id: convId } });
    if (activeConvId === convId) {
      setActiveConvId(null);
      setMessages([]);
    }
    await loadConversations();
  };

  const handleRename = async (convId: string) => {
    if (!renameValue.trim()) return;
    await renameOwnConversationApiV1SessionConversationsConvIdRenamePatch({
      path: { conv_id: convId },
      body: { title: renameValue.trim() },
    });
    setRenamingId(null);
    setRenameValue('');
    await loadConversations();
  };

  const startNewChat = () => {
    setActiveConvId(null);
    setMessages([]);
    setError(null);
  };

  return (
    <div className="flex h-full">
      {/* Conversation list */}
      <aside className="w-64 border-r border-gray-200 bg-white flex flex-col shrink-0">
        <div className="px-4 py-4 border-b border-gray-100">
          <Button variant="primary" size="sm" className="w-full" onClick={startNewChat}>
            + New chat
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {isLoadingConvs ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : conversations.length === 0 ? (
            <EmptyState icon="💬" title="No conversations yet" description="Start a new chat above" />
          ) : (
            conversations.map((conv) => (
              <ConversationItem
                key={conv.conversation_id}
                conv={conv}
                isActive={activeConvId === conv.conversation_id}
                isRenaming={renamingId === conv.conversation_id}
                renameValue={renameValue}
                onSelect={() => setActiveConvId(conv.conversation_id)}
                onDelete={() => handleDeleteConv(conv.conversation_id)}
                onStartRename={() => {
                  setRenamingId(conv.conversation_id);
                  setRenameValue(conv.title ?? '');
                }}
                onRenameChange={setRenameValue}
                onRenameSubmit={() => handleRename(conv.conversation_id)}
                onRenameCancel={() => setRenamingId(null)}
              />
            ))
          )}
        </div>
      </aside>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {isLoadingMsgs ? (
            <div className="flex justify-center py-16"><Spinner size="lg" /></div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-indigo-100 flex items-center justify-center text-3xl mb-4">💬</div>
              <h2 className="text-lg font-semibold text-gray-800">How can I help?</h2>
              <p className="text-sm text-gray-500 mt-1">Type a message below to get started.</p>
            </div>
          ) : (
            messages.map((msg, i) => <MessageBubble key={i} message={msg} />)
          )}
          {isSending && (
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white text-sm font-bold shrink-0">A</div>
              <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-none px-4 py-3">
                <Spinner size="sm" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Error */}
        {error && (
          <div className="px-6 pb-2">
            <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>
          </div>
        )}

        {/* Input */}
        <div className="px-6 py-4 border-t border-gray-200 bg-white">
          <form onSubmit={handleSend} className="flex gap-3 items-end">
            <textarea
              className="flex-1 resize-none px-4 py-3 text-sm border border-gray-300 rounded-xl
                focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                min-h-[48px] max-h-36"
              placeholder="Type a message… (Enter to send, Shift+Enter for new line)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
            />
            <Button type="submit" isLoading={isSending} disabled={!query.trim()} size="lg">
              Send
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';
  return (
    <div className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0
          ${isUser ? 'bg-gray-200 text-gray-600' : 'bg-indigo-600 text-white'}`}
      >
        {isUser ? 'U' : 'A'}
      </div>
      <div
        className={`max-w-[70%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap
          ${isUser
            ? 'bg-indigo-600 text-white rounded-tr-none'
            : 'bg-white border border-gray-200 text-gray-800 rounded-tl-none'}`}
      >
        {message.content}
      </div>
    </div>
  );
}

interface ConvItemProps {
  conv: ConversationSummary;
  isActive: boolean;
  isRenaming: boolean;
  renameValue: string;
  onSelect: () => void;
  onDelete: () => void;
  onStartRename: () => void;
  onRenameChange: (v: string) => void;
  onRenameSubmit: () => void;
  onRenameCancel: () => void;
}

function ConversationItem({
  conv, isActive, isRenaming, renameValue,
  onSelect, onDelete, onStartRename, onRenameChange, onRenameSubmit, onRenameCancel,
}: ConvItemProps) {
  if (isRenaming) {
    return (
      <div className="px-3 py-2">
        <input
          autoFocus
          className="w-full text-sm px-2 py-1 border border-indigo-400 rounded focus:outline-none"
          value={renameValue}
          onChange={(e) => onRenameChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onRenameSubmit();
            if (e.key === 'Escape') onRenameCancel();
          }}
        />
        <div className="flex gap-2 mt-1">
          <button className="text-xs text-indigo-600 font-medium" onClick={onRenameSubmit}>Save</button>
          <button className="text-xs text-gray-400" onClick={onRenameCancel}>Cancel</button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`group flex items-center gap-2 px-3 py-2.5 cursor-pointer rounded-lg mx-2 transition-colors
        ${isActive ? 'bg-indigo-50' : 'hover:bg-gray-50'}`}
      onClick={onSelect}
    >
      <div className="flex-1 min-w-0">
        <p className={`text-sm truncate ${isActive ? 'text-indigo-700 font-medium' : 'text-gray-700'}`}>
          {conv.title || 'Untitled conversation'}
        </p>
        <p className="text-xs text-gray-400">
          {conv.message_count} message{conv.message_count !== 1 ? 's' : ''}
        </p>
      </div>
      <div className="hidden group-hover:flex items-center gap-1 shrink-0">
        <button
          title="Rename"
          className="p-1 text-gray-400 hover:text-gray-600 rounded"
          onClick={(e) => { e.stopPropagation(); onStartRename(); }}
        >✏️</button>
        <button
          title="Delete"
          className="p-1 text-gray-400 hover:text-red-500 rounded"
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
        >🗑️</button>
      </div>
    </div>
  );
}