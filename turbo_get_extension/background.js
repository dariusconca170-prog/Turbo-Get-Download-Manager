// The name must match the 'name' in your native host manifest file
const NATIVE_HOST_NAME = "io.github.dariusconca170-prog.turboget";

// 1. Intercept downloads
chrome.downloads.onCreated.addListener((downloadItem) => {
    // We only want to intercept downloads that are "in_progress"
    if (downloadItem.state === 'in_progress') {
        // Cancel the browser's download
        chrome.downloads.cancel(downloadItem.id);

        // Send the URL to our native application
        const port = chrome.runtime.connectNative(NATIVE_HOST_NAME);
        port.postMessage({ url: downloadItem.finalUrl });

        port.onDisconnect.addListener(() => {
            if (chrome.runtime.lastError) {
                console.error("Failed to connect:", chrome.runtime.lastError.message);
            }
        });
    }
});

// 2. Add "Download with TurboGet" to the right-click context menu
chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: "download-with-turboget",
        title: "Download with TurboGet",
        contexts: ["link"]
    });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === "download-with-turboget") {
        const port = chrome.runtime.connectNative(NATIVE_HOST_NAME);
        port.postMessage({ url: info.linkUrl });
    }
});