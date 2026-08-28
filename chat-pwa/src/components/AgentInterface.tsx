import { useAgentController } from '../hooks/useAgentController';
import { AgentInterfaceView } from './agent/AgentInterfaceView';
import type { AgentInterfaceProps } from './agent/agentTypes';

export default function AgentInterface(props: AgentInterfaceProps) {
  return <AgentInterfaceView {...useAgentController(props)} />;
}
