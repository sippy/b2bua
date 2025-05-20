function updateCallStatus() {
    fetch('/api/active_stats')
        .then(res => res.json())
        .then(data => {
            const box = document.getElementById('call-status');
            box.textContent = `Calls: ${data.connected} / ${data.total}`;
        })
        .catch(err => {
            console.warn("Call status update failed:", err);
        });
}

// Update every 5 seconds
setInterval(updateCallStatus, 5000);

// Trigger immediately on load
document.addEventListener('DOMContentLoaded', updateCallStatus);
