// Copyright (c) 2025 Sippy Software, Inc. All rights reserved.
//
// Redistribution and use in source and binary forms, with or without modification,
// are permitted provided that the following conditions are met:
//
// 1. Redistributions of source code must retain the above copyright notice, this
// list of conditions and the following disclaimer.
//
// 2. Redistributions in binary form must reproduce the above copyright notice,
// this list of conditions and the following disclaimer in the documentation and/or
// other materials provided with the distribution.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
// ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
// WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
// ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
// (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
// LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
// ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
// SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.action-form').forEach(form => {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const callid = form.dataset.callid;
            const endpoint = form.getAttribute('action');
            fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ callid: callid })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    location.reload();
                } else {
                    alert("Error: " + data.message);
                    location.reload();
                }
            })
            .catch(err => {
                alert("Request failed: " + err);
                location.reload();
            });
        });
    });
});

function checkChanges(selector) {
    const data = {};
    document.querySelectorAll(`#${selector} input:not(:disabled), #${selector} select:not(:disabled)`).forEach(input => {
        let current, original;

        if (input.type === 'checkbox') {
            current = input.checked;
            original = input.dataset.original === 'true';
        } else if (input.tagName === 'SELECT') {
            current = input.value;
            original = input.dataset.original;
            // try to coerce true/false if value is known boolean string
            if (input.dataset.type === 'bool') {
                current = current === 'True';
                original = original === 'True';
            }
        } else if (input.type === 'number') {
            current = parseFloat(input.value);
            original = parseFloat(input.dataset.original);
        } else {
            current = input.value;
            original = input.dataset.original;
        }

        if (current !== original && !(Number.isNaN(current) && Number.isNaN(original))) {
            data[input.name] = current;
        }
    });
    return data;
}

function submitChanges(selector, onsave) {
    const statusIcon = document.getElementById('save-status');
    const saveButton = document.getElementById('save-changes-btn');
    const data = checkChanges(selector);

    if (Object.keys(data).length === 0) {
        alert("No changes to save.");
        location.reload();
        return;
    }

    fetch(onsave, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(res => {
        if (res.status === 'ok') {
            statusIcon.textContent = '✅ Saved successfully';
            saveButton.disabled = true;

            document.querySelectorAll(`#${selector} input`).forEach(input => {
                if (input.name in data) {
                    if (input.type === 'checkbox') {
                        input.dataset.original = input.checked ? 'true' : 'false';
                    } else {
                        input.dataset.original = input.value;
                    }
                }
            });
            setTimeout(() => location.reload(), 500);
        } else {
            alert("Failed: " + res.message);
            location.reload();
        }
    })
    .catch(err => {alert("Error: " + err)});
}

document.addEventListener('DOMContentLoaded', function () {
    const statusIcon = document.getElementById('save-status');
    const saveButton = document.getElementById('save-changes-btn');
    const selector = 'edit-config-table';
    const inputs = document.querySelectorAll(`#${selector} input, #${selector} select`);

    function markUnsaved() {
        const data = checkChanges(selector);
        if (Object.keys(data).length === 0) {
            statusIcon.textContent = '✅ No changes';
            saveButton.disabled = true;
        } else {
            statusIcon.textContent = '🔴 Modified';
            saveButton.disabled = false;
        }
    }

    inputs.forEach(input => {
        input.addEventListener('input', markUnsaved);
        input.addEventListener('change', markUnsaved);
    });

    //markUnsaved();
});
