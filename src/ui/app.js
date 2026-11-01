const form = document.querySelector("#research-form");
const topicInput = document.querySelector("#topic");
const characterCount = document.querySelector("#character-count");
const launchButton = document.querySelector("#launch-button");
const formError = document.querySelector("#form-error");
const activityPanel = document.querySelector("#activity-panel");
const activityTopic = document.querySelector("#activity-topic");
const statusBadge = document.querySelector("#run-status");
const statusText = document.querySelector("#run-status-text");
const progressFill = document.querySelector("#progress-fill");
const analystsSection = document.querySelector("#analysts-section");
const analystGrid = document.querySelector("#analyst-grid");
const analystTotal = document.querySelector("#analyst-total");
const approvalControls = document.querySelector("#approval-controls");
const analystFeedback = document.querySelector("#analyst-feedback");
const approveButton = document.querySelector("#approve-button");
const reviseButton = document.querySelector("#revise-button");
const reportSection = document.querySelector("#report-section");
const reportContent = document.querySelector("#report-content");
const runError = document.querySelector("#run-error");
const toast = document.querySelector("#toast");
const menuButton = document.querySelector("#menu-button");
const sidebar = document.querySelector("#sidebar");
const activeJobStorageKey = "datahelix.activeResearchJob";

let activeJobId = null;
let pollTimer = null;
let toastTimer = null;

document.querySelector("#today-date").textContent = new Intl.DateTimeFormat(
  undefined,
  { month: "short", day: "numeric", year: "numeric" },
).format(new Date());

topicInput.addEventListener("input", () => {
  characterCount.textContent = `${topicInput.value.length} / 500`;
});

document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    topicInput.value = button.dataset.topic || "";
    topicInput.dispatchEvent(new Event("input"));
    topicInput.focus();
  });
});

document.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", () => {
    document.querySelectorAll(".nav-link").forEach((item) => {
      item.classList.toggle("active", item === link);
    });
    sidebar.classList.remove("open");
    menuButton.setAttribute("aria-expanded", "false");
  });
});

menuButton.addEventListener("click", () => {
  const isOpen = sidebar.classList.toggle("open");
  menuButton.setAttribute("aria-expanded", String(isOpen));
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideFormError();
  const topic = topicInput.value.trim();
  if (topic.length < 3) {
    showFormError("Add a research question with at least 3 characters.");
    topicInput.focus();
    return;
  }

  setLaunchState(true);
  try {
    const result = await request("/api/research", {
      method: "POST",
      body: JSON.stringify({
        topic,
        max_analysts: Number(document.querySelector("#analyst-count").value),
      }),
    });
    resetActivity(topic);
    activeJobId = result.id;
    storeActiveJob(activeJobId);
    await pollJob();
  } catch (error) {
    showFormError(error.message);
    setLaunchState(false);
  }
});

approveButton.addEventListener("click", () => submitAnalystFeedback(true));
reviseButton.addEventListener("click", () => submitAnalystFeedback(false));

document.querySelector("#copy-report").addEventListener("click", async () => {
  const button = document.querySelector("#copy-report");
  const report = reportContent.dataset.report || "";
  try {
    await navigator.clipboard.writeText(report);
    button.textContent = "Copied";
    showToast("Report copied to clipboard.");
    window.setTimeout(() => {
      button.textContent = "Copy report";
    }, 1400);
  } catch {
    showToast("Clipboard access is unavailable in this browser.");
  }
});

async function request(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
  } catch {
    throw new Error("Could not reach the DataHelix server. Check your connection and try again.");
  }

  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`The server returned an invalid response (HTTP ${response.status}).`);
  }
  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `The request failed (HTTP ${response.status}).`,
    );
  }
  return data;
}

async function checkHealth() {
  const engineStatus = document.querySelector("#engine-status");
  const healthNote = document.querySelector("#health-note");
  try {
    const health = await request("/api/health");
    document.querySelectorAll("[data-service]").forEach((item) => {
      const configured = health.services?.[item.dataset.service];
      setConnectionState(item, Boolean(configured));
    });
    if (health.ready) {
      engineStatus.textContent = "Configuration ready";
      healthNote.textContent = "Provider credentials are present. Connectivity is verified when a research run starts.";
    } else {
      engineStatus.textContent = "Setup needed";
      const missing = Object.entries(health.services || {})
        .filter(([, configured]) => !configured)
        .map(([key]) => key);
      healthNote.textContent = `Configure ${missing.join(" and ")} in the server environment to enable live research.`;
    }
  } catch {
    engineStatus.textContent = "Server unavailable";
    healthNote.textContent = "Could not reach the API. Start the server and reload this page.";
    document.querySelectorAll("[data-service]").forEach((item) => {
      setConnectionState(item, false, "Offline");
    });
  }
}

