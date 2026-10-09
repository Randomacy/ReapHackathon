import {
  app,
  BrowserWindow,
  Tray,
  Menu,
  globalShortcut,
  ipcMain,
  screen,
  Notification,
  type Display,
} from "electron";
import path from "node:path";

type DebugStep = "nudge" | "confirming" | "searching" | "payment" | "dismiss";

const WINDOW_WIDTH = 440;
const WINDOW_HEIGHT = 460;
const TOP_MARGIN = 24;
const DEBUG_CHANNEL = "agent:debug";
const INTERACTIVE_CHANNEL = "overlay:interactive";
const VISIBILITY_CHANNEL = "overlay:visibility";

// In dev this is the Next.js dev server; in production it's wherever the
// built Next app is served from (e.g. `next start` on the same port, or a
// deployed URL), set via AGENT_OVERLAY_URL. There's no static export here
// because the app also owns server-side agent/payment API routes.
const OVERLAY_URL = process.env.AGENT_OVERLAY_URL ?? "http://localhost:3000/overlay";

let overlayWindow: BrowserWindow | null = null;
let tray: Tray | null = null;

function positionWindow(window: BrowserWindow, display: Display = screen.getPrimaryDisplay()) {
  const { x, y, width } = display.workArea;
  const left = Math.round(x + (width - WINDOW_WIDTH) / 2);
  const top = Math.round(y + TOP_MARGIN);
  window.setBounds({ x: left, y: top, width: WINDOW_WIDTH, height: WINDOW_HEIGHT });
}

function createOverlayWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT,
    transparent: true,
    frame: false,
    hasShadow: false,
    resizable: false,
    skipTaskbar: true,
    focusable: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  window.setAlwaysOnTop(true, "screen-saver");
  window.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  window.setIgnoreMouseEvents(true, { forward: true });

  positionWindow(window);
  void window.loadURL(OVERLAY_URL);

  window.on("closed", () => {
    overlayWindow = null;
  });

  return window;
}

function repositionOnDisplayChange() {
  if (overlayWindow) positionWindow(overlayWindow);
}

function sendDebugStep(step: DebugStep) {
  overlayWindow?.webContents.send(DEBUG_CHANNEL, step);

  if (step === "nudge") {
    // Fallback in case the overlay window fails to show on this setup.
    if (Notification.isSupported()) {
      new Notification({
        title: "Coffee Agent",
        body: "You seem tired, want a coffee?",
      }).show();
    }
  }
}

function createTray() {
  const iconPath = path.join(__dirname, "..", "electron", "assets", "tray-icon.png");
  tray = new Tray(iconPath);
  tray.setToolTip("Coffee Agent");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Trigger nudge", click: () => sendDebugStep("nudge") },
      { type: "separator" },
      { label: "Quit", click: () => app.quit() },
    ]),
  );
}

function registerShortcuts() {
  globalShortcut.register("Control+Alt+1", () => sendDebugStep("nudge"));
  globalShortcut.register("Control+Alt+2", () => sendDebugStep("confirming"));
  globalShortcut.register("Control+Alt+3", () => sendDebugStep("searching"));
  globalShortcut.register("Control+Alt+4", () => sendDebugStep("payment"));
  globalShortcut.register("Control+Alt+0", () => sendDebugStep("dismiss"));
}

function registerIpcHandlers() {
  ipcMain.on(INTERACTIVE_CHANNEL, (_event, interactive: boolean) => {
    if (!overlayWindow) return;
    if (interactive) {
      overlayWindow.setIgnoreMouseEvents(false);
    } else {
      overlayWindow.setIgnoreMouseEvents(true, { forward: true });
    }
  });

  ipcMain.on(VISIBILITY_CHANNEL, (_event, visible: boolean) => {
    if (!overlayWindow) return;
    if (visible) {
      overlayWindow.showInactive();
    } else {
      overlayWindow.hide();
    }
  });
}

app.whenReady().then(() => {
  // This is a tray/overlay utility, not a regular app window — no dock icon.
  app.dock?.hide();

  overlayWindow = createOverlayWindow();
  createTray();
  registerShortcuts();
  registerIpcHandlers();

  screen.on("display-added", repositionOnDisplayChange);
  screen.on("display-removed", repositionOnDisplayChange);
  screen.on("display-metrics-changed", repositionOnDisplayChange);
});

// Keep the app (and tray) alive even if the overlay window is ever closed;
// Electron's default is to quit on Windows/Linux once all windows close.
app.on("window-all-closed", () => {});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});
