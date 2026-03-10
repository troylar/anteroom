/**
 * Shared cleanup logic for pending approval/ask_user prompt cards (#864).
 *
 * Used by chat.js (Chat.cleanupPendingPrompts) and app.js (_connectEventSource).
 * Loaded via <script> in index.html — defines a global function.
 * Tests load this file via vitest setupFiles to get the same global.
 */

// eslint-disable-next-line no-unused-vars
function cleanupPendingPrompts(shownIds) {
    document.querySelectorAll('.approval-prompt:not(.approval-allowed):not(.approval-denied)').forEach(el => {
        const id = el.getAttribute('data-approval-id');
        if (id && shownIds) shownIds.delete(id);
        el.remove();
    });
    document.querySelectorAll('.ask-user-prompt:not(.ask-user-answered):not(.ask-user-cancelled)').forEach(el => {
        const id = el.getAttribute('data-ask-id');
        if (id && shownIds) shownIds.delete(id);
        el.remove();
    });
}
