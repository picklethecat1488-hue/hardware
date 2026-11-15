/**
 * Zero-Globals Functional Review Checklist & Demo Command Runner.
 *
 * Renders review verification tasks (`review_tasks`), handles status checkbox toggles,
 * copies demo CLI commands, and executes live demo commands against `${apiBase}/run_command`.
 */

import { bindDelegatedEvent, clearChildren, createEl, resolveElement } from "../core/dom.js";
import { copyToClipboard, showToast } from "../core/toast.js";

/**
 * Render the functional review checklist items into `#review-tasks-list`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {Element|string} containerElOrId - Container element or ID.
 * @param {Array<object>} tasks - Array of `{ id, title, status, command }`.
 */
export function renderReviewTasksList(ctx, containerElOrId, tasks) {
  const container = resolveElement(ctx, containerElOrId);
  if (!container) {
    return;
  }
  clearChildren(container);

  const list = Array.isArray(tasks) ? tasks : [];
  if (list.length === 0) {
    const emptySpan = createEl(ctx, "span", {
      text: "No review tasks defined yet.",
      style: { fontSize: "10px", color: "var(--quake-text-dim)" },
    });
    container.appendChild(emptySpan);
    return;
  }

  for (const task of list) {
    if (!task) continue;
    const taskId = String(task.id || "");
    const status = String(task.status || "PENDING");
    const isDone = status === "COMPLETED";
    const badgeClass = isDone
      ? "quake-badge-green"
      : status === "FAILED"
        ? "quake-badge-red"
        : "quake-badge-muted";

    const row = createEl(ctx, "div", {
      className: "review-task-item",
      style: {
        background: "#120a05",
        border: "1px solid #331f0f",
        borderRadius: "3px",
        padding: "8px 10px",
        marginBottom: "8px",
      },
    });

    const checkbox = createEl(ctx, "input", {
      attrs: { type: "checkbox" },
      dataset: {
        action: "toggle-review-task",
        taskId,
        taskStatus: status,
      },
      style: { cursor: "pointer", width: "14px", height: "14px" },
    });
    checkbox.checked = isDone;
    if (isDone) {
      checkbox.setAttribute("checked", "checked");
    }

    const topRow = createEl(ctx, "div", {
      style: { display: "flex", alignItems: "center", gap: "8px" },
      children: [
        checkbox,
        createEl(ctx, "span", {
          text: String(task.title || ""),
          style: {
            fontSize: "11px",
            fontWeight: "600",
            color: isDone ? "var(--quake-text-dim)" : "#fff",
            textDecoration: isDone ? "line-through" : "none",
            flex: "1",
          },
        }),
        createEl(ctx, "span", {
          className: `quake-badge ${badgeClass}`,
          text: status,
        }),
      ],
    });
    row.appendChild(topRow);

    const cmd = String(task.command || "");
    if (cmd) {
      row.appendChild(
        createEl(ctx, "div", {
          style: {
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginTop: "6px",
            background: "#000",
            border: "1px solid #222",
            borderRadius: "2px",
            padding: "4px 8px",
          },
          children: [
            createEl(ctx, "code", {
              text: cmd,
              style: {
                fontFamily: "var(--font-mono)",
                fontSize: "10px",
                color: "var(--quake-gold)",
                flex: "1",
                overflowX: "auto",
              },
            }),
            createEl(ctx, "button", {
              className: "quake-btn quake-btn-default",
              text: "Copy",
              attrs: { type: "button" },
              dataset: { action: "copy-task-cmd", command: cmd },
              style: { fontSize: "9px", padding: "2px 8px" },
            }),
            createEl(ctx, "button", {
              className: "quake-btn quake-btn-green",
              text: "▶ Run Demo",
              attrs: { type: "button" },
              dataset: { action: "run-task-cmd", taskId, command: cmd },
              style: { fontSize: "9px", padding: "2px 8px" },
            }),
          ],
        }),
      );
      row.appendChild(
        createEl(ctx, "pre", {
          id: `task-output-${taskId}`,
          style: {
            display: "none",
            marginTop: "6px",
            background: "#080503",
            border: "1px solid #331f0f",
            padding: "6px",
            fontFamily: "var(--font-mono)",
            fontSize: "9.5px",
            color: "#ccc",
            maxHeight: "160px",
            overflowY: "auto",
            whiteSpace: "pre-wrap",
          },
        }),
      );
    }

    container.appendChild(row);
  }
}