function setConnectionState(element, isReady, missingLabel = "Not set") {
  element.classList.toggle("ready", isReady);
  element.classList.toggle("missing", !isReady);
  element.querySelector("span").textContent = isReady ? "Configured" : missingLabel;
}

function resetActivity(topic) {
  window.clearTimeout(pollTimer);
  activeJobId = null;
  activityTopic.textContent = topic;
  activityPanel.hidden = false;
  analystsSection.hidden = true;
  approvalControls.hidden = true;
  reportSection.hidden = true;
  runError.hidden = true;
  analystGrid.replaceChildren();
  reportContent.replaceChildren();
  reportContent.dataset.report = "";
  setStepState("analysts", "active");
  ["approval", "research", "report"].forEach((step) => setStepState(step, ""));
  setProgress("starting");
  setRunStatus("starting", "Starting");
  activityPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function pollJob() {
  if (!activeJobId) return;
  try {
    const job = await request(`/api/research/${encodeURIComponent(activeJobId)}`);
    renderJob(job);
    if (job.status === "completed" || job.status === "failed" || job.status === "awaiting_approval") {
      setLaunchState(false);
      if (job.status !== "awaiting_approval") storeActiveJob(null);
      return;
    }
  } catch (error) {
    showRunError(error.message);
    setLaunchState(false);
    return;
  }
  pollTimer = window.setTimeout(pollJob, 1800);
}

function renderJob(job) {
  const labels = {
    starting: "Starting",
    generating_analysts: "Finding perspectives",
    awaiting_approval: "Ready for review",
    researching: "Researching",
    completed: "Report ready",
    failed: "Needs attention",
  };
  setRunStatus(job.status, labels[job.status] || "Working");
  setProgress(job.status);

  if (Array.isArray(job.analysts) && job.analysts.length) {
    renderAnalysts(job.analysts);
    analystsSection.hidden = false;
  }

  if (job.status === "awaiting_approval") {
    approvalControls.hidden = false;
    setApprovalState(false);
    setLaunchState(false);
  } else {
    approvalControls.hidden = true;
  }

  if (job.status === "completed") {
    storeActiveJob(null);
    if (typeof job.report !== "string" || !job.report.trim()) {
      showRunError("The workflow finished without a report. Please start a new run.");
      return;
    }
    renderReport(job.report);
    reportSection.hidden = false;
    setLaunchState(false);
    reportSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  if (job.status === "failed") {
    storeActiveJob(null);
    showRunError(job.error || "The research run could not be completed. Please try again.");
    setLaunchState(false);
  }
}

function renderAnalysts(analysts) {
  analystGrid.replaceChildren();
  analystTotal.textContent = `${analysts.length} ${analysts.length === 1 ? "perspective" : "perspectives"}`;

  analysts.forEach((analyst) => {
    const card = document.createElement("article");
    card.className = "analyst-card";
    const header = document.createElement("div");
    header.className = "analyst-card-head";

    const avatar = document.createElement("span");
    avatar.className = "analyst-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = (analyst.name || "A").trim().charAt(0).toUpperCase();

    const identity = document.createElement("div");
    const name = document.createElement("div");
    name.className = "analyst-name";
    name.textContent = analyst.name || "Research analyst";
    const role = document.createElement("div");
    role.className = "analyst-role";
    role.textContent = analyst.role || "Research perspective";
    identity.append(name, role);
    header.append(avatar, identity);

    const affiliation = document.createElement("p");
    affiliation.className = "analyst-affiliation";
    affiliation.textContent = analyst.affiliation || "Independent perspective";
    card.append(header, affiliation);

    if (analyst.description) {
      const description = document.createElement("p");
      description.className = "analyst-description";
      description.textContent = analyst.description;
      card.append(description);
    }
    analystGrid.append(card);
  });
}

function renderReport(report) {
  reportContent.replaceChildren();
  reportContent.dataset.report = report;
  let currentList = null;
  let paragraph = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const element = document.createElement("p");
    element.textContent = paragraph.join(" ");
    reportContent.append(element);
    paragraph = [];
  };
  const closeList = () => {
    currentList = null;
  };

  report.split(/\r?\n/).forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      closeList();
      return;
    }

    const heading = line.match(/^#{1,6}\s+(.+)$/);
    if (heading) {
      flushParagraph();
      closeList();
      const element = document.createElement("h3");
      element.textContent = heading[1];
      reportContent.append(element);
      return;
    }

    const listItem = line.match(/^(?:[-*]\s+|\d+[.)]\s+)(.+)$/);
    if (listItem) {
      flushParagraph();
      const isOrdered = /^\d+[.)]\s+/.test(line);
      const listTag = isOrdered ? "OL" : "UL";
      if (!currentList || currentList.tagName !== listTag) {
        currentList = document.createElement(listTag.toLowerCase());
        reportContent.append(currentList);
      }
      const item = document.createElement("li");
      item.textContent = listItem[1];
      currentList.append(item);
      return;
    }

    closeList();
    paragraph.push(line);
  });
  flushParagraph();
}

