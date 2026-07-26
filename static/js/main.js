/**
 * main.js
 * --------
 * Controla o fluxo completo da interface do DataLens:
 * upload (clique ou drag&drop) -> POST /analyze -> renderização do
 * dashboard (KPIs, qualidade dos dados, gráficos Plotly, preview).
 *
 * Não depende de nenhum framework — DOM puro, de propósito, pra manter
 * o projeto simples de rodar (só Flask servindo estático).
 */

(() => {
  "use strict";

  // -------------------------------------------------------------------- //
  // Elementos
  // -------------------------------------------------------------------- //
  const heroSection = document.getElementById("hero-section");
  const dropzone = document.getElementById("dropzone");
  const browseBtn = document.getElementById("browse-btn");
  const fileInput = document.getElementById("file-input");
  const processingState = document.getElementById("processing-state");
  const stepperSteps = Array.from(document.querySelectorAll(".stepper__step"));
  const errorMessage = document.getElementById("error-message");

  const resultsSection = document.getElementById("results-section");
  const resultFilename = document.getElementById("result-filename");
  const resetBtn = document.getElementById("reset-btn");

  const insightText = document.getElementById("insight-text");
  const insightBadge = document.getElementById("insight-badge");

  const kpiGrid = document.getElementById("kpi-grid");
  const qualityGrid = document.getElementById("quality-grid");
  const chartGrid = document.getElementById("chart-grid");
  const previewTable = document.getElementById("preview-table");

  const KPI_LABELS = {
    total_records: "Registros",
    total_columns: "Colunas",
    missing_values: "Valores ausentes",
    duplicated_rows: "Duplicados",
    numeric_columns: "Colunas numéricas",
    categorical_columns: "Colunas categóricas",
  };

  let stepperTimer = null;

  // -------------------------------------------------------------------- //
  // Upload — clique
  // -------------------------------------------------------------------- //
  browseBtn.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("click", (e) => {
    // evita disparar duas vezes quando o clique já veio do botão
    if (e.target === browseBtn) return;
    fileInput.click();
  });
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      handleFile(fileInput.files[0]);
    }
  });

  // -------------------------------------------------------------------- //
  // Upload — drag & drop
  // -------------------------------------------------------------------- //
  ["dragenter", "dragover"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add("dropzone--dragover");
    });
  });

  ["dragleave", "dragend"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dropzone--dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dropzone--dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  });

  // -------------------------------------------------------------------- //
  // Reset
  // -------------------------------------------------------------------- //
  resetBtn.addEventListener("click", resetToUpload);

  function resetToUpload() {
    resultsSection.hidden = true;
    heroSection.classList.remove("hero--collapsed");
    fileInput.value = "";
    hideError();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // -------------------------------------------------------------------- //
  // Fluxo principal
  // -------------------------------------------------------------------- //
  async function handleFile(file) {
    hideError();
    startProcessingUI();

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/analyze", { method: "POST", body: formData });
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Não foi possível analisar o arquivo.");
      }

      finishStepper();
      renderResults(data);
    } catch (err) {
      showError(err.message || "Algo deu errado. Tente novamente.");
      stopProcessingUI();
    }
  }

  // -------------------------------------------------------------------- //
  // Estado de processamento (stepper animado)
  // -------------------------------------------------------------------- //
  function startProcessingUI() {
    dropzone.classList.add("dropzone--processing");
    processingState.hidden = false;

    let activeIndex = 0;
    stepperSteps.forEach((s) => s.classList.remove("stepper__step--active", "stepper__step--done"));
    stepperSteps[0].classList.add("stepper__step--active");

    stepperTimer = setInterval(() => {
      if (activeIndex >= stepperSteps.length - 1) return; // segura no último passo até a resposta chegar
      stepperSteps[activeIndex].classList.remove("stepper__step--active");
      stepperSteps[activeIndex].classList.add("stepper__step--done");
      activeIndex += 1;
      stepperSteps[activeIndex].classList.add("stepper__step--active");
    }, 900);
  }

  function finishStepper() {
    clearInterval(stepperTimer);
    stepperSteps.forEach((s) => {
      s.classList.remove("stepper__step--active");
      s.classList.add("stepper__step--done");
    });
  }

  function stopProcessingUI() {
    clearInterval(stepperTimer);
    dropzone.classList.remove("dropzone--processing");
    processingState.hidden = true;
    stepperSteps.forEach((s) => s.classList.remove("stepper__step--active", "stepper__step--done"));
  }

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.hidden = false;
  }

  function hideError() {
    errorMessage.hidden = true;
    errorMessage.textContent = "";
  }

  // -------------------------------------------------------------------- //
  // Renderização do dashboard
  // -------------------------------------------------------------------- //
  function renderResults(data) {
    stopProcessingUI();

    resultFilename.textContent = data.filename;
    renderInsight(data.insights);
    renderKpis(data.analysis.kpis);
    renderQuality(data.analysis.data_quality);
    renderPreview(data.analysis.preview, data.analysis.general_info.column_names);

    // A seção precisa ficar visível ANTES de renderizar os gráficos:
    // o Plotly mede a largura real do container no momento do newPlot().
    // Se o container ainda estiver com display:none, ele cai no tamanho
    // padrão (700x450) e vaza pros cards vizinhos — era exatamente o bug
    // dos gráficos "pra fora do card".
    heroSection.classList.add("hero--collapsed");
    resultsSection.hidden = false;
    resultsSection.classList.add("fade-in");

    renderCharts(data.charts);

    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderInsight(insights) {
    insightText.textContent = insights.summary;
    if (insights.source === "ai") {
      insightBadge.textContent = "Gerado por IA";
      insightBadge.classList.add("insight-card__badge--ai");
    } else {
      insightBadge.textContent = "Resumo local (sem IA configurada)";
      insightBadge.classList.remove("insight-card__badge--ai");
    }
  }

  function renderKpis(kpis) {
    kpiGrid.innerHTML = "";
    Object.entries(KPI_LABELS).forEach(([key, label]) => {
      if (!(key in kpis)) return;
      const card = document.createElement("div");
      card.className = "kpi-card";

      const value = document.createElement("div");
      value.className = "kpi-card__value";
      value.textContent = kpis[key];

      const labelEl = document.createElement("div");
      labelEl.className = "kpi-card__label";
      labelEl.textContent = label;

      card.append(value, labelEl);
      kpiGrid.appendChild(card);
    });
  }

  function renderQuality(quality) {
    qualityGrid.innerHTML = "";
    const items = [];

    const missingEntries = Object.entries(quality.missing_values_by_column || {});
    if (missingEntries.length > 0) {
      const detail = missingEntries
        .slice(0, 6)
        .map(([col, count]) => `${col}: ${count}`)
        .join(" · ");
      items.push({ level: "warn", title: "Valores ausentes por coluna", detail });
    }

    if (quality.duplicated_rows > 0) {
      items.push({
        level: "warn",
        title: "Linhas duplicadas",
        detail: `${quality.duplicated_rows} linha(s) repetida(s) no dataset`,
      });
    }

    if ((quality.constant_columns || []).length > 0) {
      items.push({
        level: "warn",
        title: "Colunas constantes",
        detail: quality.constant_columns.join(" · "),
      });
    }

    const outlierEntries = Object.entries(quality.outlier_columns || {});
    if (outlierEntries.length > 0) {
      const detail = outlierEntries.map(([col, count]) => `${col}: ${count}`).join(" · ");
      items.push({ level: "bad", title: "Possíveis outliers", detail });
    }

    if ((quality.invalid_date_columns || []).length > 0) {
      const detail = quality.invalid_date_columns
        .map((d) => `${d.column}: ${d.invalid_count}`)
        .join(" · ");
      items.push({ level: "bad", title: "Datas inválidas", detail });
    }

    if (items.length === 0) {
      const empty = document.createElement("p");
      empty.className = "quality-empty";
      empty.textContent = "Nenhum problema de qualidade encontrado — os dados estão limpos e prontos para uso.";
      qualityGrid.appendChild(empty);
      return;
    }

    items.forEach((item) => {
      const el = document.createElement("div");
      el.className = "quality-item";

      const header = document.createElement("div");
      header.className = "quality-item__header";

      const dot = document.createElement("span");
      dot.className = `quality-dot quality-dot--${item.level}`;

      const title = document.createElement("span");
      title.textContent = item.title;

      header.append(dot, title);

      const detail = document.createElement("div");
      detail.className = "quality-item__detail";
      detail.textContent = item.detail;

      el.append(header, detail);
      qualityGrid.appendChild(el);
    });
  }

  const renderedPlotIds = [];

  function renderCharts(charts) {
    chartGrid.innerHTML = "";
    renderedPlotIds.length = 0;

    if (!charts || charts.length === 0) {
      const empty = document.createElement("p");
      empty.className = "quality-empty";
      empty.textContent = "Não foi possível identificar gráficos relevantes para este dataset.";
      chartGrid.appendChild(empty);
      return;
    }

    charts.forEach((chart) => {
      const card = document.createElement("div");
      card.className = "chart-card";

      const title = document.createElement("p");
      title.className = "chart-card__title";
      title.textContent = chart.title;

      const plotDiv = document.createElement("div");
      plotDiv.className = "chart-card__plot";
      plotDiv.id = `chart-${chart.id}`;

      card.append(title, plotDiv);
      chartGrid.appendChild(card);

      // Legendas verticais (padrão do Plotly) empurram a largura do
      // gráfico pra fora em cards estreitos — força horizontal embaixo
      // quando o próprio gráfico já não define uma legenda própria.
      const layout = {
        ...chart.figure.layout,
        autosize: true,
        legend: {
          orientation: "h",
          y: -0.25,
          x: 0.5,
          xanchor: "center",
          ...(chart.figure.layout.legend || {}),
        },
      };

      Plotly.newPlot(plotDiv.id, chart.figure.data, layout, {
        responsive: true,
        displayModeBar: false,
      });

      renderedPlotIds.push(plotDiv.id);
    });

    // Força um recálculo de tamanho logo após o primeiro paint — cobre
    // casos em que a fonte do Google Fonts termina de carregar depois
    // do gráfico e desloca a largura do card em alguns pixels.
    requestAnimationFrame(() => {
      renderedPlotIds.forEach((id) => {
        const el = document.getElementById(id);
        if (el) Plotly.Plots.resize(el);
      });
    });
  }

  let resizeTimeout = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      renderedPlotIds.forEach((id) => {
        const el = document.getElementById(id);
        if (el) Plotly.Plots.resize(el);
      });
    }, 150);
  });

  function renderPreview(rows, columnNames) {
    previewTable.innerHTML = "";
    if (!rows || rows.length === 0) return;

    const columns = columnNames && columnNames.length > 0 ? columnNames : Object.keys(rows[0]);

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    columns.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      columns.forEach((col) => {
        const td = document.createElement("td");
        const value = row[col];
        if (value === null || value === undefined || value === "") {
          td.textContent = "—";
          td.classList.add("is-empty");
        } else {
          td.textContent = value;
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    previewTable.append(thead, tbody);
  }
})();