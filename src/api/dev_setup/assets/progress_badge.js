(function () {
    const badge = document.createElement("div");
    badge.id = "soc-progress-badge";
    Object.assign(badge.style, {
        position: "fixed",
        bottom: "16px",
        right: "16px",
        zIndex: "9999",
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "8px 14px",
        borderRadius: "999px",
        backgroundColor: "#0f172a",
        color: "#f8fafc",
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        fontSize: "13px",
        fontWeight: "600",
        boxShadow: "0 4px 12px rgba(0, 0, 0, 0.25)",
        border: "1px solid #334155",
    });

    const dot = document.createElement("span");
    Object.assign(dot.style, {
        width: "8px",
        height: "8px",
        borderRadius: "50%",
        backgroundColor: "#94a3b8",
    });

    const label = document.createElement("span");
    label.textContent = "Jobs: syncing...";

    badge.appendChild(dot);
    badge.appendChild(label);
    document.body.appendChild(badge);

    function connect() {
        const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
        const ws = new WebSocket(`${proto}//${window.location.host}/threat_analyzer/progress`);

        ws.onopen = () => {
            dot.style.backgroundColor = "#22c55e";
        };
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (typeof data.processed === "number" && typeof data.total === "number") {
                const runningSuffix = data.in_progress > 0 ? ` (${data.in_progress} running...)` : "";
                dot.style.backgroundColor = data.in_progress > 0 ? "#38bdf8" : "#22c55e";
                label.textContent = `Jobs: ${data.processed} / ${data.total} processed${runningSuffix}`;
            }
        };
        ws.onerror = () => {
            ws.close();
        };
        ws.onclose = () => {
            dot.style.backgroundColor = "#f59e0b";
            label.textContent = "Jobs: reconnecting...";
            setTimeout(connect, 2000);
        };
    }

    connect();
})();