async function submitAnalystFeedback(approved) {
  const feedback = analystFeedback.value.trim();
  if (!approved && !feedback) {
    showToast("Add a note first if you want to revise the analyst perspectives.");
    analystFeedback.focus();
    return;
  }

  setApprovalState(true);
  runError.hidden = true;
  try {
    await request(`/api/research/${encodeURIComponent(activeJobId)}/approval`, {
      method: "POST",
      body: JSON.stringify({ approved, feedback: feedback || null }),
    });
    approvalControls.hidden = true;
    setRunStatus(approved ? "researching" : "generating_analysts", approved ? "Researching" : "Refreshing analysts");
    if (approved) {
      setStepState("analysts", "done");
      setStepState("approval", "done");
      setStepState("research", "active");
    } else {
      setStepState("analysts", "active");
      setStepState("approval", "");
      analystFeedback.value = "";
    }
    setProgress(approved ? "researching" : "generating_analysts");
    setLaunchState(true);
    await pollJob();
  } catch (error) {
    showRunError(error.message);
    setApprovalState(false);
  }
}

function setApprovalState(isBusy) {
  approveButton.disabled = isBusy;
  reviseButton.disabled = isBusy;
  approveButton.textContent = isBusy ? "Starting…" : "Looks good — start research →";
}

function setLaunchState(isBusy) {
  launchButton.disabled = isBusy;
  launchButton.querySelector("span").textContent = isBusy ? "Research in progress" : "Launch research";
}

function setProgress(status) {
  const states = {
    starting: { active: "analysts", done: [], percent: 8 },
    generating_analysts: { active: "analysts", done: [], percent: 22 },
    awaiting_approval: { active: "approval", done: ["analysts"], percent: 38 },
    researching: { active: "research", done: ["analysts", "approval"], percent: 67 },
    completed: { active: null, done: ["analysts", "approval", "research", "report"], percent: 100 },
    failed: { active: null, done: [], percent: 0 },
  };
  const current = states[status] || states.starting;
  ["analysts", "approval", "research", "report"].forEach((step) => {
    const state = current.done.includes(step)
      ? "done"
      : current.active === step
        ? "active"
        : "";
    setStepState(step, state);
  });
  progressFill.style.width = `${current.percent}%`;
}

function setStepState(step, state) {
  const element = document.querySelector(`[data-step="${step}"]`);
  if (!element) return;
  element.classList.toggle("active", state === "active");
  element.classList.toggle("done", state === "done");
}

function setRunStatus(state, label) {
  statusBadge.dataset.state = state;
  statusText.textContent = label;
}

function showFormError(message) {
  formError.textContent = message;
  formError.hidden = false;
}

function hideFormError() {
  formError.textContent = "";
  formError.hidden = true;
}

function showRunError(message) {
  runError.textContent = message;
  runError.hidden = false;
  setRunStatus("failed", "Needs attention");
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 2600);
}

function storeActiveJob(jobId) {
  try {
    if (jobId) {
      localStorage.setItem(activeJobStorageKey, jobId);
    } else {
      localStorage.removeItem(activeJobStorageKey);
    }
  } catch {
    showToast("This browser could not save the run. Keep this tab open until it finishes.");
  }
}

async function restoreActiveJob() {
  let savedJobId;
  try {
    savedJobId = localStorage.getItem(activeJobStorageKey);
  } catch {
    return;
  }
  if (!savedJobId) return;

  activeJobId = savedJobId;
  try {
    const job = await request(`/api/research/${encodeURIComponent(activeJobId)}`);
    activityTopic.textContent = job.topic;
    activityPanel.hidden = false;
    renderJob(job);
    if (job.status === "awaiting_approval") {
      setLaunchState(false);
    } else if (job.status === "completed" || job.status === "failed") {
      setLaunchState(false);
    } else {
      setLaunchState(true);
      await pollJob();
    }
  } catch (error) {
    if (error.message === "Research run not found.") {
      storeActiveJob(null);
    } else {
      showToast(error.message);
    }
  }
}

checkHealth();
restoreActiveJob();
