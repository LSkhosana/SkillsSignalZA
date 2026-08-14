const state = { track: "SE Track", record: null, warnings: [] };

const extractForm = document.querySelector("#extract-form");
const recordForm = document.querySelector("#record-form");
const reviewSection = document.querySelector("#review-section");
const recordFields = document.querySelector("#record-fields");
const manualFallback = document.querySelector("#manual-fallback");

const longFields = new Set([
  "Soft Skills Mentioned (verbatim)",
  "Specific Readiness Signals (verbatim, beyond generic buzzwords)",
  "Key Requirements Paragraph (paste)",
  "Notes / Anything Unusual",
]);

const selectOptions = {
  "Work Type": ["", "Remote", "Hybrid", "On-site"],
  "Qualification Required": [
    "Degree required",
    "Degree preferred",
    "Certificate/bootcamp mentioned",
    "No qualification specified",
  ],
  "Git/GitHub Explicitly Named (Y/N)": ["Y", "N"],
  "SQL Explicitly Named (Y/N)": ["Y", "N"],
  "Portfolio/GitHub Requested (Y/N)": ["Y", "N"],
  "Requirement Level (Required/Preferred/Not Mentioned)": ["Required", "Preferred", "Not Mentioned"],
};

extractForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideMessage("extract-error");
  hideMessage("record-error");
  hideMessage("record-success");
  const button = document.querySelector("#extract-button");
  setBusy(button, true, "Extracting...");

  const payload = {
    track: document.querySelector("#track").value,
    url: document.querySelector("#url").value.trim(),
    manual_text: document.querySelector("#manual-text").value.trim(),
  };

  try {
    const response = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      if (data.needs_manual_text) {
        manualFallback.open = true;
        document.querySelector("#manual-text").focus();
      }
      throw new Error(data.error || "Extraction failed.");
    }
    state.track = payload.track;
    state.record = data.record;
    state.warnings = data.warnings || [];
    renderRecord(data.record, state.warnings);
    document.querySelector("#word-count").textContent = `${data.source_word_count} source words`;
    reviewSection.classList.remove("hidden");
    reviewSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showMessage("extract-error", error.message);
  } finally {
    setBusy(button, false, "Extract post");
  }
});

recordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideMessage("record-error");
  hideMessage("record-success");
  const button = recordForm.querySelector('button[type="submit"]');
  setBusy(button, true, "Creating...");
  const record = {};
  recordFields.querySelectorAll("[data-header]").forEach((input) => {
    record[input.dataset.header] = input.value.trim();
  });

  try {
    const response = await fetch("/api/records", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ track: state.track, record }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The record could not be created.");
    showMessage("record-success", `${data.post_id} was added to ${data.track}.`);
    await refreshStatus();
    button.disabled = true;
    button.textContent = "Record created";
  } catch (error) {
    showMessage("record-error", error.message);
    setBusy(button, false, "Create record");
  }
});

document.querySelector("#discard-button").addEventListener("click", () => {
  state.record = null;
  reviewSection.classList.add("hidden");
  recordFields.replaceChildren();
  document.querySelector("#url").focus();
});

function renderRecord(record, warnings) {
  const createButton = recordForm.querySelector('button[type="submit"]');
  createButton.disabled = false;
  createButton.textContent = "Create record";
  recordFields.replaceChildren();
  const headers = Object.keys(record);
  const groups = [
    { title: "Job information", fields: headers.slice(0, 9) },
    { title: "Requirements and technical signals", fields: headers.slice(9, 17) },
    { title: "Verbatim evidence and notes", fields: headers.slice(17) },
  ];

  groups.forEach((group) => {
    const section = document.createElement("section");
    section.className = "field-group";
    const title = document.createElement("h4");
    title.className = "field-group-title";
    title.textContent = group.title;
    const grid = document.createElement("div");
    grid.className = "field-grid";
    group.fields.forEach((header) => grid.appendChild(createField(header, record[header] || "")));
    section.append(title, grid);
    recordFields.appendChild(section);
  });

  const warningBox = document.querySelector("#warning-list");
  warningBox.replaceChildren();
  if (warnings.length) {
    const strong = document.createElement("strong");
    strong.textContent = `${warnings.length} item${warnings.length === 1 ? "" : "s"} to check`;
    const list = document.createElement("ul");
    warnings.forEach((warning) => {
      const item = document.createElement("li");
      item.textContent = warning;
      list.appendChild(item);
    });
    warningBox.append(strong, list);
    warningBox.classList.remove("hidden");
  } else {
    warningBox.classList.add("hidden");
  }
}

function createField(header, value) {
  const label = document.createElement("label");
  const isLong = longFields.has(header);
  const isMissing = !value || value === "Not specified";
  label.className = `field ${isLong ? "full" : ""} ${isMissing ? "needs-review" : "extracted"}`;
  const caption = document.createElement("span");
  caption.textContent = header;
  let input;
  if (selectOptions[header]) {
    input = document.createElement("select");
    selectOptions[header].forEach((optionValue) => {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = optionValue || "Select...";
      input.appendChild(option);
    });
    input.value = value;
  } else if (isLong) {
    input = document.createElement("textarea");
    input.rows = header.startsWith("Key Requirements") ? 6 : 3;
    input.value = value;
  } else {
    input = document.createElement("input");
    input.type = header.includes("URL") ? "url" : "text";
    input.value = value;
  }
  input.dataset.header = header;
  if (header === "Post ID") input.readOnly = true;
  input.addEventListener("input", () => {
    label.classList.toggle("needs-review", !input.value.trim());
    label.classList.toggle("extracted", Boolean(input.value.trim()));
  });
  label.append(caption, input);
  return label;
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Status unavailable.");
    const se = data.counts["SE Track"] || 0;
    const da = data.counts["DA Track"] || 0;
    document.querySelector("#se-count").textContent = se;
    document.querySelector("#da-count").textContent = da;
    document.querySelector("#total-progress").style.width = `${Math.min(100, ((se + da) / 60) * 100)}%`;
    document.querySelector("#export-name").textContent = data.export_name;
    renderRecent(data.recent || []);
  } catch (error) {
    console.error(error);
  }
}

function renderRecent(records) {
  const container = document.querySelector("#recent-records");
  container.replaceChildren();
  if (!records.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No records yet.";
    container.appendChild(empty);
    return;
  }
  records.forEach((record) => {
    const item = document.createElement("div");
    item.className = "recent-item";
    const title = document.createElement("strong");
    title.textContent = record.title || "Untitled role";
    const detail = document.createElement("span");
    detail.textContent = `${record.id} · ${record.company || "Company not entered"}`;
    item.append(title, detail);
    container.appendChild(item);
  });
}

function showMessage(id, text) {
  const element = document.querySelector(`#${id}`);
  element.textContent = text;
  element.classList.remove("hidden");
}

function hideMessage(id) {
  const element = document.querySelector(`#${id}`);
  element.textContent = "";
  element.classList.add("hidden");
}

function setBusy(button, busy, text) {
  button.disabled = busy;
  const label = button.querySelector("span") || button;
  label.textContent = text;
}

refreshStatus();
