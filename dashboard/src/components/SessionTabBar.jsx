import React, { useState, useRef, useEffect } from 'react';
import { Plus, X, Pencil, Check, Loader2, Film, AlertCircle, Copy, RotateCcw, MoreHorizontal } from 'lucide-react';

/**
 * SessionTabBar provides a tabbed interface for managing multiple video editing/generation sessions.
 * Features:
 * - Switch between active sessions without losing state
 * - Rename tabs inline (double click or pencil button)
 * - Real-time status indicators (idle, processing spinner, completed badge, error)
 * - Add new session tab (+)
 * - Close session tab (with confirmation for active/processing jobs)
 * - Duplicate session
 * - Reset active session
 */
export default function SessionTabBar({
  sessions = [],
  activeSessionId,
  onSelectSession,
  onAddSession,
  onCloseSession,
  onRenameSession,
  onDuplicateSession,
  onResetSession,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const [menuOpenId, setMenuOpenId] = useState(null);
  const inputRef = useRef(null);
  const scrollContainerRef = useRef(null);
  const menuRef = useRef(null);

  // Focus and select text when entering rename mode
  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  // Close context menu on click outside
  useEffect(() => {
    if (!menuOpenId) return;
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpenId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpenId]);

  // Auto-scroll active tab into view when switching tabs
  useEffect(() => {
    if (!scrollContainerRef.current || !activeSessionId) return;
    const activeEl = scrollContainerRef.current.querySelector(`[data-session-id="${activeSessionId}"]`);
    if (activeEl) {
      activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
    }
  }, [activeSessionId]);

  const startRenaming = (session, e) => {
    if (e) e.stopPropagation();
    setEditingId(session.id);
    setEditName(session.name || '');
    setMenuOpenId(null);
  };

  const commitRename = (sessionId) => {
    const trimmed = editName.trim();
    if (trimmed && onRenameSession) {
      onRenameSession(sessionId, trimmed);
    }
    setEditingId(null);
    setEditName('');
  };

  const handleKeyDown = (e, sessionId) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitRename(sessionId);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setEditingId(null);
      setEditName('');
    }
  };

  const handleClose = (session, e) => {
    e.stopPropagation();
    if (session.status === 'processing') {
      const confirmClose = window.confirm(
        `Session "${session.name}" is currently processing video clips.\n\nClosing this tab will remove it from your workspace. Are you sure?`
      );
      if (!confirmClose) return;
    } else if (session.results?.clips?.length > 0) {
      const confirmClose = window.confirm(
        `Session "${session.name}" has generated clips.\n\nClose this session tab?`
      );
      if (!confirmClose) return;
    }
    if (onCloseSession) {
      onCloseSession(session.id);
    }
  };

  const processingCount = sessions.filter((s) => s.status === 'processing').length;
  const completedCount = sessions.filter((s) => s.status === 'complete').length;

  return (
    <div className="bg-paper2/95 border-b border-rule px-3 sm:px-6 py-1.5 flex items-center justify-between gap-2 shrink-0 select-none z-10 backdrop-blur-sm">
      {/* Scrollable Tab Strip */}
      <div
        ref={scrollContainerRef}
        className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5 min-w-0 flex-1 scroll-smooth"
      >
        {sessions.map((session, index) => {
          const isActive = session.id === activeSessionId;
          const isEditing = editingId === session.id;
          const clipCount = session.results?.clips?.length || 0;

          // Status indicator elements
          let StatusIcon = <Film size={12} className="text-muted/70 shrink-0" />;
          let statusBadgeClass = 'text-muted';

          if (session.status === 'processing') {
            StatusIcon = <Loader2 size={12} className="animate-spin text-brass shrink-0" />;
            statusBadgeClass = 'text-brass';
          } else if (session.status === 'complete') {
            StatusIcon = <Check size={12} className="text-ok shrink-0" />;
            statusBadgeClass = 'text-ok';
          } else if (session.status === 'error') {
            StatusIcon = <AlertCircle size={12} className="text-danger shrink-0" />;
            statusBadgeClass = 'text-danger';
          }

          return (
            <div
              key={session.id}
              data-session-id={session.id}
              onClick={() => onSelectSession(session.id)}
              onDoubleClick={(e) => startRenaming(session, e)}
              className={`group relative flex items-center gap-1.5 px-3 py-1.5 rounded-input text-xs font-medium transition-all cursor-pointer shrink-0 border ${
                isActive
                  ? 'bg-paper text-ink border-rule shadow-sm ring-1 ring-brass/25'
                  : 'bg-paper3/40 hover:bg-paper3/80 text-muted hover:text-ink2 border-transparent'
              }`}
              title={
                isEditing
                  ? 'Press Enter to save, Esc to cancel'
                  : `${session.name || `Video ${index + 1}`} (${session.status}${clipCount ? ` · ${clipCount} clips` : ''}) - Double click to rename`
              }
            >
              {/* Status Icon */}
              <span className={`flex items-center ${statusBadgeClass}`}>
                {StatusIcon}
              </span>

              {/* Title Display or Inline Rename Input */}
              {isEditing ? (
                <input
                  ref={inputRef}
                  type="text"
                  value={editName}
                  maxLength={40}
                  onChange={(e) => setEditName(e.target.value)}
                  onBlur={() => commitRename(session.id)}
                  onKeyDown={(e) => handleKeyDown(e, session.id)}
                  onClick={(e) => e.stopPropagation()}
                  className="bg-paper3 text-ink text-xs px-1.5 py-0.5 rounded border border-brass outline-none w-28 sm:w-36 font-normal"
                  placeholder="Session name..."
                />
              ) : (
                <span className="truncate max-w-[110px] sm:max-w-[170px] leading-tight">
                  {session.name || `Video ${index + 1}`}
                </span>
              )}

              {/* Clip Count Badge for Completed Sessions */}
              {session.status === 'complete' && clipCount > 0 && !isEditing && (
                <span className="readout bg-paper3/80 px-1.5 py-0.2 rounded text-[10px] text-ink2 shrink-0">
                  {clipCount}
                </span>
              )}

              {/* Hover Actions: Rename, Context Menu, Close */}
              {!isEditing && (
                <div className="flex items-center gap-0.5 ml-0.5 shrink-0">
                  {/* Pencil Edit Icon Button (visible on hover or active) */}
                  <button
                    type="button"
                    onClick={(e) => startRenaming(session, e)}
                    className={`p-0.5 rounded hover:bg-paper3 hover:text-ink text-muted/60 transition-opacity ${
                      isActive ? 'opacity-70 group-hover:opacity-100' : 'opacity-0 group-hover:opacity-80'
                    }`}
                    title="Rename tab"
                    aria-label="Rename tab"
                  >
                    <Pencil size={11} />
                  </button>

                  {/* Context Menu Button */}
                  <div className="relative">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuOpenId(menuOpenId === session.id ? null : session.id);
                      }}
                      className={`p-0.5 rounded hover:bg-paper3 hover:text-ink text-muted/60 transition-opacity ${
                        isActive ? 'opacity-70 group-hover:opacity-100' : 'opacity-0 group-hover:opacity-80'
                      }`}
                      title="Session options"
                      aria-label="Session options"
                    >
                      <MoreHorizontal size={11} />
                    </button>

                    {/* Dropdown Menu */}
                    {menuOpenId === session.id && (
                      <div
                        ref={menuRef}
                        onClick={(e) => e.stopPropagation()}
                        className="absolute left-0 top-full mt-1.5 w-40 bg-paper2 border border-rule rounded-card shadow-lg py-1 z-30 animate-fade"
                      >
                        <button
                          type="button"
                          onClick={(e) => startRenaming(session, e)}
                          className="w-full px-3 py-1.5 text-left text-xs text-ink hover:bg-paper3 flex items-center gap-2"
                        >
                          <Pencil size={12} className="text-muted" />
                          <span>Rename</span>
                        </button>
                        {onDuplicateSession && (
                          <button
                            type="button"
                            onClick={() => {
                              setMenuOpenId(null);
                              onDuplicateSession(session.id);
                            }}
                            className="w-full px-3 py-1.5 text-left text-xs text-ink hover:bg-paper3 flex items-center gap-2"
                          >
                            <Copy size={12} className="text-muted" />
                            <span>Duplicate Tab</span>
                          </button>
                        )}
                        {onResetSession && isActive && session.status !== 'idle' && (
                          <button
                            type="button"
                            onClick={() => {
                              setMenuOpenId(null);
                              onResetSession();
                            }}
                            className="w-full px-3 py-1.5 text-left text-xs text-ink hover:bg-paper3 flex items-center gap-2"
                          >
                            <RotateCcw size={12} className="text-muted" />
                            <span>Reset Video</span>
                          </button>
                        )}
                        <div className="h-px bg-rule my-1" />
                        <button
                          type="button"
                          onClick={(e) => {
                            setMenuOpenId(null);
                            handleClose(session, e);
                          }}
                          className="w-full px-3 py-1.5 text-left text-xs text-danger hover:bg-danger/10 flex items-center gap-2"
                        >
                          <X size={12} />
                          <span>Close Tab</span>
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Close Tab Button */}
                  <button
                    type="button"
                    onClick={(e) => handleClose(session, e)}
                    className="p-0.5 rounded text-muted hover:text-danger hover:bg-danger/10 transition-colors ml-0.5"
                    title="Close session"
                    aria-label="Close session"
                  >
                    <X size={12} />
                  </button>
                </div>
              )}
            </div>
          );
        })}

        {/* Add New Session Tab Button (+) */}
        <button
          type="button"
          onClick={onAddSession}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-input text-xs text-muted hover:text-ink hover:bg-paper3 border border-dashed border-rule/60 hover:border-rule transition-all shrink-0 active:scale-95"
          title="Add new video session"
          aria-label="Add new video session"
        >
          <Plus size={13} className="text-brass" />
          <span className="hidden sm:inline">New Video</span>
        </button>
      </div>

      {/* Right Side: Quick Stats & Session Summary */}
      <div className="hidden lg:flex items-center gap-2 shrink-0 text-[11px] text-muted">
        {processingCount > 0 && (
          <span className="flex items-center gap-1 text-brass font-medium">
            <Loader2 size={12} className="animate-spin" />
            <span>{processingCount} processing</span>
          </span>
        )}
        {completedCount > 0 && (
          <span className="readout">
            {completedCount} ready
          </span>
        )}
        <span className="readout border-l border-rule pl-2">
          {sessions.length} {sessions.length === 1 ? 'session' : 'sessions'}
        </span>
      </div>
    </div>
  );
}