/**
 * Bind delegated events on `#review-tasks-list` for checkbox toggle, command copy, and demo execution.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {Element|string} containerElOrId - Container element or ID.
 * @param {object} callbacks - `{ onToggleTask, onRunCommand }`.
 */
export function bindReviewTasksEvents(ctx, containerElOrId, callbacks = {}) {
  const container = resolveElement(ctx, containerElOrId);
  if (!container || container.dataset?.boundReviewTasks) {
    return;
  }
  if (container.dataset) {
    container.dataset.boundReviewTasks = "1";
  }

  bindDelegatedEvent(
    container,
    "change",
    '[data-action="toggle-review-task"]',
    (_ev, checkbox) => {
      const taskId = checkbox.dataset?.taskId || "";
      const currentStatus = checkbox.dataset?.taskStatus || "PENDING";
      if (taskId && typeof callbacks.onToggleTask === "function") {
        callbacks.onToggleTask(taskId, currentStatus);
      }
    },
  );

  bindDelegatedEvent(container, "click", '[data-action="copy-task-cmd"]', (_ev, btn) => {
    const cmd = btn.dataset?.command || "";
    if (cmd) {
      void copyToClipboard(ctx, cmd, `Copied: ${cmd}`);
    }
  });

  bindDelegatedEvent(container, "click", '[data-action="run-task-cmd"]', (_ev, btn) => {
    const taskId = btn.dataset?.taskId || "";
    const cmd = btn.dataset?.command || "";
    if (taskId && cmd && typeof callbacks.onRunCommand === "function") {
      callbacks.onRunCommand(taskId, cmd);
    }
  });
}

/**
 * Append a new review verification task via `${apiBase}/add_task`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {string} apiBase - Base tracker API route (`"/api/bugs"` or `"/api/worms"`).
 * @param {string} activeId - Active issue ID.
 * @param {string} title - Task title.
 * @param {string} command - Optional executable demo command.
 * @returns {Promise<object>} Server response payload.
 */
export async function addReviewTask(ctx, apiBase, activeId, title, command) {
  return ctx.postJson(`${apiBase}/add_task`, {
    id: activeId,
    title: String(title || "").trim(),
    command: String(command || "").trim(),
  });
}

/**
 * Toggle a review task between `"COMPLETED"` and `"PENDING"` via `${apiBase}/update_task`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {string} apiBase - Base tracker API route.
 * @param {string} activeId - Active issue ID.
 * @param {string} taskId - Task identifier.
 * @param {string} currentStatus - Current status string.
 * @returns {Promise<object>} Server response payload.
 */
export async function toggleReviewTaskStatus(ctx, apiBase, activeId, taskId, currentStatus) {
  const newStatus = currentStatus === "COMPLETED" ? "PENDING" : "COMPLETED";
  return ctx.postJson(`${apiBase}/update_task`, {
    id: activeId,
    task_id: taskId,
    status: newStatus,
  });
}

/**
 * Execute a review task demo command via `${apiBase}/run_command` and render output into `#task-output-<id>`.
 *
 * @param {object} ctx - Explicit `RuntimeContext`.
 * @param {string} apiBase - Base tracker API route.
 * @param {string} activeId - Active issue ID.
 * @param {string} taskId - Task identifier.
 * @param {string} command - Executable command string.
 * @returns {Promise<object|null>}
 */
export async function runReviewTaskCommand(ctx, apiBase, activeId, taskId, command) {
  const doc = ctx.getDocument();
  const outBox = doc ? doc.getElementById(`task-output-${taskId}`) : null;
  if (outBox) {
    outBox.style.display = "block";
    outBox.textContent = "▶ Executing command...";
  }
  try {
    const data = await ctx.postJson(`${apiBase}/run_command`, {
      id: activeId,
      command,
    });
    if (outBox) {
      const combined =
        String(data.stdout || "") + (data.stderr ? `\n[STDERR]\n${data.stderr}` : "");
      outBox.textContent = `[Exit Code ${data.exit_code}]\n${combined || "(No output)"}`;
    }
    if (data.status === "ok") {
      showToast(ctx, "Command succeeded.", "success");
    } else {
      showToast(ctx, "Command completed with error.", "error");
    }
    return data;
  } catch (err) {
    const message = err && err.message ? err.message : String(err);
    if (outBox) {
      outBox.textContent = `Error executing command: ${message}`;
    }
    showToast(ctx, `Execution failed: ${message}`, "error");
    return null;
  }
}
