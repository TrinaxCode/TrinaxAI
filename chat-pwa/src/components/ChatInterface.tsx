import { memo } from 'react';
import { useChatController, type ChatInterfaceProps } from '../hooks/useChatController';
import { ChatInterfaceView } from './chat/ChatInterfaceView';

function ChatInterface(props: ChatInterfaceProps) {
  const controller = useChatController(props);
  return <ChatInterfaceView controller={controller} />;
}

export default memo(ChatInterface);
