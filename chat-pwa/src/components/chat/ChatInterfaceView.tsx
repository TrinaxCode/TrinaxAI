import { MdVisibilityOff } from 'react-icons/md';
import type { ChatController } from '../../hooks/useChatController';
import AttachmentPreview from './AttachmentPreview';
import ChatComposer from './ChatComposer';
import ChatHeader from './ChatHeader';
import EmptyChat from './EmptyChat';
import MessageList from './MessageList';
import SpeakingIndicator from './SpeakingIndicator';
import VoiceCallView from './VoiceCallView';
import './chat.css';

export function ChatInterfaceView({ controller }: { controller: ChatController }) {
  const {
    activeCollectionsForRequest,
    activeCollectionIds,
    activityLabel,
    attachmentMenuRef,
    attachedDocs,
    attachedImages,
    attachmentMenuOpen,
    busy,
    callMode,
    canOpenPreview,
    clearAttachedDocs,
    clearDragActive,
    collections,
    continueResponse,
    copiedKey,
    copyMessage,
    customPrompts,
    displayChips,
    docConvertProgress,
    docIndexCollectionId,
    docInputRef,
    docUploadStatus,
    downloadPreviewAttachment,
    dragActive,
    editInputRef,
    editingIndex,
    editingText,
    engine,
    exportMenuOpen,
    exportPdf,
    exportMarkdown,
    exportWord,
    fileInputRef,
    handleDragEnter,
    handleDragLeave,
    handleDragOver,
    handleDrop,
    handleInputChange,
    handleKeyDown,
    handlePaste,
    handlePromptSelect,
    handleSend,
    handleStop,
    imageError,
    indexAttachedDocs,
    input,
    inputRef,
    isDark,
    isMobile,
    listening,
    messages,
    messagesRef,
    motd,
    onEngineChange,
    onMenuToggle,
    onNavigate,
    onPickDocs,
    onPickImage,
    openInBrowser,
    openPreviewAttachment,
    openStoredAttachment,
    placeholder,
    previewAttachment,
    quickChipRotation,
    regenerateFrom,
    researchMode,
    saveEdit,
    showScrollButton,
    scrollToBottom,
    setAttachedImages,
    setAttachmentMenuOpen,
    setDocIndexCollectionId,
    setEditingIndex,
    setEditingText,
    setExportMenuOpen,
    setPreviewAttachment,
    setResearchMode,
    slashFilter,
    slashOpen,
    speak,
    startEdit,
    stopSpeak,
    streamedText,
    streaming,
    temporary,
    textPreview,
    t,
    toggleCollection,
    toggleDictation,
    toggleVoice,
    ttsActiveKey,
    ttsSpeaking,
    ttsSupported,
    updateScrollState,
    userDisplayName,
    voiceSupported,
    webSearchAvailable,
    webSearchMode,
    handleWebSearchModeChange,
  } = controller;

  return (
    <div
      className="chat-interface-enter relative flex h-full min-h-0 min-w-0 max-w-full flex-col overflow-hidden transition-colors duration-300"
      onPaste={handlePaste}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onDragEnd={clearDragActive}
    >
      {dragActive && !callMode && (
        <div role="status" className={`pointer-events-none absolute inset-3 z-[70] grid place-items-center rounded-2xl border-2 border-dashed ${isDark ? 'border-[#4ea3e0] bg-[#006bbd]/20 text-white' : 'border-[#006bbd] bg-white/85 text-[#004d8a]'}`}>
          <span className="rounded-lg px-4 py-2 text-sm font-medium shadow-lg">{t('dropFilesHere')}</span>
        </div>
      )}
      {!callMode && (
        <ChatHeader
          engine={engine}
          temporary={temporary}
          isDark={isDark}
           messageCount={messages.length}
           researchMode={researchMode}
          webSearchMode={webSearchMode}
          webSearchAvailable={webSearchAvailable === true}
          exportMenuOpen={exportMenuOpen}
          onMenuToggle={onMenuToggle}
          onEngineChange={onEngineChange}
           onResearchModeChange={setResearchMode}
            onWebSearchModeChange={handleWebSearchModeChange}
          onExportMenuChange={setExportMenuOpen}
          onExportMarkdown={exportMarkdown}
          onExportPdf={exportPdf}
          onExportWord={exportWord}
          onOpenAgent={onNavigate ? () => onNavigate('agent') : undefined}
        />
      )}

      {callMode ? (
        <VoiceCallView
          isDark={isDark}
          listening={listening}
          speaking={ttsSpeaking}
          thinking={busy}
          onEnd={toggleVoice}
        />
      ) : <>
      {temporary && messages.length === 0 && (
        <div className="shrink-0 px-3 pt-3 sm:px-5">
          <div
            role="status"
            className={`mx-auto flex max-w-xl items-start gap-2.5 rounded-xl border px-3.5 py-2.5 text-xs shadow-sm ${isDark ? 'border-amber-300/25 bg-amber-300/[0.10] text-amber-100/90 shadow-black/20' : 'border-amber-400/45 bg-amber-50 text-amber-900/80 shadow-amber-900/5'}`}
          >
            <MdVisibilityOff size={17} className="mt-0.5 shrink-0" />
            <span><strong>{t('temporaryChat')}.</strong> {t('temporaryChatDescription')}</span>
          </div>
        </div>
      )}

      {messages.length === 0 && !streaming && (
        <EmptyChat
          isDark={isDark}
          motd={motd}
          rotation={quickChipRotation}
          chips={displayChips}
        />
      )}

      <MessageList
        messages={messages}
        streaming={busy}
        activityLabel={activityLabel}
        streamedText={streamedText}
        isDark={isDark}
        userDisplayName={userDisplayName}
        messagesRef={messagesRef}
        editInputRef={editInputRef}
        editingIndex={editingIndex}
        editingText={editingText}
        copiedKey={copiedKey}
        ttsSupported={ttsSupported}
        ttsActiveKey={ttsActiveKey}
        showScrollButton={showScrollButton}
        activeCollections={activeCollectionsForRequest}
        onScroll={updateScrollState}
        onEditingTextChange={setEditingText}
        onCancelEdit={() => setEditingIndex(null)}
        onSaveEdit={saveEdit}
        onStartEdit={startEdit}
        onRegenerate={regenerateFrom}
        onContinue={continueResponse}
        onCopy={copyMessage}
        onSpeak={(text, key) => speak(text, undefined, key)}
        onStopSpeak={stopSpeak}
        onOpenAttachment={openStoredAttachment}
        onOpenBrowser={onNavigate ? openInBrowser : undefined}
        onOpenIndexing={onNavigate ? () => onNavigate('indexing') : undefined}
        onScrollToBottom={() => scrollToBottom('smooth')}
      />

      <SpeakingIndicator speaking={ttsSpeaking} />

      <ChatComposer
        engine={engine}
        isDark={isDark}
        collections={collections}
        activeCollectionIds={activeCollectionIds}
        docUploadStatus={docUploadStatus}
        docConvertProgress={docConvertProgress}
        attachedDocs={attachedDocs}
        docIndexCollectionId={docIndexCollectionId}
         attachedImages={attachedImages}
        imageError={imageError}
        streaming={busy}
        attachmentMenuOpen={attachmentMenuOpen}
        slashOpen={slashOpen}
        slashFilter={slashFilter}
        prompts={customPrompts.current}
        input={input}
        placeholder={placeholder}
        voiceSupported={voiceSupported}
        callMode={callMode}
        listening={listening}
        inputRef={inputRef}
        fileInputRef={fileInputRef}
        docInputRef={docInputRef}
        attachmentMenuRef={attachmentMenuRef}
        onToggleCollection={toggleCollection}
        onDocIndexCollectionChange={setDocIndexCollectionId}
        onIndexAttachedDocs={indexAttachedDocs}
        onClearDocs={clearAttachedDocs}
         onRemoveImage={(index) => setAttachedImages((current) => current.filter((_, itemIndex) => itemIndex !== index))}
        onPickImage={onPickImage}
        onPickDocs={onPickDocs}
        onAttachmentMenuChange={setAttachmentMenuOpen}
        onPromptSelect={handlePromptSelect}
        onInputChange={handleInputChange}
        onKeyDown={handleKeyDown}
        onToggleCall={toggleVoice}
        onToggleDictation={toggleDictation}
        onStop={handleStop}
        onSend={handleSend}
      />
      </>}

      <AttachmentPreview
        preview={previewAttachment}
        textPreview={textPreview}
        isDark={isDark}
        isMobile={isMobile}
        canOpen={canOpenPreview}
        onOpen={openPreviewAttachment}
        onDownload={downloadPreviewAttachment}
        onClose={() => setPreviewAttachment(null)}
      />
    </div>
  );
}
