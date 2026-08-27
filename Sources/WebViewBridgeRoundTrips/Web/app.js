globalThis.silexWebViewReady = true;
window.silex.on("ping", payload => window.silex.send("pong", payload));
window.silex.on("context-menu-state", () => {
    const event = new MouseEvent("contextmenu", { bubbles: true, cancelable: true });
    document.documentElement.dispatchEvent(event);
    window.silex.send("context-menu-state", event.defaultPrevented ? "disabled" : "enabled");
});
