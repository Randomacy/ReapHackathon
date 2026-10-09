import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron";

export type DebugStep = "nudge" | "confirming" | "searching" | "payment" | "dismiss";

const DEBUG_CHANNEL = "agent:debug";
const INTERACTIVE_CHANNEL = "overlay:interactive";
const VISIBILITY_CHANNEL = "overlay:visibility";

export interface AgentBridge {
  onDebug: (callback: (step: DebugStep) => void) => () => void;
  setInteractive: (interactive: boolean) => void;
  setVisible: (visible: boolean) => void;
}

const agentBridge: AgentBridge = {
  onDebug(callback) {
    const listener = (_event: IpcRendererEvent, step: DebugStep) => callback(step);
    ipcRenderer.on(DEBUG_CHANNEL, listener);
    return () => ipcRenderer.removeListener(DEBUG_CHANNEL, listener);
  },
  setInteractive(interactive) {
    ipcRenderer.send(INTERACTIVE_CHANNEL, interactive);
  },
  setVisible(visible) {
    ipcRenderer.send(VISIBILITY_CHANNEL, visible);
  },
};

contextBridge.exposeInMainWorld("agentBridge", agentBridge);
