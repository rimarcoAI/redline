(function () {
  "use strict";

  const EXERCISES = window.EXERCISES_DATA || [];
  const BY_ID = new Map(EXERCISES.map((e) => [e.id, e]));

  const LABELS = {
    bodyPart: {
      arms: "Brazos",
      back: "Espalda",
      cardio: "Cardio",
      chest: "Pecho",
      core: "Core",
      legs: "Piernas",
      shoulders: "Hombros",
    },
    muscle: {
      abductors: "Abductores",
      abs: "Abdominales",
      adductors: "Aductores",
      biceps: "Bíceps",
      calves: "Gemelos",
      cardio: "Cardio",
      delts: "Deltoides",
      forearms: "Antebrazos",
      glutes: "Glúteos",
      hamstrings: "Isquiotibiales",
      lats: "Dorsales",
      "levator-scapulae": "Elevador de la escápula",
      pectorals: "Pectorales",
      quads: "Cuádriceps",
      "serratus-anterior": "Serrato anterior",
      spine: "Espalda baja / columna",
      traps: "Trapecios",
      triceps: "Tríceps",
      "upper-back": "Espalda alta",
    },
    equipment: {
      band: "Banda elástica",
      barbell: "Barra",
      bodyweight: "Peso corporal",
      cable: "Polea/Cable",
      dumbbell: "Mancuerna",
      "ez-bar": "Barra Z",
      kettlebell: "Kettlebell",
      lever: "Máquina de palanca",
      machine: "Máquina",
      other: "Otro",
      sled: "Trineo",
      smith: "Multipower",
    },
    category: {
      cardio: "Cardio",
      plyometrics: "Pliometría",
      strength: "Fuerza",
      stretching: "Estiramiento",
    },
  };

  function label(kind, value) {
    if (!value) return "";
    return (LABELS[kind] && LABELS[kind][value]) || value;
  }

  // ---------------------------------------------------------------------
  // Storage
  // ---------------------------------------------------------------------
  const STORAGE_TAGS = "exgym_exercise_tags_v1";
  const STORAGE_ROUTINES = "exgym_routines_v1";

  function loadJSON(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }
  function saveJSON(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  let exerciseTags = loadJSON(STORAGE_TAGS, {}); // { exerciseId: [tags] }
  let routines = loadJSON(STORAGE_ROUTINES, []); // [{id, title, tags, exerciseIds, createdAt, updatedAt}]

  function persistTags() { saveJSON(STORAGE_TAGS, exerciseTags); }
  function persistRoutines() { saveJSON(STORAGE_ROUTINES, routines); }

  function getExerciseTags(id) { return exerciseTags[id] || []; }

  function normalizeTag(raw) {
    let t = (raw || "").trim().toLowerCase();
    t = t.replace(/\s+/g, "-");
    t = t.replace(/^#+/, "");
    t = t.replace(/[^\p{L}\p{N}_-]/gu, "");
    if (!t) return null;
    return "#" + t;
  }

  function addTagToExercise(exerciseId, rawTag) {
    const tag = normalizeTag(rawTag);
    if (!tag) return null;
    const current = exerciseTags[exerciseId] || [];
    if (!current.includes(tag)) {
      exerciseTags[exerciseId] = [...current, tag];
      persistTags();
    }
    return tag;
  }
  function removeTagFromExercise(exerciseId, tag) {
    const current = exerciseTags[exerciseId] || [];
    exerciseTags[exerciseId] = current.filter((t) => t !== tag);
    persistTags();
  }

  function allExerciseTags() {
    const set = new Set();
    Object.values(exerciseTags).forEach((tags) => tags.forEach((t) => set.add(t)));
    return [...set].sort();
  }
  function allRoutineTags() {
    const set = new Set();
    routines.forEach((r) => (r.tags || []).forEach((t) => set.add(t)));
    return [...set].sort();
  }
  function allTagsCombined() {
    return [...new Set([...allExerciseTags(), ...allRoutineTags()])].sort();
  }

  function uid() {
    return "r_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  // ---------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------
  const state = {
    view: "exercises",
    search: "",
    bodyPart: "",
    muscle: "",
    equipment: "",
    category: "",
    tags: new Set(),
    selectMode: false,
    selected: new Set(),
    routineTagFilter: new Set(),
    editingRoutineId: null,
    routineDraftExerciseIds: [],
  };

  // ---------------------------------------------------------------------
  // DOM refs
  // ---------------------------------------------------------------------
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  const grid = $("#exerciseGrid");
  const resultsCount = $("#resultsCount");
  const emptyState = $("#emptyState");
  const searchInput = $("#searchInput");
  const filterBodyPart = $("#filterBodyPart");
  const filterMuscle = $("#filterMuscle");
  const filterEquipment = $("#filterEquipment");
  const filterCategory = $("#filterCategory");
  const filterTags = $("#filterTags");
  const selectionBar = $("#selectionBar");
  const selectionCount = $("#selectionCount");
  const selectModeToggle = $("#selectModeToggle");

  const routinesGrid = $("#routinesGrid");
  const emptyRoutines = $("#emptyRoutines");
  const filterRoutineTags = $("#filterRoutineTags");

  const exerciseModal = $("#exerciseModal");
  const exerciseModalBody = $("#exerciseModalBody");
  const routineModal = $("#routineModal");
  const routineModalBody = $("#routineModalBody");

  function showToast(msg) {
    const toast = $("#toast");
    toast.textContent = msg;
    toast.hidden = false;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => { toast.hidden = true; }, 2200);
  }

  function closeModal(el) { el.hidden = true; el.querySelector(".modal-body").innerHTML = ""; }
  document.addEventListener("click", (e) => {
    if (e.target.matches("[data-close-modal]") || e.target.classList.contains("modal-overlay")) {
      closeModal(exerciseModal);
      closeModal(routineModal);
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeModal(exerciseModal); closeModal(routineModal); }
  });

  // ---------------------------------------------------------------------
  // Tabs
  // ---------------------------------------------------------------------
  $$(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      state.view = tab.dataset.view;
      $$(".tab").forEach((t) => t.classList.toggle("active", t === tab));
      $$(".view").forEach((v) => v.classList.remove("active"));
      $("#view-" + state.view).classList.add("active");
      if (state.view === "routines") renderRoutines();
    });
  });

  // ---------------------------------------------------------------------
  // Filter option population
  // ---------------------------------------------------------------------
  function countBy(key) {
    const counts = {};
    EXERCISES.forEach((e) => { counts[e[key]] = (counts[e[key]] || 0) + 1; });
    return counts;
  }

  function renderChipGroup(container, kind, counts, activeValue, onSelect) {
    container.innerHTML = "";
    Object.keys(counts).sort((a, b) => label(kind, a).localeCompare(label(kind, b))).forEach((value) => {
      const chip = document.createElement("button");
      chip.className = "chip" + (activeValue === value ? " active" : "");
      chip.innerHTML = `${label(kind, value)} <span class="count">${counts[value]}</span>`;
      chip.addEventListener("click", () => onSelect(value));
      container.appendChild(chip);
    });
  }

  function renderBodyPartFilter() {
    const counts = countBy("bodyPart");
    renderChipGroup(filterBodyPart, "bodyPart", counts, state.bodyPart, (value) => {
      state.bodyPart = state.bodyPart === value ? "" : value;
      populateDependentFilters();
      renderAll();
    });
  }

  function renderCategoryFilter() {
    const counts = countBy("category");
    renderChipGroup(filterCategory, "category", counts, state.category, (value) => {
      state.category = state.category === value ? "" : value;
      renderAll();
    });
  }

  function populateSelect(select, kind, values, selectedValue, placeholder) {
    const current = selectedValue;
    select.innerHTML = `<option value="">${placeholder}</option>`;
    values.sort((a, b) => label(kind, a).localeCompare(label(kind, b))).forEach((value) => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label(kind, value);
      if (value === current) opt.selected = true;
      select.appendChild(opt);
    });
  }

  function populateDependentFilters() {
    const scoped = EXERCISES.filter((e) => !state.bodyPart || e.bodyPart === state.bodyPart);
    populateSelect(filterMuscle, "muscle", [...new Set(scoped.map((e) => e.muscle))], state.muscle, "Todos los músculos");
    populateSelect(filterEquipment, "equipment", [...new Set(EXERCISES.map((e) => e.equipment))], state.equipment, "Todo el equipamiento");
  }

  function renderTagFilter() {
    const tags = allExerciseTags();
    if (!tags.length) {
      filterTags.innerHTML = '<span class="hint">Aún no hay etiquetas creadas. Ábrelas desde el detalle de un ejercicio.</span>';
      return;
    }
    filterTags.innerHTML = "";
    tags.forEach((tag) => {
      const chip = document.createElement("button");
      chip.className = "chip tag-chip" + (state.tags.has(tag) ? " active" : "");
      chip.textContent = tag;
      chip.addEventListener("click", () => {
        state.tags.has(tag) ? state.tags.delete(tag) : state.tags.add(tag);
        renderTagFilter();
        renderGrid();
      });
      filterTags.appendChild(chip);
    });
  }

  searchInput.addEventListener("input", (e) => { state.search = e.target.value; renderGrid(); });
  filterMuscle.addEventListener("change", (e) => { state.muscle = e.target.value; renderGrid(); });
  filterEquipment.addEventListener("change", (e) => { state.equipment = e.target.value; renderGrid(); });

  $("#resetFiltersBtn").addEventListener("click", () => {
    state.search = ""; state.bodyPart = ""; state.muscle = ""; state.equipment = "";
    state.category = ""; state.tags = new Set();
    searchInput.value = "";
    populateDependentFilters();
    renderAll();
  });

  selectModeToggle.addEventListener("change", (e) => {
    state.selectMode = e.target.checked;
    if (!state.selectMode) { state.selected.clear(); }
    updateSelectionBar();
    renderGrid();
  });

  $("#clearSelectionBtn").addEventListener("click", () => {
    state.selected.clear();
    updateSelectionBar();
    renderGrid();
  });

  $("#createRoutineFromSelectionBtn").addEventListener("click", () => {
    openRoutineEditor(null, [...state.selected]);
  });

  function updateSelectionBar() {
    selectionBar.hidden = !state.selectMode;
    selectionCount.textContent = state.selected.size;
    $("#createRoutineFromSelectionBtn").disabled = state.selected.size === 0;
  }

  // ---------------------------------------------------------------------
  // Exercise grid
  // ---------------------------------------------------------------------
  function normalizeText(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  function filteredExercises() {
    const q = normalizeText(state.search);
    return EXERCISES.filter((e) => {
      if (state.bodyPart && e.bodyPart !== state.bodyPart) return false;
      if (state.muscle && e.muscle !== state.muscle) return false;
      if (state.equipment && e.equipment !== state.equipment) return false;
      if (state.category && e.category !== state.category) return false;
      if (q && !normalizeText(e.name).includes(q)) return false;
      if (state.tags.size) {
        const tags = getExerciseTags(e.id);
        for (const t of state.tags) if (!tags.includes(t)) return false;
      }
      return true;
    });
  }

  function exerciseCard(e) {
    const card = document.createElement("div");
    card.className = "exercise-card" + (state.selected.has(e.id) ? " selected" : "");
    card.dataset.id = e.id;

    const tags = getExerciseTags(e.id);
    card.innerHTML = `
      <div class="card-media">
        ${state.selectMode ? '<input type="checkbox" class="card-select" ' + (state.selected.has(e.id) ? "checked" : "") + '>' : ""}
        ${e.thumbUrl || e.gifUrl ? `<img loading="lazy" src="${e.thumbUrl || e.gifUrl}" alt="${escapeHtml(e.name)}">` : '<span class="no-media">Sin imagen</span>'}
      </div>
      <div class="card-body">
        <div class="card-title">${escapeHtml(e.name)}</div>
        <div class="card-badges">
          <span class="badge body-part">${label("bodyPart", e.bodyPart)}</span>
          <span class="badge">${label("muscle", e.muscle)}</span>
          <span class="badge">${label("equipment", e.equipment)}</span>
        </div>
        ${tags.length ? `<div class="card-tags">${tags.map((t) => `<span class="tag-pill">${escapeHtml(t)}</span>`).join("")}</div>` : ""}
      </div>
    `;

    card.addEventListener("click", (ev) => {
      if (state.selectMode) {
        toggleSelection(e.id);
      } else {
        openExerciseModal(e.id);
      }
    });

    return card;
  }

  function toggleSelection(id) {
    state.selected.has(id) ? state.selected.delete(id) : state.selected.add(id);
    updateSelectionBar();
    renderGrid();
  }

  function renderGrid() {
    const list = filteredExercises();
    grid.innerHTML = "";
    const frag = document.createDocumentFragment();
    list.forEach((e) => frag.appendChild(exerciseCard(e)));
    grid.appendChild(frag);
    resultsCount.textContent = `${list.length} ejercicio${list.length === 1 ? "" : "s"}`;
    emptyState.hidden = list.length !== 0;
  }

  function renderAll() {
    renderBodyPartFilter();
    renderCategoryFilter();
    renderTagFilter();
    renderGrid();
  }

  function escapeHtml(str) {
    return (str || "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  // ---------------------------------------------------------------------
  // Exercise detail modal
  // ---------------------------------------------------------------------
  function tagEditorHtml(currentTags) {
    return `
      <div class="tag-editor" id="tagEditorList">
        ${currentTags.map((t) => `<span class="tag-pill" data-tag="${escapeHtml(t)}">${escapeHtml(t)} <span class="remove-tag" data-remove-tag="${escapeHtml(t)}">✕</span></span>`).join("")}
      </div>
      <div class="tag-input-row">
        <input type="text" id="tagInput" placeholder="Añadir etiqueta, ej. esguincetobillo">
        <button class="btn small primary" id="tagAddBtn">Añadir</button>
      </div>
      <div class="tag-suggestions" id="tagSuggestions"></div>
    `;
  }

  function wireTagEditor(getTags, onAdd, onRemove, rerender) {
    const input = $("#tagInput");
    const addBtn = $("#tagAddBtn");
    const suggestionsBox = $("#tagSuggestions");

    const existing = allTagsCombined();
    function renderSuggestions() {
      const current = getTags();
      const remaining = existing.filter((t) => !current.includes(t));
      suggestionsBox.innerHTML = remaining.length
        ? remaining.map((t) => `<button class="chip" data-suggest="${escapeHtml(t)}">${escapeHtml(t)}</button>`).join("")
        : "";
    }
    renderSuggestions();

    suggestionsBox.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-suggest]");
      if (!btn) return;
      onAdd(btn.dataset.suggest);
      rerender();
    });

    function submit() {
      const val = input.value;
      if (!val.trim()) return;
      onAdd(val);
      input.value = "";
      rerender();
    }
    addBtn.addEventListener("click", submit);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } });

    $("#tagEditorList").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-remove-tag]");
      if (!btn) return;
      onRemove(btn.dataset.removeTag);
      rerender();
    });
  }

  function openExerciseModal(id) {
    const e = BY_ID.get(id);
    if (!e) return;
    exerciseModalBody.innerHTML = `
      <div class="modal-media">${e.gifUrl ? `<img src="${e.gifUrl}" alt="${escapeHtml(e.name)}">` : ""}</div>
      <h2 class="modal-title">${escapeHtml(e.name)}</h2>
      <div class="modal-badges">
        <span class="badge body-part">${label("bodyPart", e.bodyPart)}</span>
        <span class="badge">${label("muscle", e.muscle)}</span>
        <span class="badge">${label("equipment", e.equipment)}</span>
        <span class="badge">${label("category", e.category)}</span>
      </div>
      ${e.secondaryMuscles && e.secondaryMuscles.length ? `
        <div class="modal-section">
          <h4>Músculos secundarios</h4>
          <div class="chip-group">${e.secondaryMuscles.map((m) => `<span class="badge">${label("muscle", m)}</span>`).join("")}</div>
        </div>` : ""}
      ${e.instructions && e.instructions.length ? `
        <div class="modal-section">
          <h4>Instrucciones</h4>
          <ol>${e.instructions.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ol>
        </div>` : ""}
      <div class="modal-section">
        <h4>Etiquetas</h4>
        ${tagEditorHtml(getExerciseTags(e.id))}
      </div>
    `;
    exerciseModal.hidden = false;

    wireTagEditor(
      () => getExerciseTags(e.id),
      (raw) => addTagToExercise(e.id, raw),
      (tag) => removeTagFromExercise(e.id, tag),
      () => { openExerciseModal(e.id); renderGrid(); renderTagFilter(); }
    );
  }

  // ---------------------------------------------------------------------
  // Routines view
  // ---------------------------------------------------------------------
  function renderRoutineTagFilter() {
    const tags = allRoutineTags();
    if (!tags.length) { filterRoutineTags.innerHTML = ""; return; }
    filterRoutineTags.innerHTML = "";
    tags.forEach((tag) => {
      const chip = document.createElement("button");
      chip.className = "chip tag-chip" + (state.routineTagFilter.has(tag) ? " active" : "");
      chip.textContent = tag;
      chip.addEventListener("click", () => {
        state.routineTagFilter.has(tag) ? state.routineTagFilter.delete(tag) : state.routineTagFilter.add(tag);
        renderRoutines();
      });
      filterRoutineTags.appendChild(chip);
    });
  }

  function routineCard(routine) {
    const exs = routine.exerciseIds.map((id) => BY_ID.get(id)).filter(Boolean);
    const card = document.createElement("div");
    card.className = "routine-card";
    const shown = exs.slice(0, 5);
    const remaining = exs.length - shown.length;
    card.innerHTML = `
      <h3>${escapeHtml(routine.title)}</h3>
      <div class="routine-meta">${exs.length} ejercicio${exs.length === 1 ? "" : "s"} · creada ${new Date(routine.createdAt).toLocaleDateString("es-ES")}</div>
      <div class="routine-thumbs">
        ${shown.map((e) => `<img src="${e.thumbUrl || e.gifUrl}" alt="${escapeHtml(e.name)}" title="${escapeHtml(e.name)}">`).join("")}
        ${remaining > 0 ? `<div class="more">+${remaining}</div>` : ""}
      </div>
      ${routine.tags && routine.tags.length ? `<div class="routine-tags">${routine.tags.map((t) => `<span class="tag-pill">${escapeHtml(t)}</span>`).join("")}</div>` : ""}
      <div class="routine-actions">
        <button class="btn small" data-edit-routine="${routine.id}">Editar</button>
        <button class="btn small danger" data-delete-routine="${routine.id}">Eliminar</button>
      </div>
    `;
    return card;
  }

  function renderRoutines() {
    renderRoutineTagFilter();
    let list = routines;
    if (state.routineTagFilter.size) {
      list = list.filter((r) => {
        const tags = r.tags || [];
        for (const t of state.routineTagFilter) if (!tags.includes(t)) return false;
        return true;
      });
    }
    list = [...list].sort((a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""));
    routinesGrid.innerHTML = "";
    list.forEach((r) => routinesGrid.appendChild(routineCard(r)));
    emptyRoutines.hidden = list.length !== 0;
  }

  routinesGrid.addEventListener("click", (e) => {
    const editBtn = e.target.closest("[data-edit-routine]");
    const delBtn = e.target.closest("[data-delete-routine]");
    if (editBtn) {
      const r = routines.find((x) => x.id === editBtn.dataset.editRoutine);
      if (r) openRoutineEditor(r.id, r.exerciseIds);
    }
    if (delBtn) {
      const r = routines.find((x) => x.id === delBtn.dataset.deleteRoutine);
      if (r && confirm(`¿Eliminar la rutina "${r.title}"?`)) {
        routines = routines.filter((x) => x.id !== r.id);
        persistRoutines();
        renderRoutines();
        showToast("Rutina eliminada");
      }
    }
  });

  $("#newRoutineBtn").addEventListener("click", () => openRoutineEditor(null, []));

  // ---------------------------------------------------------------------
  // Routine editor modal
  // ---------------------------------------------------------------------
  function openRoutineEditor(routineId, initialExerciseIds) {
    const existing = routineId ? routines.find((r) => r.id === routineId) : null;
    state.editingRoutineId = routineId;
    state.routineDraftExerciseIds = [...(initialExerciseIds || [])];
    let draftTags = existing ? [...(existing.tags || [])] : [];

    function chosenListHtml() {
      const exs = state.routineDraftExerciseIds.map((id) => BY_ID.get(id)).filter(Boolean);
      if (!exs.length) return '<div class="chosen-empty">Aún no has añadido ejercicios.</div>';
      return exs.map((e) => `
        <div class="chosen-row" data-chosen-id="${e.id}">
          <img src="${e.thumbUrl || e.gifUrl}" alt="">
          <div class="info">
            <span class="name">${escapeHtml(e.name)}</span>
            <span class="sub">${label("bodyPart", e.bodyPart)} · ${label("muscle", e.muscle)}</span>
          </div>
          <button data-remove-chosen="${e.id}">Quitar</button>
        </div>
      `).join("");
    }

    function pickerListHtml(query) {
      const q = normalizeText(query);
      const list = EXERCISES.filter((e) => !q || normalizeText(e.name).includes(q)).slice(0, 200);
      return list.map((e) => {
        const added = state.routineDraftExerciseIds.includes(e.id);
        return `
          <div class="picker-row${added ? " added" : ""}" data-picker-id="${e.id}">
            <img src="${e.thumbUrl || e.gifUrl}" alt="">
            <div class="info">
              <span class="name">${escapeHtml(e.name)}</span>
              <span class="sub">${label("bodyPart", e.bodyPart)} · ${label("muscle", e.muscle)}</span>
            </div>
            <button data-toggle-picker="${e.id}">${added ? "Añadido" : "Añadir"}</button>
          </div>
        `;
      }).join("");
    }

    routineModalBody.innerHTML = `
      <h2 class="modal-title">${existing ? "Editar rutina" : "Nueva rutina"}</h2>
      <div class="routine-editor">
        <div>
          <div class="routine-editor-field">
            <label>Título</label>
            <input type="text" id="routineTitleInput" placeholder="Ej. Rutina pierna día 1" value="${escapeHtml(existing ? existing.title : "")}">
          </div>
          <div class="routine-editor-field">
            <label>Etiquetas</label>
            ${tagEditorHtml(draftTags)}
          </div>
          <div class="routine-editor-field">
            <label>Ejercicios seleccionados (${state.routineDraftExerciseIds.length})</label>
            <div class="chosen-list" id="chosenList">${chosenListHtml()}</div>
          </div>
        </div>
        <div>
          <label style="display:block;font-size:0.78rem;color:var(--text-dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:.04em;">Añadir ejercicios</label>
          <input type="text" id="pickerSearch" class="picker-search" placeholder="Buscar ejercicio para añadir…">
          <div class="picker-list" id="pickerList">${pickerListHtml("")}</div>
        </div>
      </div>
      <div class="routine-editor-footer">
        <button class="btn ghost" id="cancelRoutineBtn">Cancelar</button>
        <button class="btn primary" id="saveRoutineBtn">Guardar rutina</button>
      </div>
    `;
    routineModal.hidden = false;

    // Tag editor re-renders its whole block on each change to keep listeners in sync.
    function rerenderTagBlock() {
      const container = routineModalBody.querySelector(".routine-editor-field:nth-of-type(2)");
      container.innerHTML = `<label>Etiquetas</label>${tagEditorHtml(draftTags)}`;
      wireTagEditor(
        () => draftTags,
        (raw) => { const t = normalizeTag(raw); if (t && !draftTags.includes(t)) draftTags.push(t); },
        (tag) => { draftTags = draftTags.filter((t) => t !== tag); },
        rerenderTagBlock
      );
    }
    rerenderTagBlock();

    function refreshChosen() {
      $("#chosenList").innerHTML = chosenListHtml();
      const label2 = routineModalBody.querySelector(".routine-editor-field:nth-of-type(3) label");
      if (label2) label2.textContent = `Ejercicios seleccionados (${state.routineDraftExerciseIds.length})`;
      refreshPicker($("#pickerSearch").value);
    }
    function refreshPicker(query) {
      $("#pickerList").innerHTML = pickerListHtml(query);
    }

    $("#chosenList").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-remove-chosen]");
      if (!btn) return;
      state.routineDraftExerciseIds = state.routineDraftExerciseIds.filter((id) => id !== btn.dataset.removeChosen);
      refreshChosen();
    });

    $("#pickerList").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-toggle-picker]");
      if (!btn) return;
      const id = btn.dataset.togglePicker;
      if (state.routineDraftExerciseIds.includes(id)) {
        state.routineDraftExerciseIds = state.routineDraftExerciseIds.filter((x) => x !== id);
      } else {
        state.routineDraftExerciseIds.push(id);
      }
      refreshChosen();
    });

    $("#pickerSearch").addEventListener("input", (e) => refreshPicker(e.target.value));

    $("#cancelRoutineBtn").addEventListener("click", () => closeModal(routineModal));

    $("#saveRoutineBtn").addEventListener("click", () => {
      const title = $("#routineTitleInput").value.trim();
      if (!title) { showToast("Ponle un título a la rutina"); return; }
      if (!state.routineDraftExerciseIds.length) { showToast("Añade al menos un ejercicio"); return; }
      const now = new Date().toISOString();
      if (existing) {
        existing.title = title;
        existing.tags = draftTags;
        existing.exerciseIds = [...state.routineDraftExerciseIds];
        existing.updatedAt = now;
      } else {
        routines.push({
          id: uid(),
          title,
          tags: draftTags,
          exerciseIds: [...state.routineDraftExerciseIds],
          createdAt: now,
          updatedAt: now,
        });
      }
      persistRoutines();
      closeModal(routineModal);
      state.selected.clear();
      state.selectMode = false;
      selectModeToggle.checked = false;
      updateSelectionBar();
      renderGrid();
      state.view = "routines";
      $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === "routines"));
      $$(".view").forEach((v) => v.classList.remove("active"));
      $("#view-routines").classList.add("active");
      renderRoutines();
      showToast(existing ? "Rutina actualizada" : "Rutina creada");
    });
  }

  // ---------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------
  populateDependentFilters();
  renderAll();
  updateSelectionBar();
})();
